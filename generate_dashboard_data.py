import os
import json
import random
import logging
import argparse
from datetime import datetime, timedelta, date

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Directory for dashboard data
DASHBOARD_DIR = 'nbss_data'

# Ensure the directory exists
if not os.path.exists(DASHBOARD_DIR):
    os.makedirs(DASHBOARD_DIR)
    logger.info(f"Created directory: {DASHBOARD_DIR}")


def generate_test_data(days=7):
    """
    Generate synthetic test data for NBSS Dashboard for the specified number of days

    Args:
        days (int): Number of days to generate data for
    """
    logger.info(f"Generating synthetic test data for NBSS Dashboard for {days} days...")

    # Clear existing data
    clear_existing_data()

    # Calculate start date to get requested number of business days
    end_date = date.today()
    calendar_days_needed = int(days * 1.4)  # Adjustment for weekends
    start_date = end_date - timedelta(days=calendar_days_needed)

    # Budget and project parameters
    from config import PROJECT_BUDGET

    # Используйте переменную вместо жестко заданного значения
    budget = PROJECT_BUDGET  # Budget in person-days
    total_working_days = 252  # Approximate working days in a year (excluding weekends and holidays)

    # Generate random projects for open tasks data
    projects = [
        "NBSSPORTAL", "NUS", "UDB", "CHM", "ATS", "SSO", "TUDBRES", "BFAM",
        "SAM", "EPM", "MBUS", "TOMCAT", "TLRDAPIMF", "MCCA", "UFMNX", "LCM",
        "DMS", "FIM", "COMMON", "TLRKCELL", "UZTK", "IOTCMPRTK", "IOTCMP"
    ]

    # For a short period, set a realistic starting point for cumulative time spent
    # We'll pretend that we're already 3 months into the project
    day_offset = 60  # About 3 months of working days
    cumulative_time_spent = (budget / total_working_days) * day_offset * 0.95  # 95% of expected progress

    # Generate data for each day
    test_data = []
    current_date = start_date
    day_count = day_offset
    actual_days_generated = 0

    while current_date <= end_date and actual_days_generated < days:
        # Skip weekends
        if current_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            current_date += timedelta(days=1)
            continue

        day_count += 1
        actual_days_generated += 1

        # Calculate projected time spent based on days passed
        projected_time_spent = (budget / total_working_days) * day_count

        # Calculate actual time spent with some randomness
        # Time spent should generally follow projection but with variations
        daily_work = (budget / total_working_days) * (0.8 + random.random() * 0.4)  # 80-120% of average daily work

        # Some days might have spikes
        if random.random() < 0.1:  # 10% chance of a spike
            daily_work *= 1.5

        cumulative_time_spent += daily_work

        # Generate random open tasks data
        open_tasks_data = {}
        for project in random.sample(projects, min(15, len(projects))):
            # Some projects will have more open tasks than others
            open_tasks_data[project] = random.randint(1, 20)

        # Create data for this day
        date_str = current_date.strftime('%Y-%m-%d')
        daily_data = {
            'date': date_str,
            'total_time_spent_hours': float(cumulative_time_spent * 8),  # Convert to hours
            'total_time_spent_days': float(cumulative_time_spent),
            'projected_time_spent_days': float(projected_time_spent),
            'days_passed': day_count,
            'total_working_days': total_working_days,
            'open_tasks_data': open_tasks_data,
            'clm_issues_count': random.randint(80, 120),
            'est_issues_count': random.randint(150, 200),
            'improvement_issues_count': random.randint(180, 250),
            'implementation_issues_count': random.randint(300, 400)
        }

        # Save to file
        save_daily_data(daily_data)

        # Add to test data list
        test_data.append(daily_data)

        # Move to next day
        current_date += timedelta(days=1)

    logger.info(f"Generated test data for {actual_days_generated} working days")
    logger.info(f"Files saved in {DASHBOARD_DIR} directory")

    return test_data


