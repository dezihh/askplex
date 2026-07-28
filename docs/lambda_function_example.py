# -*- coding: utf-8 -*-
"""
Example: Modified lambda_function.py snippet

Shows the critical encoding fix for JSON loading.

Location: lambda/lambda_function.py (LocalizationInterceptor class)
"""

import json
import logging
from ask_sdk_core.dispatch_decorator import (
    AbstractRequestInterceptor, AbstractResponseInterceptor)


class LocalizationInterceptor(AbstractRequestInterceptor):
    """
    This interceptor loads localized response strings.

    CRITICAL FIX: Add encoding='utf-8' to file opening for cross-platform
    compatibility. This ensures Unicode/Umlaute are properly loaded on
    Windows, Linux, and AWS Lambda.
    """

    def process(self, handler_input):
        """Load localized strings based on request locale."""
        locale = handler_input.request_envelope.request.locale
        logger.debug(f"Loading locale: {locale}")

        # ========================================================================
        # ORIGINAL (PROBLEMATIC):
        # ========================================================================
        # with open("askplex/language_strings.json") as language_prompts:
        #     language_data = json.load(language_prompts)

        # PROBLEM: On Windows with non-UTF-8 system encoding, this can fail
        # or mangle Umlaute characters. Example:
        # - "Entschuldigung" might become "Entschuldigung" (corrupted)
        # - "Ärzte" might become "?rzte"

        # ========================================================================
        # FIXED (RECOMMENDED):
        # ========================================================================

        try:
            # Explicitly specify UTF-8 encoding
            with open("askplex/language_strings.json", encoding='utf-8') as language_prompts:
                language_data = json.load(language_prompts)
        except FileNotFoundError:
            logger.error("language_strings.json not found!")
            logger.info("Ensuring file is in: lambda/askplex/language_strings.json")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in language_strings.json: {e}")
            raise
        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error in language_strings.json: {e}")
            logger.info("File may not be valid UTF-8. Check encoding.")
            raise

        # Try to get exact locale match
        if locale in language_data:
            data = language_data[locale]
            logger.debug(f"Using exact locale: {locale}")
        else:
            # Fallback to language family (e.g., "de" from "de-DE")
            language_code = locale.split('-')[0]
            if language_code in language_data:
                data = language_data[language_code]
                logger.debug(f"Fallback locale: {language_code}")
            else:
                # Final fallback to English
                data = language_data.get('en', {})
                logger.warning(f"No locale data for {locale}, falling back to English")

        # Store in request attributes for use in handlers
        handler_input.attributes_manager.request_attributes["_"] = data
        logger.debug(f"Localization loaded: {len(data)} strings")


# ============================================================================
# VERIFICATION: Check that language_strings.json is valid UTF-8
# ============================================================================

# Add this to your Lambda or test locally to verify encoding:

def verify_language_strings_encoding():
    """
    Verify that language_strings.json is properly UTF-8 encoded.

    Call this once during skill setup to catch encoding issues early.
    """
    import io

    logger.info("Verifying language_strings.json encoding...")

    try:
        # Try to read as UTF-8
        with open("askplex/language_strings.json", encoding='utf-8') as f:
            content = f.read()
            data = json.loads(content)

        # Check for German locale
        if 'de-DE' in data:
            german_strings = data['de-DE']

            # Verify Umlaute are present
            test_strings = [
                ('SKILL_WELCOME', 'Willkommen'),
                ('SKILL_HELP', 'Künstlern'),  # Contains Umlaut ü
                ('PMS_PLAYING', 'Wiedergabe'),
            ]

            for key, expected_substring in test_strings:
                if key in german_strings:
                    value = german_strings[key]
                    if expected_substring.lower() in value.lower():
                        logger.info(f"✓ {key}: OK")
                    else:
                        logger.warning(f"✗ {key}: Expected to contain '{expected_substring}'")
                else:
                    logger.warning(f"✗ {key}: Missing key")

        logger.info("✓ language_strings.json encoding verified successfully")
        return True

    except UnicodeDecodeError as e:
        logger.error(f"✗ UTF-8 decode error: {e}")
        logger.error("File is not valid UTF-8. Please re-encode language_strings.json")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"✗ Invalid JSON: {e}")
        return False
    except FileNotFoundError:
        logger.error("✗ language_strings.json not found")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        return False


# ============================================================================
# INTEGRATION: Call verification in lambda_handler setup
# ============================================================================

def create_skill_builder():
    """Create and configure the skill builder."""

    # Verify encoding before building skill
    if not verify_language_strings_encoding():
        logger.error("language_strings.json encoding issue detected!")
        # In production, you might want to raise or handle gracefully

    # Create skill builder
    sb = CustomSkillBuilder(persistence_adapter=dynamodb_adapter)

    # Add localization interceptor with UTF-8 support
    sb.add_global_request_interceptor(LocalizationInterceptor())

    # ... rest of skill builder setup ...

    return sb


# ============================================================================
# BEST PRACTICE: UTF-8 Handling Checklist
# ============================================================================

"""
When setting up your askplex skill, ensure:

✓ lambda_function.py:
  - LocalizationInterceptor has encoding='utf-8'

✓ language_strings.json:
  - File encoding is UTF-8 (not Latin-1, CP1252, etc.)
  - Verify in file editor: View > Encoding should show "UTF-8"

✓ controller.py:
  - Imports unicode_normalizer.py
  - Uses SearchStrategy for all artist/song/playlist searches

✓ Testing:
  - Run test_unicode_normalizer.py before deployment
  - Test locally with German artist names containing Umlaute

✓ AWS Lambda:
  - Ensure Lambda runtime supports UTF-8 (all Python 3.x do)
  - Check CloudWatch logs for encoding issues

✓ Plex Server:
  - Verify Plex database properly stores artist names with Umlaute
  - Check Plex Web UI: Settings > Library > Metadata agents
"""

