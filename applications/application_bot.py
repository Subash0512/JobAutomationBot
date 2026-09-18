from pathlib import Path

from playwright.sync_api import sync_playwright


class ApplicationBot:
    def __init__(self, headless=False):
        self.headless = headless

    def _fill_text_field(self, page, selectors, value):
        for selector in selectors:
            locator = page.locator(selector)

            if locator.count() == 0:
                continue

            field = locator.first

            try:
                field.fill(value)
                return True
            except Exception:
                continue

        return False

    def _fill_profile(self, page, profile):
        """
        Fill common application fields using labels,
        names, placeholders, and autocomplete attributes.
        """

        results = {}

        results["name"] = self._fill_text_field(
            page,
            [
                'input[autocomplete="name"]',
                'input[name*="name" i]',
                'input[id*="name" i]',
                'input[placeholder*="name" i]',
                'label:has-text("Full Name") + input',
            ],
            profile["full_name"],
        )

        results["email"] = self._fill_text_field(
            page,
            [
                'input[type="email"]',
                'input[autocomplete="email"]',
                'input[name*="email" i]',
                'input[id*="email" i]',
                'input[placeholder*="email" i]',
            ],
            profile["email"],
        )

        results["phone"] = self._fill_text_field(
            page,
            [
                'input[type="tel"]',
                'input[autocomplete="tel"]',
                'input[name*="phone" i]',
                'input[name*="mobile" i]',
                'input[id*="phone" i]',
                'input[id*="mobile" i]',
                'input[placeholder*="phone" i]',
                'input[placeholder*="mobile" i]',
            ],
            profile["phone"],
        )

        results["linkedin"] = self._fill_text_field(
            page,
            [
                'input[name*="linkedin" i]',
                'input[id*="linkedin" i]',
                'input[placeholder*="linkedin" i]',
            ],
            profile.get("linkedin", ""),
        )

        results["github"] = self._fill_text_field(
            page,
            [
                'input[name*="github" i]',
                'input[id*="github" i]',
                'input[placeholder*="github" i]',
            ],
            profile.get("github", ""),
        )

        return results

    def _upload_resume(self, page, resume_path):
        resume = Path(resume_path)

        if not resume.exists():
            raise FileNotFoundError(
                f"Resume not found: {resume}"
            )

        file_inputs = page.locator(
            'input[type="file"]'
        )

        count = file_inputs.count()

        if count == 0:
            return False

        for index in range(count):
            try:
                file_inputs.nth(index).set_input_files(
                    str(resume)
                )
                return True
            except Exception:
                continue

        return False

    def _find_unfilled_required_fields(self, page):
        """
        Find visible required inputs that remain empty.

        We intentionally stop rather than guessing.
        """

        required = page.locator(
            "input[required], textarea[required], select[required]"
        )

        problems = []

        for index in range(required.count()):

            field = required.nth(index)

            try:
                if not field.is_visible():
                    continue
            except Exception:
                continue

            tag = field.evaluate(
                "(el) => el.tagName.toLowerCase()"
            )

            if tag == "select":
                value = field.input_value()

                if not value:
                    problems.append(
                        field.get_attribute("name")
                        or field.get_attribute("id")
                        or "required select"
                    )

            else:
                value = field.input_value()

                if not value.strip():
                    problems.append(
                        field.get_attribute("name")
                        or field.get_attribute("id")
                        or "required field"
                    )

        return problems

    def apply_to_form(self, url, profile, resume_path):
        """
        Fill a direct application form.

        Returns:
            APPLIED
            REVIEW_REQUIRED
            ERROR
        """

        with sync_playwright() as playwright:

            browser = playwright.chromium.launch(
                headless=self.headless
            )

            page = browser.new_page()

            try:
                print()
                print(f"Opening application form: {url}")

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                print(f"Page title: {page.title()}")
                print(f"Current URL: {page.url}")

                # Stop for obvious authentication barriers.
                if "login" in page.url.lower():
                    print("Login required.")
                    return "REVIEW_REQUIRED"

                if "signin" in page.url.lower():
                    print("Sign-in required.")
                    return "REVIEW_REQUIRED"

                # Fill known fields.
                filled = self._fill_profile(
                    page,
                    profile,
                )

                print()
                print("Known fields:")
                for field, result in filled.items():
                    print(
                        f"  {field}: "
                        f"{'filled' if result else 'not found'}"
                    )

                # Upload resume.
                uploaded = self._upload_resume(
                    page,
                    resume_path,
                )

                print(
                    "Resume: "
                    f"{'uploaded' if uploaded else 'file field not found'}"
                )

                # Detect CAPTCHA.
                captcha_count = page.locator(
                    'iframe[src*="captcha" i], '
                    '[class*="captcha" i], '
                    '[id*="captcha" i]'
                ).count()

                if captcha_count > 0:
                    print(
                        "CAPTCHA detected. "
                        "Manual review required."
                    )
                    return "REVIEW_REQUIRED"

                # Detect remaining required fields.
                problems = self._find_unfilled_required_fields(
                    page
                )

                if problems:

                    print()
                    print(
                        "Required fields still need attention:"
                    )

                    for problem in problems:
                        print(f"  - {problem}")

                    print(
                        "Application NOT submitted."
                    )

                    return "REVIEW_REQUIRED"

                # IMPORTANT:
                # We don't click arbitrary submit buttons.
                # This first direct-form version prepares and
                # validates the form, then requires explicit
                # confirmation for submission.
                print()
                print(
                    "Form appears ready for submission."
                )

                input(
                    "Review the form in the browser. "
                    "Press Enter to submit, or close the "
                    "browser/terminate the program to cancel: "
                )

                submit_buttons = page.locator(
                    'button[type="submit"], '
                    'input[type="submit"]'
                )

                if submit_buttons.count() == 0:
                    print(
                        "No submit button found."
                    )
                    return "REVIEW_REQUIRED"

                submit_buttons.first.click()

                page.wait_for_load_state(
                    "domcontentloaded",
                    timeout=30000,
                )

                print()
                print(
                    "Submission action completed."
                )

                return "APPLIED"

            except Exception as error:

                print()
                print(
                    f"Application error: {error}"
                )

                return "ERROR"

            finally:
                browser.close()