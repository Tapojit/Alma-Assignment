from fastapi import FastAPI
import gradio as gr
from google import genai
import os
from pathlib import Path
from typing import Optional, Tuple
from dotenv import load_dotenv
import time

# Import models and form population
from models import FormA28Data
from form_populator import FormPopulator

# Load environment variables
load_dotenv()

# Configure Gemini client
GOOGLE_AI_API_KEY = os.environ.get("GOOGLE_AI_API_KEY")
if not GOOGLE_AI_API_KEY:
    raise ValueError("GOOGLE_AI_API_KEY environment variable not set")

client = genai.Client(api_key=GOOGLE_AI_API_KEY)

main_app = FastAPI()

# Global variable to store extracted data
current_extracted_data = None


def upload_document_to_gemini(file_path: str):
    """Upload document (PDF or image) to Gemini using Files API"""
    if not file_path or not os.path.exists(file_path):
        raise ValueError(f"File not found: {file_path}")

    print(f"Uploading {file_path} to Gemini...")

    # Upload file using new SDK
    uploaded_file = client.files.upload(file=file_path)

    # Wait for file processing
    while uploaded_file.state == "PROCESSING":
        print("Processing document...")
        time.sleep(2)
        uploaded_file = client.files.get(name=uploaded_file.name)

    if uploaded_file.state == "FAILED":
        raise ValueError(f"File processing failed")

    print(f"Document uploaded successfully: {uploaded_file.name}")
    return uploaded_file


