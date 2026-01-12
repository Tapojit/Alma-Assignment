from fastapi import FastAPI
import gradio as gr
from google import genai
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Configure Gemini client
GOOGLE_AI_API_KEY = os.environ.get("GOOGLE_AI_API_KEY")
if not GOOGLE_AI_API_KEY:
    raise ValueError("GOOGLE_AI_API_KEY environment variable not set")

client = genai.Client(api_key=GOOGLE_AI_API_KEY)

main_app = FastAPI()


class FormA28Data(BaseModel):
    """Complete structured data for Form A-28 from all documents"""

    # Part 1: Attorney/Representative Information
    attorney_online_account: Optional[str] = Field(
        None, description="USCIS Online Account Number")
    attorney_family_name: Optional[str] = Field(
        None, description="Attorney's last name")
    attorney_given_name: Optional[str] = Field(
        None, description="Attorney's first name")
    attorney_middle_name: Optional[str] = Field(
        None, description="Attorney's middle name")
    attorney_street_number: Optional[str] = Field(
        None, description="Street number and name")
    attorney_apt_ste_flr: Optional[str] = Field(
        None, description="Apartment, Suite, or Floor number")
    attorney_city: Optional[str] = Field(None, description="City or Town")
    attorney_state: Optional[str] = Field(
        None, description="State (use abbreviation)")
    attorney_zip_code: Optional[str] = Field(None, description="ZIP Code")
    attorney_country: Optional[str] = Field(None, description="Country")
    attorney_daytime_phone: Optional[str] = Field(
        None, description="Daytime Telephone Number")
    attorney_mobile_phone: Optional[str] = Field(
        None, description="Mobile Telephone Number")
    attorney_email: Optional[str] = Field(None, description="Email Address")
    attorney_fax_number: Optional[str] = Field(None, description="Fax Number")

    # Part 2: Eligibility Information
    attorney_licensing_authority: Optional[str] = Field(
        None, description="State/jurisdiction where licensed")
    attorney_bar_number: Optional[str] = Field(None, description="Bar Number")
    attorney_subject_to_restrictions: Optional[str] = Field(
        None, description="Whether subject to restrictions (am or am not)")
    attorney_law_firm: Optional[str] = Field(
        None, description="Name of Law Firm or Organization")
    attorney_recognized_org: Optional[str] = Field(
        None, description="Name of Recognized Organization")
    attorney_accreditation_date: Optional[str] = Field(
        None, description="Date of Accreditation (MM/DD/YYYY)")

    # Part 3: Passport/Beneficiary Information (from passport document)
    beneficiary_last_name: Optional[str] = Field(
        None, description="Last name from passport")
    beneficiary_first_name: Optional[str] = Field(
        None, description="First name(s) from passport")
    beneficiary_middle_name: Optional[str] = Field(
        None, description="Middle name(s) from passport")
    passport_number: Optional[str] = Field(None, description="Passport number")
    passport_country_of_issue: Optional[str] = Field(
        None, description="Country that issued passport")
    passport_nationality: Optional[str] = Field(
        None, description="Nationality")
    beneficiary_date_of_birth: Optional[str] = Field(
        None, description="Date of birth (MM/DD/YYYY)")
    beneficiary_place_of_birth: Optional[str] = Field(
        None, description="Place/city of birth")
    beneficiary_sex: Optional[str] = Field(
        None, description="Sex (M, F, or X)")
    passport_date_of_issue: Optional[str] = Field(
        None, description="Passport issue date (MM/DD/YYYY)")
    passport_date_of_expiration: Optional[str] = Field(
        None, description="Passport expiration date (MM/DD/YYYY)")

    # Part 4: Client Information (from G-28 form)
    client_family_name: Optional[str] = Field(
        None, description="Client's last name")
    client_given_name: Optional[str] = Field(
        None, description="Client's first name")
    client_middle_name: Optional[str] = Field(
        None, description="Client's middle name")
    client_daytime_phone: Optional[str] = Field(
        None, description="Client's daytime telephone")
    client_mobile_phone: Optional[str] = Field(
        None, description="Client's mobile telephone")
    client_email: Optional[str] = Field(
        None, description="Client's email address")
    client_street_number: Optional[str] = Field(
        None, description="Client's street address")
    client_apt_ste_flr: Optional[str] = Field(
        None, description="Client's apartment/suite/floor")
    client_city: Optional[str] = Field(None, description="Client's city")
    client_state: Optional[str] = Field(None, description="Client's state")
    client_zip_code: Optional[str] = Field(
        None, description="Client's ZIP code")
    client_country: Optional[str] = Field(None, description="Client's country")
    client_uscis_account: Optional[str] = Field(
        None, description="Client's USCIS Online Account Number")
    client_alien_number: Optional[str] = Field(
        None, description="Client's A-Number (Alien Registration Number)")


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
        extraction_prompt = """Extract ALL information from the provided documents (passport and/or G-28 form) to fill Form A-28: Legal Documentation.

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
Look for "Information About Client" or "Part 3" or "Part 4" sections:
- client_family_name: Client's last name
- client_given_name: Client's first name
- client_middle_name: Client's middle name
- client_daytime_phone: Client's daytime telephone
- client_mobile_phone: Client's mobile telephone
- client_email: Client's email address
- client_street_number: Client's street address
- client_apt_ste_flr: Client's apartment/suite/floor
- client_city: Client's city
- client_state: Client's state
- client_zip_code: Client's ZIP code
- client_country: Client's country
- client_uscis_account: Client's USCIS Online Account Number
- client_alien_number: Client's A-Number (Alien Registration Number)

**IMPORTANT INSTRUCTIONS:**
1. Convert ALL dates to MM/DD/YYYY format
2. For sex/gender, return only: M, F, or X
3. If a field is blank/empty in the document, return null (not "N/A")
4. Look at BOTH the passport MRZ and main fields
5. Distinguish between ATTORNEY information (Part 1-2) and CLIENT information (Part 3-4)
6. The client is the person being represented (Joe Jonas in the example)
7. The attorney is the legal representative (Barbara Smith in the example)
8. Return null for any fields not found

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
    """Main processing function for Gradio interface"""
    if passport_file is None and g28_file is None:
        return "Please upload at least one document", None

    try:
        status = "Uploading and processing documents..."

        # Extract all data at once
        extracted_data = extract_all_data(passport_file, g28_file)

        # Convert to dict for JSON display
        result = extracted_data.model_dump()

        status = "✓ Data extraction complete"

        return status, result

    except Exception as e:
        return f"✗ Error: {str(e)}", None


# Gradio interface
with gr.Blocks(title="Alma Assignment") as interface:
    gr.Markdown("# Alma Assignment: Document Processing")
    gr.Markdown(
        "Upload passport and G-28 documents to automatically extract data and populate the form")
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
            with gr.Row():
                process_btn = gr.Button(
                    "Process Documents", variant="primary", size="lg")
                clear_btn = gr.Button(
                    "Clear", variant="secondary", size="lg")

        with gr.Column():
            gr.Markdown("### Results")
            status_output = gr.Textbox(
                label="Status",
                lines=3,
                interactive=False
            )
            data_output = gr.JSON(
                label="Extracted Data"
            )

    process_btn.click(
        fn=process_documents,
        inputs=[passport_input, g28_input],
        outputs=[status_output, data_output]
    )

    clear_btn.click(
        fn=lambda: (None, None, "", None),
        inputs=[],
        outputs=[passport_input, g28_input, status_output, data_output]
    )

    gr.Markdown("""
    ---
    ### Instructions:
    1. Upload a passport document (PDF or image format: JPG, PNG)
    2. Upload a G-28 form (PDF or image format: JPG, PNG)  
    3. Click "Process Documents" to extract data and populate the form
    
    **Note:** The form will be populated but NOT submitted (as per requirements)
    """)

main_app = gr.mount_gradio_app(main_app, interface, path="/")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(main_app, host="0.0.0.0", port=8000)
