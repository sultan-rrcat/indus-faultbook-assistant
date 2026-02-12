import dateparser
import re
import config
import logging

# --- Logging Setup ---
config.setup_logging()
logger = logging.getLogger(__name__)
logger.info("📝 Logging has been successfully set up.")

def normalize_dates_in_text(user_message, replace=True, date_format="%Y-%m-%d"):
    """
    Normalizes all detected date strings in the text to a consistent format.
    If `replace` is True, replaces the original date strings with normalized dates.
    Else, appends normalized dates in brackets after the detected dates.
    """
    logger.info(f"💬 Received User Message: {user_message}")
    # Regex patterns for common date formats
    date_patterns = [
        r"\b(?:\d{1,2}[/-])?\d{1,2}[/-]\d{2,4}\b",               # 07/15/2015, 15/07/2015
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\.]?\s+\d{1,2},?\s+\d{4}\b", # July 15, 2015
        r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*,?\s+\d{4}\b",      # 15 July 2015
        r"\b\d{4}-\d{2}-\d{2}\b",                               # 2015-07-15
    ]

    combined_pattern = "|".join(date_patterns)
    matches = re.finditer(combined_pattern, user_message, flags=re.IGNORECASE)

    replacements = []
    for match in matches:
        date_str = match.group(0)
        parsed_date = dateparser.parse(date_str)
        if parsed_date:
            normalized_date = parsed_date.strftime(date_format)
            if replace:
                replacements.append((date_str, normalized_date))
            else:
                replacements.append((date_str, f"{date_str} ({normalized_date})"))

    for old, new in replacements:
        user_message = user_message.replace(old, new)
    logger.info(f"📅 User message after date parsing: {user_message}")
    return user_message

# Example usage
if __name__ == "__main__":
    test_text = """
What was the cause of the power supply failure in the TL-3 MPS System on July 15, 2015?
    """

    normalized_text = normalize_dates_in_text(test_text, replace=True)
    print(normalized_text)
