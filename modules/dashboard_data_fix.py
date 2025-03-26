import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta, date


# Use this to generate initial data for an empty dashboard
def generate_initial_dashboard_data():
    """
    Generate initial data for the dashboard when no real data exists.
    This ensures the dashboard is never empty.
    """
    logger = logging.getLogger(__name__)
    logger.info("Generating initial dashboard data")

    try:
        # Create data directory if it doesn't exist
        DASHBOARD_DIR = 'nbss_data'
        if not os.path.exists(DASHBOARD_DIR):
            os.makedirs(DASHBOARD_DIR)

        # Generate data for today
        today = datetime.now()
        date_str = today.strftime('%Y%m%d')

        # Create folder structure
        folder_path = os.path.join(DASHBOARD_DIR, date_str)
        data_dir = os.path.join(folder_path, 'data')

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        # Create basic placeholder dummy data

        # 1. Empty raw_issues structure with proper format
        raw_data = {
            "filtered_issues": [],
            "all_implementation_issues": [],
            "additional_data": {
                "clm_issues": [],
                "est_issues": [],
                "improvement_issues": []
            }
        }

        raw_issues_path = os.path.join(folder_path, 'raw_issues.json')
        with open(raw_issues_path, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)

        # 2. Empty clm_issue_keys data
        keys_data = {
            'clm_issue_keys': [],
            'est_issue_keys': [],
            'improvement_issue_keys': [],
            'implementation_issue_keys': [],
            'filtered_issue_keys': [],
            'open_tasks_issue_keys': [],
            'project_issue_mapping': {}
        }

        clm_keys_path = os.path.join(data_dir, 'clm_issue_keys.json')
        with open(clm_keys_path, 'w', encoding='utf-8') as f:
            json.dump(keys_data, f, indent=4, ensure_ascii=False)

        # 3. Sample dashboard data
        dashboard_data = {
            'date': today.strftime('%Y-%m-%d'),
            'timestamp': date_str,
            'total_time_spent_hours': 800.0,  # Sample value: 100 days * 8 hours
            'total_time_spent_days': 100.0,  # Sample value: 100 days
            'projected_time_spent_days': 110.0,  # Slightly higher than actual
            'days_passed': 85,  # Sample value
            'total_working_days': 252,  # Typical working days in a year
            'open_tasks_data': {  # Sample open tasks data
                'NBSSPORTAL': 15,
                'UDB': 10,
                'CHM': 7,
                'NUS': 5,
                'ATS': 3
            },
            'clm_issues_count': 5,
            'est_issues_count': 10,
            'improvement_issues_count': 8,
            'implementation_issues_count': 50,
            'refresh_interval': 3600  # 1 hour refresh
        }

        # Save summary file
        summary_path = os.path.join(folder_path, 'summary.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(dashboard_data, f, indent=2, ensure_ascii=False)

        # Generate sample past data for time series (last 7 days)
        for i in range(1, 8):
            past_date = today - timedelta(days=i)
            past_date_str = past_date.strftime('%Y%m%d')
            past_folder = os.path.join(DASHBOARD_DIR, past_date_str)

            # Only create if folder doesn't exist
            if not os.path.exists(past_folder):
                os.makedirs(past_folder)

                # Create decreasing values for past dates
                past_data = dashboard_data.copy()
                past_data['date'] = past_date.strftime('%Y-%m-%d')
                past_data['timestamp'] = past_date_str
                past_data['total_time_spent_days'] = 100.0 - i * 5  # Decrease by 5 each day going back
                past_data['total_time_spent_hours'] = past_data['total_time_spent_days'] * 8
                past_data['projected_time_spent_days'] = past_data['total_time_spent_days'] * 1.1

                # Save past summary file
                past_summary_path = os.path.join(past_folder, 'summary.json')
                with open(past_summary_path, 'w', encoding='utf-8') as f:
                    json.dump(past_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Generated initial dashboard data for {date_str} and 7 previous days")
        return True

    except Exception as e:
        logger.error(f"Error generating initial dashboard data: {e}", exc_info=True)
        return False


# Execute this function to generate initial data
# This can be called from app.py on startup to ensure dashboard is never empty
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_initial_dashboard_data()