def extract_all_data(passport_file_path: Optional[str], g28_file_path: Optional[str]) -> FormA28Data:
    """Extract all data from passport and G-28 documents using Gemini with structured output"""
    try:
        # Upload all available documents
        uploaded_files = []

        if passport_file_path:
            passport_file = upload_document_to_gemini(passport_file_path)
            uploaded_files.append(passport_file)

        if g28_file_path:
            g28_file = upload_document_to_gemini(g28_file_path)
            uploaded_files.append(g28_file)

        if not uploaded_files:
            return FormA28Data()

        # Comprehensive extraction prompt
        extraction_prompt = """Extract ALL information from the provided documents (passport and/or G-28/A-28 form) to fill Form A-28: Legal Documentation.

**PART 1: ATTORNEY/REPRESENTATIVE INFORMATION (from G-28 form)**
- attorney_online_account: USCIS Online Account Number
- attorney_family_name: Attorney's last name
- attorney_given_name: Attorney's first name
- attorney_middle_name: Attorney's middle name
- attorney_street_number: Street number and name
- attorney_apt_ste_flr: Apartment, Suite, or Floor
- attorney_city: City or Town
- attorney_state: State (use abbreviation like CA, NY)
- attorney_zip_code: ZIP Code
- attorney_country: Country
- attorney_daytime_phone: Daytime Telephone Number
- attorney_mobile_phone: Mobile Telephone Number
- attorney_email: Email Address
- attorney_fax_number: Fax Number

**PART 2: ATTORNEY ELIGIBILITY (from G-28 form)**
- attorney_licensing_authority: Licensing Authority (e.g., "State Bar of California")
- attorney_bar_number: Bar Number
- attorney_subject_to_restrictions: "am" or "am not" (whether subject to restrictions)
- attorney_law_firm: Name of Law Firm or Organization
- attorney_recognized_org: Name of Recognized Organization (if accredited rep)
- attorney_accreditation_date: Date of Accreditation (MM/DD/YYYY)

**PART 3: PASSPORT/BENEFICIARY INFORMATION (from passport document)**
- beneficiary_last_name: Last name from passport
- beneficiary_first_name: First name(s) from passport
- beneficiary_middle_name: Middle name(s) from passport
- passport_number: Passport number
- passport_country_of_issue: Country that issued passport
- passport_nationality: Nationality
- beneficiary_date_of_birth: Date of birth (MM/DD/YYYY)
- beneficiary_place_of_birth: Place/city of birth
- beneficiary_sex: Sex (M, F, or X)
- passport_date_of_issue: Passport issue date (MM/DD/YYYY)
- passport_date_of_expiration: Passport expiration date (MM/DD/YYYY)

**PART 4: CLIENT INFORMATION (from G-28 form - this is about the CLIENT/APPLICANT, not the attorney)**
Look for "Information About Client" or "Part 3" or "Part 4" sections in the G-28 form:
- client_family_name: Client's last name
- client_given_name: Client's first name
- client_middle_name: Client's middle name
- client_daytime_phone: Client's daytime telephone
- client_mobile_phone: Client's mobile telephone
- client_email: Client's email address
- client_street_number: Client's street address
- client_apt_ste_flr: Client's apartment/suite/floor
- client_city: Client's city
- client_state: Client's state (use abbreviation if US, otherwise full name)
- client_zip_code: Client's ZIP Code (for US addresses) OR Postal Code (for international addresses) - look for BOTH "ZIP Code" field (13.e) AND "Postal Code" field (13.g)
- client_country: Client's country
- client_uscis_account: Client's USCIS Online Account Number
- client_alien_number: Client's A-Number (Alien Registration Number)

**IMPORTANT INSTRUCTIONS:**
1. Convert ALL dates to MM/DD/YYYY format
2. For sex/gender, return only: M, F, or X
3. If a field is blank/empty in the document, return null (not "N/A" or "N / A")
4. Look at BOTH the passport MRZ and main fields
5. Distinguish between ATTORNEY information (Part 1-2) and CLIENT information (Part 3-4)
6. The client is the person being represented (Joe Jonas in the example)
7. The attorney is the legal representative (Barbara Smith in the example)
8. **CRITICAL**: For client_zip_code, check BOTH fields:
   - Field 13.e "ZIP Code" (for US addresses)
   - Field 13.g "Postal Code" (for international addresses like Australia, Canada, UK)
   - Extract whichever one has a value
9. Return null for any fields not found

Return a JSON object with these exact field names."""

        # Build content array with all files and prompt
        content = uploaded_files + [extraction_prompt]

        # Generate response with structured output using response_json_schema
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=content,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": FormA28Data.model_json_schema(),
            }
        )

        # Parse and validate JSON response using Pydantic
        extracted_data = FormA28Data.model_validate_json(response.text)
        return extracted_data

    except Exception as e:
        print(f"Extraction error: {str(e)}")
        return FormA28Data()


def process_documents(passport_file, g28_file):
    """Extract data from documents"""
    global current_extracted_data

    if passport_file is None and g28_file is None:
        return "Please upload at least one document", None, gr.update(visible=False)

    try:
        status = "Uploading and processing documents..."

        # Extract all data at once
        extracted_data = extract_all_data(passport_file, g28_file)
        current_extracted_data = extracted_data

        # Convert to dict for JSON display
        result = extracted_data.model_dump()

        status = "✓ Data extraction complete. Click 'Submit Form' to populate the form."

        # Make Submit Form button visible
        return status, result, gr.update(visible=True)

    except Exception as e:
        current_extracted_data = None
        return f"✗ Error: {str(e)}", None, gr.update(visible=False)


