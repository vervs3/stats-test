import os
import logging
import pandas as pd
from io import BytesIO

# Get logger
logger = logging.getLogger(__name__)


def read_excel_from_binary(file_binary):
    """
    Read Excel file from binary data

    Args:
        file_binary (bytes): Excel file binary data

    Returns:
        pandas.DataFrame: DataFrame with Excel data or None if error
    """
    try:
        # Read Excel file from binary data
        df = pd.read_excel(BytesIO(file_binary))
        return df
    except Exception as e:
        logger.error(f"Error reading Excel file: {e}", exc_info=True)
        return None


def save_subsystem_mapping(file_binary):
    """
    Save subsystem mapping from uploaded Excel file

    Args:
        file_binary (bytes): Excel file binary data

    Returns:
        bool: True if successful, False if error
    """
    try:
        # Read Excel file
        df = read_excel_from_binary(file_binary)
        if df is None:
            return False

        # Create data directory if it doesn't exist
        data_dir = os.path.join('data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        # Save Excel file
        excel_file = os.path.join(data_dir, 'subsystem_mapping.xlsx')
        df.to_excel(excel_file, index=False)

        logger.info(f"Saved subsystem mapping to {excel_file}")

        return True
    except Exception as e:
        logger.error(f"Error saving subsystem mapping: {e}", exc_info=True)
        return False


def get_subsystems_for_product(product_code='DIGITAL_BSS'):
    """
    Get subsystems for the given product code

    Args:
        product_code (str): Product code

    Returns:
        list: List of subsystems
    """
    try:
        # Path to the Excel file
        excel_file = os.path.join('data', 'subsystem_mapping.xlsx')

        if not os.path.exists(excel_file):
            logger.warning(f"Subsystem mapping file not found: {excel_file}")
            return []

        # Read Excel file
        df = pd.read_excel(excel_file)

        # Filter for the given product code
        df_filtered = df[df['ProdCode'] == product_code]

        # Get all subsystems (SubCode values)
        subsystems = df_filtered['SubCode'].unique().tolist()

        return subsystems
    except Exception as e:
        logger.error(f"Error getting subsystems: {e}", exc_info=True)
        return []