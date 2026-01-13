from playwright.sync_api import sync_playwright
from browserbase import Browserbase
from models import FormA28Data
from dotenv import load_dotenv
from google import genai
import os
import json

# Load environment variables
load_dotenv()


class FormPopulator:
    """Handles form population using Browserbase remote browser"""

    def __init__(self, form_url: str = None):
        self.form_url = form_url or "https://mendrika-alma.github.io/form-submission/"

        # Get credentials from environment
        api_key = os.environ.get("BROWSERBASE_API_KEY")
        project_id = os.environ.get("BROWSERBASE_PROJECT_ID")
        gemini_key = os.environ.get("GOOGLE_AI_API_KEY")

        if not api_key or not project_id:
            raise ValueError(
                "BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID must be set in .env")

        self.bb = Browserbase(api_key=api_key)
        self.project_id = project_id
        self.gemini = genai.Client(api_key=gemini_key)

    def populate_form(self, data: FormA28Data) -> dict:
        """
        Populate the web form using Browserbase

        Args:
            data: FormA28Data object with extracted information

        Returns:
            dict: {"screenshot": path, "session_url": url, "session_id": id}
        """
        try:
            # Create Browserbase session
            print("Creating Browserbase session...")
            session = self.bb.sessions.create(project_id=self.project_id)

            session_id = session.id
            # Browserbase session viewing URL
            session_url = f"https://www.browserbase.com/sessions/{session_id}"

            print(f"Session ID: {session_id}")
            print(f"View session: {session_url}")

            with sync_playwright() as playwright:
                # Connect to remote browser
                print("Connecting to remote browser...")
                browser = playwright.chromium.connect_over_cdp(
                    session.connect_url)
                context = browser.contexts[0]
                page = context.pages[0]

                # Set timeout
                page.set_default_timeout(30000)

                # Navigate to form
                print(f"Navigating to {self.form_url}...")
                page.goto(self.form_url, wait_until="networkidle")
                page.wait_for_timeout(2000)

                # Get form HTML
                print("Analyzing form structure...")
                form_html = page.content()

                # Use LLM to match fields
                print("Generating field mappings...")
                fill_commands = self._generate_fill_commands(form_html, data)

                # Fill all fields
                print(f"Filling {len(fill_commands)} fields...")
                filled = self._execute_fill_commands(page, fill_commands)

                # Wait for form to update
                page.wait_for_timeout(1000)

                # Take screenshot
                print("Taking screenshot...")
                screenshot_path = "/tmp/populated_form.png"
                page.screenshot(path=screenshot_path, full_page=True)

                print(f"Form populated successfully! ({filled} fields filled)")
                print(f"\nView live session: {session_url}")

                # Note: Don't close browser so user can inspect
                # browser.close()

                return {
                    "screenshot": screenshot_path,
                    "session_url": session_url,
                    "session_id": session_id,
                    "fields_filled": filled
                }

        except Exception as e:
            print(f"Form population error: {str(e)}")
            raise

    def _generate_fill_commands(self, form_html: str, data: FormA28Data) -> list:
        """Use LLM to generate CSS selectors for form fields"""

        # Get non-null data
        data_dict = {k: v for k, v in data.model_dump().items()
                     if v is not None}

        # Save HTML for debugging
        with open("/tmp/form_debug.html", "w") as f:
            f.write(form_html)
        print(
            f"  Saved form HTML to /tmp/form_debug.html ({len(form_html)} chars)")

        prompt = f"""You are a form-filling expert. Analyze this HTML form and generate Playwright commands to fill it with the provided data.

HTML Form:
{form_html[:25000]}

Data to Fill (field_name: value):
{json.dumps(data_dict, indent=2)}

YOUR TASK:
1. Analyze the HTML form above to find all input, select, and textarea elements
2. For each field in the data, find the best matching form element by examining:
   - Element "id" attributes
   - Element "name" attributes  
   - Element "placeholder" text
   - Nearby <label> text
   - Element "aria-label" attributes
   - Semantic meaning of the field

3. Match data fields to form fields intelligently:
   - "attorney_family_name" → look for attorney/lawyer/representative last name fields
   - "attorney_given_name" → look for attorney/lawyer/representative first name fields
   - "attorney_email" → look for attorney/lawyer/representative email fields
   - "client_family_name" → look for client/applicant/beneficiary last name fields
   - "client_given_name" → look for client/applicant/beneficiary first name fields
   - etc. (use semantic understanding for all fields)

4. Generate commands with the appropriate action type:
   - "action": "fill" for <input type="text">, <input type="email">, <input type="tel">, <textarea>
   - "action": "select" for <select> dropdowns (use the VALUE attribute, e.g., "CA" not "California")
   - "action": "check" for <input type="checkbox"> (when field value suggests it should be checked)

5. Generate SPECIFIC CSS selectors that EXIST in the HTML:
   - Prefer selectors by "id": input[id='firstName']
   - Fallback to "name": input[name='first_name']
   - Use other attributes if needed: input[placeholder='First Name']

CRITICAL RULES:
- Analyze the ACTUAL HTML provided - don't assume field names
- Only generate commands for fields that EXIST in the HTML
- If a field can't be matched, skip it (don't generate a command)
- For checkboxes, determine if they should be checked based on the field value
- For selects, use the VALUE attribute from the <option> tags
- Match ALL {len(data_dict)} data fields if possible

Return ONLY a valid JSON array:
[
  {{"action": "fill", "selector": "input[id='actualFieldId']", "value": "Smith"}},
  {{"action": "select", "selector": "select[name='state']", "value": "CA"}},
  {{"action": "check", "selector": "input[id='checkboxId']"}},
  ...
]"""

        response = self.gemini.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )

        # Save LLM response for debugging
        with open("/tmp/llm_response.json", "w") as f:
            f.write(response.text)
        print(f"  Saved LLM response to /tmp/llm_response.json")

        try:
            commands = json.loads(response.text)
            print(
                f"  Gemini generated {len(commands)} fill commands (expected {len(data_dict)})")

            # Print first few commands for debugging
            if commands:
                print(f"  Sample commands:")
                for cmd in commands[:5]:
                    action_type = cmd.get('action', 'fill')
                    print(
                        f"    - [{action_type.upper()}] {cmd.get('selector')} = {cmd.get('value')}")

            return commands
        except Exception as e:
            print(f"  LLM response parsing failed: {str(e)}")
            print(f"  Response: {response.text[:500]}")
            return []

    def _execute_fill_commands(self, page, commands: list) -> int:
        """Execute fill commands and return count of filled fields"""
        filled = 0

        for cmd in commands:
            action = cmd.get("action", "fill")
            selector = cmd.get("selector")
            value = cmd.get("value")

            if not selector:
                continue

            try:
                if page.locator(selector).count() > 0:
                    if action == "select":
                        # Handle select dropdowns
                        page.select_option(selector, value, timeout=5000)
                        print(f"  ✓ [SELECT] {selector} = {value}")
                        filled += 1
                    elif action == "check":
                        # Handle checkboxes
                        page.check(selector, timeout=5000)
                        print(f"  ✓ [CHECK] {selector}")
                        filled += 1
                    else:
                        # Handle input/textarea (fill)
                        if value is not None:
                            page.fill(selector, str(value), timeout=5000)
                            print(f"  ✓ [FILL] {selector} = {value}")
                            filled += 1
                else:
                    print(f"  ⊘ {selector} (not found)")
            except Exception as e:
                print(f"  ✗ {selector}: {str(e)}")

        return filled