def generate_real_data(days=7, clm_filter_id=114473):
    """
    Generate real data from JIRA for NBSS Dashboard for the specified number of days

    Args:
        days (int): Number of days to generate data for
        clm_filter_id (int): CLM Filter ID to use
    """
    logger.info(f"Generating real data from JIRA for NBSS Dashboard for {days} days...")
    try:
        # Import necessary modules
        from modules.jira_analyzer import JiraAnalyzer
        from modules.data_processor import process_issues_data, get_improved_open_statuses
    except ImportError:
        logger.error(
            "Could not import necessary modules. Make sure you're running this script from the project root directory.")
        return None

    # Clear existing data
    clear_existing_data()

    try:
        # Initialize Jira analyzer
        analyzer = JiraAnalyzer()

        # Calculate start date to get requested number of business days
        end_date = date.today()
        calendar_days_needed = int(days * 1.4)  # Adjustment for weekends
        start_date = end_date - timedelta(days=calendar_days_needed)

        logger.info(f"Generating data from {start_date} to {end_date} (up to {days} working days)")

        # Budget and project parameters
        budget = 23000  # Budget in person-days

        # Count working days in 2025
        year_start = date(2025, 1, 1)
        year_end = date(2025, 12, 31)
        total_working_days = count_working_days(year_start, year_end)
        logger.info(f"Calculated {total_working_days} working days in 2025")

        # Fetch CLM data and related issues (only needs to be done once)
        clm_query = f'project = CLM AND filter={clm_filter_id}'
        logger.info(f"Fetching CLM issues with query: {clm_query}")

        # Get CLM issues
        clm_issues = analyzer.get_issues_by_filter(jql_query=clm_query)
        logger.info(f"Found {len(clm_issues)} CLM issues")

        if not clm_issues:
            logger.error("No CLM issues found. Check your credentials and filter ID.")
            return None

        # Get related issues
        logger.info(f"Fetching related issues...")
        est_issues, improvement_issues, implementation_issues = analyzer.get_clm_related_issues(clm_issues)

        logger.info(
            f"Found {len(est_issues)} EST issues, {len(improvement_issues)} improvement issues, and {len(implementation_issues)} implementation issues")

        # Process implementation issues
        if not implementation_issues:
            logger.error("No implementation issues found. Cannot proceed.")
            return None

        # Get all implementation issue keys
        implementation_keys = [issue.get('key') for issue in implementation_issues if issue.get('key')]

        # Check if we have keys before proceeding
        if not implementation_keys:
            logger.error("No implementation issue keys found. Cannot proceed.")
            return None

        logger.info(f"Got {len(implementation_keys)} implementation issue keys")

        # Generate data for each day
        real_data = []
        current_date = start_date
        actual_days_generated = 0

        # Calculate days passed for first date of range
        days_passed_at_start = count_working_days(year_start, start_date)

        while current_date <= end_date and actual_days_generated < days:
            # Skip weekends
            if current_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                current_date += timedelta(days=1)
                continue

            # Calculate days passed until this date
            days_passed = count_working_days(year_start, current_date)

            actual_days_generated += 1
            date_str = current_date.strftime('%Y-%m-%d')
            logger.info(f"Processing data for date {date_str} (Day {actual_days_generated}/{days})")

            # For each day, we need to fetch worklogs that existed up to and including that day
            chunk_size = 100  # Adjust as needed based on JQL length limits
            worklog_issues = []

            # Process implementation issues in chunks to avoid JQL query length limits
            for i in range(0, len(implementation_keys), chunk_size):
                chunk = implementation_keys[i:i + chunk_size]
                # Create a JQL query using "issue in (key1, key2, ...)" format and add date filter
                worklog_query = f'issue in ({", ".join(chunk)}) AND worklogDate <= "{date_str}"'

                logger.info(
                    f"Fetching worklog data chunk {i // chunk_size + 1}/{(len(implementation_keys) + chunk_size - 1) // chunk_size} with query: {worklog_query}")
                try:
                    chunk_issues = analyzer.get_issues_by_filter(jql_query=worklog_query)
                    worklog_issues.extend(chunk_issues)
                    logger.info(f"Retrieved {len(chunk_issues)} issues with worklogs from chunk")
                except Exception as e:
                    logger.error(f"Error fetching chunk {i // chunk_size + 1}: {e}")

            logger.info(f"Retrieved {len(worklog_issues)} total issues with worklogs for date {date_str}")

            # Process the worklog data
            if worklog_issues:
                df_worklog = process_issues_data(worklog_issues)

                # Calculate total time spent
                total_time_spent_hours = df_worklog['time_spent_hours'].sum() if not df_worklog.empty else 0

                # Calculate projected time spent
                projected_time_spent = (budget / total_working_days) * days_passed

                # Get open tasks data
                open_tasks_data = {}
                open_statuses = get_improved_open_statuses(df_worklog)
                open_tasks = df_worklog[df_worklog['status'].isin(open_statuses) & (df_worklog['time_spent_hours'] > 0)]

                if not open_tasks.empty:
                    open_tasks_by_project = open_tasks.groupby('project').size().to_dict()
                    open_tasks_data = open_tasks_by_project

                # Create data for this date
                daily_data = {
                    'date': date_str,
                    'total_time_spent_hours': float(total_time_spent_hours),
                    'total_time_spent_days': float(total_time_spent_hours / 8),  # Convert hours to days
                    'projected_time_spent_days': float(projected_time_spent),
                    'days_passed': days_passed,
                    'total_working_days': total_working_days,
                    'open_tasks_data': open_tasks_data,
                    'clm_issues_count': len(clm_issues),
                    'est_issues_count': len(est_issues),
                    'improvement_issues_count': len(improvement_issues),
                    'implementation_issues_count': len(implementation_issues)
                }

                # Save to file
                save_daily_data(daily_data)

                # Add to real data list
                real_data.append(daily_data)

                logger.info(
                    f"Generated data for {date_str}: {total_time_spent_hours:.2f} hours spent, {projected_time_spent:.2f} days projected")
            else:
                logger.warning(f"No worklog data found for date {date_str}")

                # Create minimal data for this date
                # Even with no worklog data, we should still create an entry to maintain the time series
                minimal_data = {
                    'date': date_str,
                    'total_time_spent_hours': 0.0,
                    'total_time_spent_days': 0.0,
                    'projected_time_spent_days': float((budget / total_working_days) * days_passed),
                    'days_passed': days_passed,
                    'total_working_days': total_working_days,
                    'open_tasks_data': {},
                    'clm_issues_count': len(clm_issues),
                    'est_issues_count': len(est_issues),
                    'improvement_issues_count': len(improvement_issues),
                    'implementation_issues_count': len(implementation_issues)
                }

                # Save to file
                save_daily_data(minimal_data)

                # Add to real data list
                real_data.append(minimal_data)

            # Move to next day
            current_date += timedelta(days=1)

        logger.info(f"Generated real data for {actual_days_generated} working days")
        logger.info(f"Files saved in {DASHBOARD_DIR} directory")

        return real_data

    except Exception as e:
        logger.error(f"Error generating real data: {e}", exc_info=True)
        return None


