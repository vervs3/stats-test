import re
import logging

# Get logger
logger = logging.getLogger(__name__)

def format_timestamp_for_display(timestamp):
    """
    Convert timestamp format '20250317_193204' to
    a more readable format '2025-03-17_19-32'
    """
    if not timestamp or not isinstance(timestamp, str):
        return timestamp

    # Check that timestamp matches expected format
    pattern = r'^\d{8}_\d{6}$'
    if not re.match(pattern, timestamp):
        return timestamp

    try:
        # Split timestamp into components
        date_part = timestamp[:8]
        time_part = timestamp[9:]

        # Format date
        year = date_part[:4]
        month = date_part[4:6]
        day = date_part[6:8]

        # Format time
        hour = time_part[:2]
        minute = time_part[2:4]

        # Return formatted date and time
        return f"{year}-{month}-{day}_{hour}-{minute}"
    except Exception as e:
        logger.error(f"Error formatting timestamp: {e}")
        return timestamp