def submit_form(form_url: str):
    """Populate form using Browserbase"""
    global current_extracted_data

    if current_extracted_data is None:
        return "✗ No data extracted. Please extract data first.", "", None

    if not form_url or not form_url.strip():
        return "✗ Please provide a valid form URL.", "", None

    try:
        status = f"Populating web form at {form_url}..."

        # Populate form using FormPopulator with Browserbase
        form_populator = FormPopulator(form_url=form_url)
        result = form_populator.populate_form(current_extracted_data)

        # Extract results
        screenshot_path = result["screenshot"]
        session_url = result["session_url"]
        session_id = result["session_id"]
        fields_filled = result["fields_filled"]

        status = f"""✓ Form populated successfully ({fields_filled} fields filled)

Form URL: {form_url}
Session ID: {session_id}

Note: Browser session remains open for inspection.
Click the link below to view the live session."""

        # Create clickable HTML link that opens in new tab
        session_html = f"""
        <div style="padding: 15px; background-color: #f0f9ff; border: 2px solid #0284c7; border-radius: 8px; margin: 10px 0;">
            <h3 style="margin: 0 0 10px 0; color: #0284c7;">🔗 Live Browser Session</h3>
            <a href="{session_url}" target="_blank" style="
                display: inline-block;
                padding: 12px 24px;
                background-color: #0284c7;
                color: white;
                text-decoration: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
            ">
                Open Browserbase Session →
            </a>
            <p style="margin: 10px 0 0 0; font-size: 14px; color: #64748b;">
                Session ID: <code>{session_id}</code>
            </p>
        </div>
        """

        return status, session_html, screenshot_path

    except Exception as e:
        return f"✗ Form population error: {str(e)}", "", None


# Gradio interface
with gr.Blocks(title="Alma Assignment") as interface:
    gr.Markdown("# Alma Assignment: Document Processing")
    gr.Markdown(
        "Upload passport and G-28 documents to automatically extract data and populate any web form using Browserbase")
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Upload Documents")
            passport_input = gr.File(
                label="Passport Document",
                file_types=[".pdf", ".jpg", ".jpeg", ".png"],
                type="filepath"
            )
            g28_input = gr.File(
                label="G-28 Form",
                file_types=[".pdf", ".jpg", ".jpeg", ".png"],
                type="filepath"
            )

            gr.Markdown("### Form Configuration")
            form_url_input = gr.Textbox(
                label="Target Form URL",
                value="https://mendrika-alma.github.io/form-submission/",
                placeholder="Enter the URL of the web form to populate",
                info="The web form where extracted data will be automatically filled",
                lines=1
            )

            with gr.Row():
                extract_btn = gr.Button(
                    "Extract Data", variant="primary", size="lg")
                clear_btn = gr.Button(
                    "Clear", variant="secondary", size="lg")

            submit_btn = gr.Button(
                "Submit Form", variant="primary", size="lg", visible=False)

        with gr.Column():
            gr.Markdown("### Results")
            status_output = gr.Textbox(
                label="Status",
                lines=3,
                interactive=False
            )
            session_link_output = gr.HTML(
                label="Browserbase Session",
                visible=False
            )
            data_output = gr.JSON(
                label="Extracted Data"
            )
            screenshot_output = gr.Image(
                label="Populated Form Screenshot",
                type="filepath"
            )

    # Extract Data button click
    extract_btn.click(
        fn=process_documents,
        inputs=[passport_input, g28_input],
        outputs=[status_output, data_output, submit_btn]
    )

    # Submit Form button click
    submit_btn.click(
        fn=submit_form,
        inputs=[form_url_input],
        outputs=[status_output, session_link_output, screenshot_output]
    )

    # Clear button click
    clear_btn.click(
        fn=lambda: (None, None, "https://mendrika-alma.github.io/form-submission/",
                    "", "", None, None, gr.update(visible=False)),
        inputs=[],
        outputs=[passport_input, g28_input, form_url_input, status_output,
                 session_link_output, data_output, screenshot_output, submit_btn]
    )

    gr.Markdown("""
    ---
    ### Instructions:
    1. Upload a passport document (PDF or image format: JPG, PNG)
    2. Upload a G-28 form (PDF or image format: JPG, PNG)
    3. (Optional) Customize the target form URL - defaults to the test form
    4. Click "Extract Data" to extract information using Google Gemini
    5. Click "Submit Form" to populate the web form using Browserbase
    
    **Note:** The form will be populated but NOT submitted (as per requirements)
    """)

main_app = gr.mount_gradio_app(main_app, interface, path="/")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(main_app, host="0.0.0.0", port=8000)