def clear_existing_data():
    """Clear existing data from the dashboard directory"""
    for file in os.listdir(DASHBOARD_DIR):
        file_path = os.path.join(DASHBOARD_DIR, file)
        if os.path.isfile(file_path):
            os.unlink(file_path)
    logger.info(f"Cleared existing data from {DASHBOARD_DIR}")


def save_daily_data(data):
    """
    Save daily dashboard data to a file.

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
        logger.error(f"Error saving dashboard data: {e}")


def count_working_days(start_date, end_date):
    """
    Count working days between two dates (excluding weekends)

    Args:
        start_date (date): Start date
        end_date (date): End date

    Returns:
        int: Number of working days
    """
    working_days = 0
    current_date = start_date

    while current_date <= end_date:
        # Check if current date is a weekday (0 = Monday, 6 = Sunday)
        if current_date.weekday() < 5:  # 0-4 are weekdays
            working_days += 1
        current_date += timedelta(days=1)

    return working_days


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate data for NBSS Dashboard')
    parser.add_argument('--days', type=int, default=7, help='Number of days to generate data for (default: 7)')
    parser.add_argument('--real', action='store_true', help='Generate real data from JIRA instead of test data')
    parser.add_argument('--filter', type=int, default=114473,
                        help='CLM Filter ID to use for real data (default: 114473)')

    args = parser.parse_args()

    if args.real:
        generate_real_data(args.days, args.filter)
    else:
        generate_test_data(args.days)