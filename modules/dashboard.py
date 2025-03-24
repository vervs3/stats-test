import os
import json
import logging

import logger
import pandas as pd
from datetime import datetime, timedelta, date
from modules.jira_analyzer import JiraAnalyzer
from modules.data_processor import process_issues_data, get_improved_open_statuses

try:
    from config import PROJECT_BUDGET
except ImportError:
    # Если импорт не удался, используем значение по умолчанию
    logger.warning("Could not import PROJECT_BUDGET from config.py, using default value")
    PROJECT_BUDGET = 18000

# Get logger
logger = logging.getLogger(__name__)

# Directory for dashboard data
DASHBOARD_DIR = 'nbss_data'

# Ensure the directory exists
if not os.path.exists(DASHBOARD_DIR):
    os.makedirs(DASHBOARD_DIR)


def collect_daily_data():
    """
    Collect and process daily data for the NBSS Dashboard.
    This should be run once per day at 9:00 AM.
    """
    logger.info("Collecting daily data for NBSS Dashboard")

    try:
        # Initialize Jira analyzer
        analyzer = JiraAnalyzer()

        # Use the CLM filter to get issues
        clm_filter_id = 114473
        clm_query = f'project = CLM AND filter={clm_filter_id}'

        # Get CLM issues
        clm_issues = analyzer.get_issues_by_filter(jql_query=clm_query)
        logger.info(f"Found {len(clm_issues)} CLM issues")

        if not clm_issues:
            logger.error("No CLM issues found")
            return

        # Get related issues
        est_issues, improvement_issues, implementation_issues = analyzer.get_clm_related_issues(clm_issues)

        # Process implementation issues to get time spent
        df = None
        if implementation_issues:
            df = process_issues_data(implementation_issues)

        # Calculate time spent in person-days (assuming 8 hours per day)
        total_time_spent_hours = 0
        if df is not None and not df.empty:
            total_time_spent_hours = df['time_spent_hours'].sum()
        total_time_spent_days = total_time_spent_hours / 8

        # Calculate projected time spent
        # Budget = 23000 person-days, project duration = 2025 year

        # Используйте переменную вместо жестко заданного значения
        budget = PROJECT_BUDGET
        year_start = date(2025, 1, 1)

        # Calculate working days passed (excluding weekends)
        today = date.today()
        days_passed = 0
        current_date = year_start
        while current_date <= today:
            # Check if current date is a weekday (0 = Monday, 6 = Sunday)
            if current_date.weekday() < 5:  # 0-4 are weekdays
                days_passed += 1
            current_date += timedelta(days=1)

        # Calculate working days in the year (excluding weekends)
        total_working_days = 0
        current_date = year_start
        year_end = date(2025, 12, 31)
        while current_date <= year_end:
            # Check if current date is a weekday
            if current_date.weekday() < 5:  # 0-4 are weekdays
                total_working_days += 1
            current_date += timedelta(days=1)

        # Calculate projected time spent
        projected_time_spent = (budget / total_working_days) * days_passed

        # Calculate open tasks data
        open_tasks_data = {}
        if df is not None and not df.empty:
            # Filter for open tasks with time spent
            open_statuses = get_improved_open_statuses(df)
            open_tasks = df[df['status'].isin(open_statuses) & (df['time_spent_hours'] > 0)]

            if not open_tasks.empty:
                # Group by project
                open_tasks_by_project = open_tasks.groupby('project').size().to_dict()
                open_tasks_data = open_tasks_by_project

        # Create data to save
        dashboard_data = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'total_time_spent_hours': float(total_time_spent_hours),
            'total_time_spent_days': float(total_time_spent_days),
            'projected_time_spent_days': float(projected_time_spent),
            'days_passed': days_passed,
            'total_working_days': total_working_days,
            'open_tasks_data': open_tasks_data,
            'clm_issues_count': len(clm_issues),
            'est_issues_count': len(est_issues),
            'improvement_issues_count': len(improvement_issues),
            'implementation_issues_count': len(implementation_issues)
        }

        # Save the data
        save_daily_data(dashboard_data)

        logger.info("Daily data collection complete")
        return dashboard_data

    except Exception as e:
        logger.error(f"Error collecting daily data: {e}", exc_info=True)
        return None


def save_daily_data(data):
    """
    Save the daily dashboard data to a file.

    Args:
        data (dict): Dashboard data to save
    """
    try:
        # Create filename based on date
        date_str = data['date']
        filename = f"{date_str}.json"
        filepath = os.path.join(DASHBOARD_DIR, filename)

        # Save data to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved dashboard data to {filepath}")
    except Exception as e:
        logger.error(f"Error saving dashboard data: {e}", exc_info=True)


def get_dashboard_data():
    """
    Get all dashboard data for the NBSS Dashboard.

    Returns:
        dict: Dashboard data with time series and latest data
    """
    try:
        # Get all data files
        all_data = []
        for filename in os.listdir(DASHBOARD_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(DASHBOARD_DIR, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    all_data.append(data)

        # Sort data by date
        all_data.sort(key=lambda x: x['date'])

        # Get latest data
        latest_data = all_data[-1] if all_data else None

        # Create time series data
        time_series = {
            'dates': [data['date'] for data in all_data],
            'actual_time_spent': [data['total_time_spent_days'] for data in all_data],
            'projected_time_spent': [data['projected_time_spent_days'] for data in all_data]
        }

        # Get latest open tasks data
        open_tasks_data = latest_data['open_tasks_data'] if latest_data else {}

        return {
            'time_series': time_series,
            'latest_data': latest_data,
            'open_tasks_data': open_tasks_data
        }
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}", exc_info=True)
        return {
            'time_series': {'dates': [], 'actual_time_spent': [], 'projected_time_spent': []},
            'latest_data': None,
            'open_tasks_data': {}
        }