"""
Form Population Module using Browserbase
Uses LLM to intelligently match form fields
"""

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

    def populate_form(self, data: FormA28Data) -> str:
        """
        Populate the web form using Browserbase

        Args:
            data: FormA28Data object with extracted information

        Returns:
            str: Path to the screenshot file
        """
        try:
            # Create Browserbase session
            print("Creating Browserbase session...")
            session = self.bb.sessions.create(project_id=self.project_id)

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
                browser.close()

                return screenshot_path

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

        prompt = f"""You are a form-filling expert. Generate Playwright commands for ALL fields.

HTML Form:
{form_html[:25000]}

Data to Fill:
{json.dumps(data_dict, indent=2)}

EXACT FIELD IDS (from the HTML above - use these EXACT selectors):

ATTORNEY SECTION (Part 1):
- attorney_family_name → input[id='family-name']
- attorney_given_name → input[id='given-name']
- attorney_middle_name → input[id='middle-name']
- attorney_street_number → input[id='street-number']
- attorney_city → input[id='city']
- attorney_state → select[id='state'] VALUE (e.g., "CA" not "California")
- attorney_zip_code → input[id='zip']
- attorney_country → input[id='country']
- attorney_daytime_phone → input[id='daytime-phone']
- attorney_mobile_phone → input[id='mobile-phone']
- attorney_email → input[id='email']

ATTORNEY ELIGIBILITY (Part 2):
- attorney_licensing_authority → input[id='licensing-authority']
- attorney_bar_number → input[id='bar-number']
- attorney_law_firm → input[id='law-firm']
- attorney_subject_to_restrictions → CHECK input[id='not-subject'] if value="am not" OR CHECK input[id='am-subject'] if value="am"

BENEFICIARY (Part 3) - USE CLIENT DATA (they're the same person):
- client_family_name → input[id='passport-surname']
- client_given_name → input[id='passport-given-names']

ACTION TYPES:
- "action": "fill" for text/email/tel inputs
- "action": "select" for dropdowns (use VALUE like "CA", "M", "F")
- "action": "check" for checkboxes

CRITICAL RULES:
1. Generate commands for ALL {len(data_dict)} fields
2. For checkboxes, use "action": "check" (no value needed)
3. For selects, use VALUE not display text ("CA" not "California")
4. Use the EXACT selectors listed above

Return ONLY valid JSON:
[
  {{"action": "fill", "selector": "input[id='family-name']", "value": "Smith"}},
  {{"action": "fill", "selector": "input[id='daytime-phone']", "value": "+1234567890"}},
  {{"action": "select", "selector": "select[id='state']", "value": "CA"}},
  {{"action": "check", "selector": "input[id='not-subject']"}},
  {{"action": "fill", "selector": "input[id='passport-surname']", "value": "Jonas"}},
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
