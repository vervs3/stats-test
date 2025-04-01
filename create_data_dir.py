import os
import pandas as pd


def create_data_directory():
    """Create data directory and sample subsystem mapping file"""
    # Create data directory if it doesn't exist
    data_dir = os.path.join('data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"Created data directory: {data_dir}")

    # Create sample subsystem mapping file
    excel_file = os.path.join(data_dir, 'subsystem_mapping.xlsx')

    # Sample data - you should replace this with actual data
    data = {
        'ProdCode': [
            'DIGITAL_BSS', 'DIGITAL_BSS', 'DIGITAL_BSS', 'DIGITAL_BSS', 'DIGITAL_BSS',
            'DIGITAL_BSS', 'DIGITAL_BSS', 'DIGITAL_BSS', 'DIGITAL_BSS', 'DIGITAL_BSS'
        ],
        'SubCode': [
            'NBSS_CORE', 'UDB', 'CHM', 'NUS', 'ATS',
            'SSO', 'DMS', 'NBSSPORTAL', 'TUDS', 'LIS'
        ]
    }

    # Create DataFrame
    df = pd.DataFrame(data)

    # Save to Excel
    df.to_excel(excel_file, index=False)

    print(f"Created sample subsystem mapping file: {excel_file}")


if __name__ == "__main__":
    create_data_directory()