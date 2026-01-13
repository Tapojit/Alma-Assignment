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

        prompt = f"""You are a form-filling expert. Analyze this HTML form and create Playwright fill commands.

HTML Form:
{form_html[:20000]}

Data to Fill (field_name: value):
{json.dumps(data_dict, indent=2)}

CRITICAL INSTRUCTIONS:
1. Find the ACTUAL input/select/textarea elements in the HTML
2. For each data field, identify the matching form field by:
   - Looking at input "name" attributes
   - Looking at input "id" attributes  
   - Looking at input "placeholder" text
   - Looking at nearby <label> text
   - Looking at data-* attributes

3. Field matching hints:
   - "attorney_family_name" → look for inputs related to attorney/lawyer/representative last name
   - "attorney_given_name" → attorney first name
   - "client_family_name" → client/applicant/beneficiary last name
   - "client_given_name" → client first name
   - etc.

4. Generate SPECIFIC CSS selectors:
   ✓ GOOD: input[name="attorneyLastName"], input[id="clientFirstName"]
   ✗ BAD: input[name="attorney_family_name"] (if that name doesn't exist in HTML)

5. Return a JSON array of commands. Each command MUST have:
   - "selector": Valid CSS selector that EXISTS in the HTML
   - "value": The value to fill

IMPORTANT: Only include fields you can ACTUALLY FIND in the HTML above.

Return ONLY a valid JSON array, no markdown, no explanation:
[
  {{"selector": "input[name='actualFieldName']", "value": "Smith"}},
  {{"selector": "input[id='anotherRealField']", "value": "Barbara"}}
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
            print(f"  Gemini generated {len(commands)} fill commands")

            # Print first few commands for debugging
            if commands:
                print(f"  Sample commands:")
                for cmd in commands[:3]:
                    print(f"    - {cmd.get('selector')} = {cmd.get('value')}")

            return commands
        except Exception as e:
            print(f"  LLM response parsing failed: {str(e)}")
            print(f"  Response: {response.text[:500]}")
            return []

    def _execute_fill_commands(self, page, commands: list) -> int:
        """Execute fill commands and return count of filled fields"""
        filled = 0

        for cmd in commands:
            selector = cmd.get("selector")
            value = cmd.get("value")

            if not selector or value is None:
                continue

            try:
                if page.locator(selector).count() > 0:
                    page.fill(selector, str(value), timeout=5000)
                    print(f"  ✓ {selector} = {value}")
                    filled += 1
                else:
                    print(f"  ⊘ {selector} (not found)")
            except Exception as e:
                print(f"  ✗ {selector}: {str(e)}")

        return filled
