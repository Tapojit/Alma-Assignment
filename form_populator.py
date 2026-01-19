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

                # Show summary
                print(f"\nFilling Summary:")
                print(f"  Total data fields: {len(data.model_dump())}")
                print(f"  Commands generated: {len(fill_commands)}")
                print(f"  Successfully filled: {filled}")
                if len(fill_commands) < len([v for v in data.model_dump().values() if v is not None]):
                    print(f"  ⚠️  Some fields may not have been matched!")

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

        # Print data being filled
        print(f"  Data fields to fill ({len(data_dict)} total):")
        for key, value in list(data_dict.items())[:10]:  # Show first 10
            print(f"    - {key}: {str(value)[:50]}")
        if len(data_dict) > 10:
            print(f"    ... and {len(data_dict) - 10} more fields")

        # DETERMINISTIC MAPPING - Try common patterns first
        commands = self._generate_deterministic_commands(form_html, data_dict)
        print(f"  Deterministic matching found {len(commands)} field mappings")

        # Use LLM for remaining fields
        mapped_fields = {cmd.get('selector') for cmd in commands}
        remaining_data = {k: v for k, v in data_dict.items()
                          if not any(str(v) in str(cmd.get('value', '')) for cmd in commands)}

        if remaining_data:
            print(f"  Using LLM for {len(remaining_data)} remaining fields...")
            llm_commands = self._generate_llm_commands(
                form_html, remaining_data)

            # Filter out LLM commands targeting selectors already filled
            filled_selectors = {cmd.get('selector') for cmd in commands}
            llm_commands_filtered = [
                cmd for cmd in llm_commands
                if cmd.get('selector') not in filled_selectors
            ]

            if len(llm_commands) != len(llm_commands_filtered):
                print(
                    f"  Filtered {len(llm_commands) - len(llm_commands_filtered)} LLM commands (duplicate selectors)")

            commands.extend(llm_commands_filtered)

        print(f"  Total commands generated: {len(commands)}")
        return commands

    def _generate_deterministic_commands(self, form_html: str, data_dict: dict) -> list:
        """Generate commands using deterministic field ID patterns"""
        commands = []

        # Common field ID patterns
        field_mappings = {
            # Attorney fields
            'attorney_family_name': ['family-name', 'last-name', 'surname'],
            'attorney_given_name': ['given-name', 'first-name', 'firstname'],
            'attorney_middle_name': ['middle-name', 'middlename'],
            'attorney_street_number': ['street-number', 'street', 'address'],
            'attorney_city': ['city', 'town'],
            'attorney_state': ['state', 'province'],
            'attorney_zip_code': ['zip', 'postal-code', 'zipcode'],
            'attorney_country': ['country'],
            'attorney_daytime_phone': ['daytime-phone', 'phone', 'telephone'],
            'attorney_mobile_phone': ['mobile-phone', 'mobile', 'cell'],
            'attorney_email': ['email', 'e-mail'],
            'attorney_licensing_authority': ['licensing-authority', 'bar-authority'],
            'attorney_bar_number': ['bar-number', 'bar-id'],
            'attorney_law_firm': ['law-firm', 'firm', 'organization'],
            'attorney_subject_to_restrictions': ['not-subject', 'am-subject'],

            # Passport/Beneficiary fields
            'beneficiary_last_name': ['passport-surname', 'last-name'],
            'beneficiary_first_name': ['passport-given-names', 'first-name'],
            'passport_number': ['passport-number', 'passport-no'],
            'passport_country_of_issue': ['passport-country', 'country-of-issue'],
            'passport_nationality': ['passport-nationality', 'nationality'],
            'beneficiary_date_of_birth': ['passport-dob', 'date-of-birth', 'dob'],
            'beneficiary_place_of_birth': ['passport-pob', 'place-of-birth', 'birthplace'],
            'beneficiary_sex': ['passport-sex', 'sex', 'gender'],
            'passport_date_of_issue': ['passport-issue-date', 'date-of-issue'],
            'passport_date_of_expiration': ['passport-expiry-date', 'date-of-expiration'],
        }

        for data_field, value in data_dict.items():
            if data_field in field_mappings:
                for id_pattern in field_mappings[data_field]:
                    # Special handling for attorney_subject_to_restrictions
                    if data_field == 'attorney_subject_to_restrictions':
                        # Check which checkbox to select based on value
                        if 'not' in str(value).lower() and id_pattern == 'not-subject':
                            selector = f"input[id='{id_pattern}']"
                            commands.append({
                                "action": "check",
                                "selector": selector,
                                "value": value
                            })
                            print(
                                f"    ✓ Matched {data_field} → {id_pattern} (check - contains 'not')")
                            break
                        elif 'am' in str(value).lower() and 'not' not in str(value).lower() and id_pattern == 'am-subject':
                            selector = f"input[id='{id_pattern}']"
                            commands.append({
                                "action": "check",
                                "selector": selector,
                                "value": value
                            })
                            print(
                                f"    ✓ Matched {data_field} → {id_pattern} (check - 'am' without 'not')")
                            break
                        continue

                    # Check if this ID exists in the HTML
                    if f'id="{id_pattern}"' in form_html or f"id='{id_pattern}'" in form_html:
                        # Determine element type and action
                        if f'<select id="{id_pattern}"' in form_html or f"<select id='{id_pattern}'" in form_html:
                            action = "select"
                            selector = f"select[id='{id_pattern}']"
                        elif 'type="date"' in form_html and (f'id="{id_pattern}"' in form_html or f"id='{id_pattern}'" in form_html):
                            action = "date"
                            selector = f"input[id='{id_pattern}']"
                        elif 'type="checkbox"' in form_html and (f'id="{id_pattern}"' in form_html or f"id='{id_pattern}'" in form_html):
                            action = "check"
                            selector = f"input[id='{id_pattern}']"
                        else:
                            action = "fill"
                            selector = f"input[id='{id_pattern}']"

                        commands.append({
                            "action": action,
                            "selector": selector,
                            "value": value
                        })
                        print(
                            f"    ✓ Matched {data_field} → {id_pattern} ({action})")
                        break

        # Auto-check attorney-eligible if attorney data exists
        if any(k.startswith('attorney_') for k in data_dict.keys()):
            if 'id="attorney-eligible"' in form_html or "id='attorney-eligible'" in form_html:
                commands.append({
                    "action": "check",
                    "selector": "input[id='attorney-eligible']",
                    "value": "attorney"
                })
                print(f"    ✓ Auto-checking attorney-eligible (attorney data present)")

        return commands

    def _generate_llm_commands(self, form_html: str, remaining_data: dict) -> list:
        """Use LLM for fields that weren't deterministically matched"""
        if not remaining_data:
            return []

        prompt = f"""You are a form-filling expert. Analyze this HTML form and generate Playwright commands to fill it with the provided data.

HTML Form:
{form_html[:25000]}

Data to Fill (field_name: value):
{json.dumps(remaining_data, indent=2)}

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
   - "beneficiary_date_of_birth" → look for date of birth fields (type="date")
   - "passport_date_of_issue" → look for date of issue fields (type="date")
   - "passport_date_of_expiration" → look for date of expiration fields (type="date")
   - "beneficiary_sex" → look for sex/gender dropdown fields (F/M/X values)
   - "beneficiary_place_of_birth" → look for place of birth text fields (cities like CANBERRA)
   - "passport_nationality" → look for nationality text fields (like AUSTRALIAN, AMERICAN, etc.)
   - "passport_country_of_issue" → look for country of issue fields (like AUSTRALIA, USA, etc.)
   - etc. (use semantic understanding for all fields)

IMPORTANT: Pay special attention to these commonly missed fields:
- Nationality (often has id like "passport-nationality" or "nationality")
- Place of Birth (often has id like "passport-pob", "place-of-birth", or "birthplace")
- All date fields (Date of Birth, Date of Issue, Date of Expiration)
- Sex/Gender dropdowns (often has id like "passport-sex" or "sex")

4. Generate commands with the appropriate action type:
   - "action": "fill" for <input type="text">, <input type="email">, <input type="tel">, <textarea>
   - "action": "select" for <select> dropdowns (use the VALUE attribute, e.g., "CA" not "California")
   - "action": "check" for <input type="checkbox"> (when field value suggests it should be checked)
   - "action": "date" for <input type="date"> (convert date from MM/DD/YYYY to YYYY-MM-DD format)

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
- For date inputs, use "action": "date" and keep the value in MM/DD/YYYY format (conversion happens automatically)
- Pay special attention to date fields (Date of Birth, Date of Issue, Date of Expiration) - these are <input type="date">
- Pay special attention to dropdown fields (Sex, State, etc.) - these are <select> elements
- Match ALL {len(remaining_data)} data fields if possible

Return ONLY a valid JSON array:
[
  {{"action": "fill", "selector": "input[id='actualFieldId']", "value": "Smith"}},
  {{"action": "select", "selector": "select[name='state']", "value": "CA"}},
  {{"action": "check", "selector": "input[id='checkboxId']"}},
  {{"action": "date", "selector": "input[type='date'][id='dateOfBirth']", "value": "05/04/1991"}},
  ...
]"""

        response = self.gemini.models.generate_content(
            model="gemini-3-pro-preview",
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
                f"  Gemini generated {len(commands)} LLM commands (expected {len(remaining_data)})")

            # Print first few commands for debugging
            if commands:
                print(f"  Sample LLM commands:")
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
                        # Handle checkboxes - use click instead of check to avoid timeout
                        page.locator(selector).click(timeout=5000, force=True)
                        print(f"  ✓ [CHECK] {selector}")
                        filled += 1
                    elif action == "date":
                        # Handle date inputs - convert MM/DD/YYYY to YYYY-MM-DD
                        if value:
                            converted_date = self._convert_date_format(value)
                            page.fill(selector, converted_date, timeout=5000)
                            print(
                                f"  ✓ [DATE] {selector} = {converted_date} (from {value})")
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

    def _convert_date_format(self, date_str: str) -> str:
        """Convert date from MM/DD/YYYY to YYYY-MM-DD format"""
        try:
            # Handle MM/DD/YYYY format
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    month, day, year = parts
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            # Already in YYYY-MM-DD format
            return date_str
        except Exception as e:
            print(
                f"  Warning: Date conversion failed for '{date_str}': {str(e)}")
            return date_str
