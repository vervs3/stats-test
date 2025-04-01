import os
import json
import logging
import re

import logger
import pandas as pd
from datetime import datetime, timedelta, date
from modules.jira_analyzer import JiraAnalyzer
from modules.data_processor import process_issues_data, get_improved_open_statuses, get_status_categories

try:
    from config import PROJECT_BUDGET, DASHBOARD_UPDATE_HOUR, DASHBOARD_UPDATE_MINUTE, DASHBOARD_REFRESH_INTERVAL
except ImportError:
    # Если импорт не удался, используем значения по умолчанию
    logger.warning("Could not import dashboard configuration from config.py, using default values")
    PROJECT_BUDGET = 18000
    DASHBOARD_UPDATE_HOUR = 9
    DASHBOARD_UPDATE_MINUTE = 0
    DASHBOARD_REFRESH_INTERVAL = 3600

# Get logger
logger = logging.getLogger(__name__)

# Directory for dashboard data
DASHBOARD_DIR = 'nbss_data'

# Ensure the directory exists
if not os.path.exists(DASHBOARD_DIR):
    os.makedirs(DASHBOARD_DIR)


def has_merge_request_mentions(issue):
    """
    Проверяет, содержит ли задача упоминания merge requests

    Args:
        issue (dict): Словарь с данными задачи из Jira API

    Returns:
        bool: True если есть упоминания merge requests, иначе False
    """
    # Проверяем комментарии
    comments = issue.get('fields', {}).get('comment', {}).get('comments', [])
    for comment in comments:
        comment_text = comment.get('body', '')
        # Ищем упоминания merge requests по паттерну
        if re.search(r'merge\s+request', comment_text, re.IGNORECASE) or 'SSO-' in comment_text:
            return True

    # Проверяем описание задачи
    description = issue.get('fields', {}).get('description', '') or ''
    if re.search(r'merge\s+request', description, re.IGNORECASE) or 'SSO-' in description:
        return True

    # Проверяем summary
    summary = issue.get('fields', {}).get('summary', '') or ''
    if re.search(r'merge\s+request', summary, re.IGNORECASE) or 'SSO-' in summary:
        return True

    # Проверяем наличие issue links типа "mentioned on" с MR
    issue_links = issue.get('fields', {}).get('issuelinks', [])
    for link in issue_links:
        # Проверяем тип связи
        link_type_name = link.get('type', {}).get('name', '').lower()

        # Ищем связь "mentioned on"
        if link_type_name == 'mentioned on' or 'mention' in link_type_name:
            # Проверяем ключ связанной задачи - часто MR имеют формат "SSO-XXXXX"
            related_key = None
            if 'inwardIssue' in link:
                related_key = link.get('inwardIssue', {}).get('key', '')
            elif 'outwardIssue' in link:
                related_key = link.get('outwardIssue', {}).get('key', '')

            if related_key and 'SSO-' in related_key:
                return True

    return False


def collect_daily_data():
    """
    Collect and process daily data for the NBSS Dashboard.
    This should be run daily at the configured time (default: 9:00 AM).
    """
    logger.info(f"Collecting daily data for NBSS Dashboard at {DASHBOARD_UPDATE_HOUR}:{DASHBOARD_UPDATE_MINUTE}")

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

        # Process CLM issues to get time spent directly
        # This is important to include time logged against CLM tickets themselves
        clm_time_spent_hours = 0
        for issue in clm_issues:
            time_spent = issue.get('fields', {}).get('timespent', 0) or 0
            clm_time_spent_hours += time_spent / 3600

        logger.info(f"Time spent directly on CLM issues: {clm_time_spent_hours} hours")

        # Get related issues
        est_issues, improvement_issues, implementation_issues = analyzer.get_clm_related_issues(clm_issues)

        # Process implementation issues to get time spent
        df = None
        if implementation_issues:
            df = process_issues_data(implementation_issues)

        # Calculate time spent in person-days (assuming 8 hours per day)
        implementation_time_spent_hours = 0
        if df is not None and not df.empty:
            implementation_time_spent_hours = df['time_spent_hours'].sum()

        # Add the time spent on CLM issues to the total
        total_time_spent_hours = implementation_time_spent_hours + clm_time_spent_hours
        total_time_spent_days = total_time_spent_hours / 8

        logger.info(f"Total time spent: {total_time_spent_hours} hours ({total_time_spent_days} days)")
        logger.info(f"  - Implementation issues: {implementation_time_spent_hours} hours")
        logger.info(f"  - CLM issues: {clm_time_spent_hours} hours")

        # Calculate projected time spent
        # Budget = PROJECT_BUDGET person-days, project duration = 2025 year
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
        open_tasks_issue_keys = []

        # Calculate closed tasks data
        closed_tasks_data = {}
        closed_tasks_issue_keys = []

        if df is not None and not df.empty:
            # Filter for open tasks with time spent
            open_statuses = get_improved_open_statuses(df)
            open_tasks = df[df['status'].isin(open_statuses) & (df['time_spent_hours'] > 0)]

            if not open_tasks.empty:
                # Group by project
                open_tasks_by_project = open_tasks.groupby('project').size().to_dict()
                open_tasks_data = open_tasks_by_project

                # Store issue keys for open tasks
                open_tasks_issue_keys = open_tasks['issue_key'].tolist()

            # Calculate closed tasks without comments, attachments, and links
            # Get status categories
            status_categories = get_status_categories(df)
            closed_statuses = status_categories['closed_statuses']

            # Предварительная фильтрация
            pre_filtered_tasks = df[df['status'].isin(closed_statuses) &
                                    (~df['has_comments']) &
                                    (~df['has_attachments']) &
                                    (~df['has_links'])]

            logger.info(f"Pre-filtered {len(pre_filtered_tasks)} closed tasks without comments, attachments, and links")

            # Дополнительная фильтрация на упоминания merge requests
            closed_tasks_final = []
            merge_request_mentions_count = 0

            # Получаем raw issues для проверки упоминаний merge requests
            # Создаем mapping из ключей задач в raw issues
            issue_mapping = {issue.get('key'): issue for issue in implementation_issues if issue.get('key')}

            for _, row in pre_filtered_tasks.iterrows():
                issue_key = row['issue_key']
                raw_issue = issue_mapping.get(issue_key)

                if raw_issue:
                    if not has_merge_request_mentions(raw_issue):
                        closed_tasks_final.append(row)
                    else:
                        merge_request_mentions_count += 1
                else:
                    # Если не нашли raw issue, считаем что она всё равно подходит
                    closed_tasks_final.append(row)
                    logger.warning(f"Could not find raw issue for {issue_key} for merge request check")

            logger.info(f"Filtered out {merge_request_mentions_count} issues with merge request mentions")

            # Конвертируем список обратно в DataFrame
            if closed_tasks_final:
                closed_tasks = pd.DataFrame(closed_tasks_final)
            else:
                closed_tasks = pd.DataFrame(columns=pre_filtered_tasks.columns)

            if not closed_tasks.empty:
                # Group by project
                closed_tasks_by_project = closed_tasks.groupby('project').size().to_dict()
                closed_tasks_data = closed_tasks_by_project

                logger.info(
                    f"Found {len(closed_tasks)} closed tasks without comments, attachments, links, and merge request mentions")
                logger.info(f"Closed tasks by project: {closed_tasks_data}")

                # Store issue keys for closed tasks
                closed_tasks_issue_keys = closed_tasks['issue_key'].tolist()

                # Log some sample keys for diagnostic purposes
                sample_keys = closed_tasks_issue_keys[:5] if len(
                    closed_tasks_issue_keys) > 5 else closed_tasks_issue_keys
                logger.info(f"Sample closed task keys: {sample_keys}")
            else:
                logger.info("No closed tasks without comments, attachments, links, and merge request mentions found")

        # Get today's date string for file naming
        date_str = datetime.now().strftime('%Y%m%d')

        # Create directories for today's data
        daily_dir = os.path.join(DASHBOARD_DIR, date_str)
        data_dir = os.path.join(daily_dir, 'data')
        metrics_dir = os.path.join(daily_dir, 'metrics')

        if not os.path.exists(daily_dir):
            os.makedirs(daily_dir)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        if not os.path.exists(metrics_dir):
            os.makedirs(metrics_dir)

        # Save raw issues in a similar format to CLM analyzer
        # Modified: Using the same structure as Jira analyzer (filtered_issues and all_implementation_issues)
        combined_issues = {
            "filtered_issues": implementation_issues,  # Use implementation issues as filtered
            "all_implementation_issues": implementation_issues
        }

        # Also add CLM, EST, and improvement issues within the structure
        # but kept separately to retain full context
        raw_data = {
            "filtered_issues": implementation_issues,
            "all_implementation_issues": implementation_issues,
            "additional_data": {
                "clm_issues": clm_issues,
                "est_issues": est_issues,
                "improvement_issues": improvement_issues
            }
        }

        # Save raw issues
        raw_issues_path = os.path.join(daily_dir, 'raw_issues.json')
        with open(raw_issues_path, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved raw issues data to {raw_issues_path}")

        # Save keys data
        keys_data = {
            'clm_issue_keys': [issue.get('key') for issue in clm_issues if issue.get('key')],
            'est_issue_keys': [issue.get('key') for issue in est_issues if issue.get('key')],
            'improvement_issue_keys': [issue.get('key') for issue in improvement_issues if issue.get('key')],
            'implementation_issue_keys': [issue.get('key') for issue in implementation_issues if issue.get('key')],
            'filtered_issue_keys': [issue.get('key') for issue in implementation_issues if issue.get('key')],
            'open_tasks_issue_keys': open_tasks_issue_keys,
            'closed_tasks_issue_keys': closed_tasks_issue_keys  # Явно сохраняем ключи закрытых задач
        }

        # Group issue keys by project for JQL generation
        project_issue_mapping = {}
        for issue in implementation_issues:
            issue_key = issue.get('key')
            project_key = issue.get('fields', {}).get('project', {}).get('key', '')
            if issue_key and project_key:
                if project_key not in project_issue_mapping:
                    project_issue_mapping[project_key] = []
                project_issue_mapping[project_key].append(issue_key)

        keys_data['project_issue_mapping'] = project_issue_mapping

        # Group closed tasks by project for easier access in JQL generation
        closed_tasks_by_project = {}
        if not closed_tasks.empty:
            # Group by project
            for project in closed_tasks['project'].unique():
                project_tasks = closed_tasks[closed_tasks['project'] == project]
                closed_tasks_by_project[project] = project_tasks['issue_key'].tolist()

            logger.info(f"Mapped {len(closed_tasks_by_project)} projects with closed tasks")

        # Save the closed tasks by project mapping
        keys_data['closed_tasks_by_project'] = closed_tasks_by_project

        clm_keys_path = os.path.join(data_dir, 'clm_issue_keys.json')
        with open(clm_keys_path, 'w', encoding='utf-8') as f:
            json.dump(keys_data, f, indent=4, ensure_ascii=False)
        logger.info(f"Saved CLM issue keys to {clm_keys_path}")

        # Save additional details about closed tasks to a separate metrics file for easier access
        if closed_tasks_issue_keys:
            closed_tasks_metrics = {
                'count': len(closed_tasks_issue_keys),
                'by_project': closed_tasks_data,
                'issue_keys': closed_tasks_issue_keys,
                'by_project_issue_keys': closed_tasks_by_project
            }

            closed_tasks_metrics_path = os.path.join(metrics_dir, 'closed_tasks_no_links.json')
            with open(closed_tasks_metrics_path, 'w', encoding='utf-8') as f:
                json.dump(closed_tasks_metrics, f, indent=4, ensure_ascii=False)
            logger.info(f"Saved detailed closed tasks metrics to {closed_tasks_metrics_path}")

        # Create data to save
        dashboard_data = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'timestamp': date_str,  # Use date as timestamp for folder reference
            'total_time_spent_hours': float(total_time_spent_hours),
            'total_time_spent_days': float(total_time_spent_days),
            'projected_time_spent_days': float(projected_time_spent),
            'days_passed': days_passed,
            'total_working_days': total_working_days,
            'open_tasks_data': open_tasks_data,
            'closed_tasks_data': closed_tasks_data,  # Явно сохраняем данные по закрытым задачам
            'clm_issues_count': len(clm_issues),
            'est_issues_count': len(est_issues),
            'improvement_issues_count': len(improvement_issues),
            'implementation_issues_count': len(implementation_issues),
            'clm_time_spent_hours': float(clm_time_spent_hours),
            'implementation_time_spent_hours': float(implementation_time_spent_hours),
            'refresh_interval': DASHBOARD_REFRESH_INTERVAL
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
    MODIFIED: Now only saves in the folder structure to avoid duplication

    Args:
        data (dict): Dashboard data to save
    """
    try:
        # Create filename based on date
        date_str = data['timestamp']

        # Create the path to the specific date folder
        folder_path = os.path.join(DASHBOARD_DIR, date_str)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        # Save summary file in the date folder
        summary_path = os.path.join(folder_path, 'summary.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved dashboard data to {summary_path}")
    except Exception as e:
        logger.error(f"Error saving dashboard data: {e}", exc_info=True)


def get_dashboard_data():
    """
    Get all dashboard data for the NBSS Dashboard.
    MODIFIED: Now properly handles folder structure and avoids duplicates

    Returns:
        dict: Dashboard data with time series and latest data
    """
    try:
        # Get all data folders in the DASHBOARD_DIR
        all_data = []
        processed_dates = set()  # To track processed dates and avoid duplicates

        # First, scan the directory for date folders
        for item in os.listdir(DASHBOARD_DIR):
            item_path = os.path.join(DASHBOARD_DIR, item)

            # Only process directories with the date format (8 digits)
            if os.path.isdir(item_path) and item.isdigit() and len(item) == 8:
                # Look for summary.json in the folder
                summary_path = os.path.join(item_path, 'summary.json')
                if os.path.exists(summary_path):
                    try:
                        with open(summary_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                            # Make sure the data has required fields
                            if 'date' not in data:
                                date_obj = datetime.strptime(item, '%Y%m%d')
                                data['date'] = date_obj.strftime('%Y-%m-%d')

                            # Check if we already processed this date
                            if data['date'] not in processed_dates:
                                processed_dates.add(data['date'])

                                # Make sure open_tasks_data exists
                                if 'open_tasks_data' not in data:
                                    data['open_tasks_data'] = {}

                                # Make sure closed_tasks_data exists
                                if 'closed_tasks_data' not in data:
                                    data['closed_tasks_data'] = {}

                                all_data.append(data)
                                logger.info(f"Loaded dashboard data from folder: {item}")
                    except Exception as e:
                        logger.error(f"Error reading summary file {summary_path}: {e}")

        # Sort data by date
        all_data.sort(key=lambda x: x['date'])

        # Get latest data
        latest_data = all_data[-1] if all_data else None

        # Get the raw data for the latest date if available
        latest_date = latest_data.get('timestamp') if latest_data else None
        latest_folder_path = os.path.join(DASHBOARD_DIR, latest_date) if latest_date else None
        has_raw_data = False

        if latest_folder_path and os.path.exists(latest_folder_path):
            raw_issues_path = os.path.join(latest_folder_path, 'raw_issues.json')
            has_raw_data = os.path.exists(raw_issues_path)

        # Create time series data
        time_series = {
            'dates': [data['date'] for data in all_data],
            'actual_time_spent': [data.get('total_time_spent_days', 0) for data in all_data],
            'projected_time_spent': [data.get('projected_time_spent_days', 0) for data in all_data]
        }

        # Get latest open tasks data
        open_tasks_data = {}
        if latest_data:
            open_tasks_data = latest_data.get('open_tasks_data', {})

        # Get closed tasks data - improved logging and handling
        closed_tasks_data = {}
        if latest_data:
            closed_tasks_data = latest_data.get('closed_tasks_data', {})
            # Более подробное логирование для отладки
            if not closed_tasks_data:
                logger.warning(f"No closed_tasks_data found in latest data for timestamp {latest_date}")
                # Пытаемся найти closed_tasks_data в метриках или других местах
                if 'closed_tasks_no_links_count' in latest_data:
                    logger.info(f"Found closed_tasks_no_links_count: {latest_data['closed_tasks_no_links_count']}")

                # Проверяем файл метрик если не нашли closed_tasks_data в summary
                metrics_path = os.path.join(latest_folder_path, 'metrics', 'closed_tasks_no_links.json')
                if os.path.exists(metrics_path):
                    try:
                        with open(metrics_path, 'r', encoding='utf-8') as f:
                            metrics_data = json.load(f)
                            if 'by_project' in metrics_data:
                                closed_tasks_data = metrics_data['by_project']
                                logger.info(
                                    f"Found closed tasks data in metrics file: {len(closed_tasks_data)} projects")
                    except Exception as e:
                        logger.error(f"Error reading closed tasks metrics: {e}")

        # Get refresh interval from latest data or use the default
        refresh_interval = latest_data.get('refresh_interval',
                                           DASHBOARD_REFRESH_INTERVAL) if latest_data else DASHBOARD_REFRESH_INTERVAL

        logger.info(f"Returning dashboard data with latest_timestamp: {latest_date}")

        # Логируем данные для закрытых задач для отладки
        logger.info(f"Closed tasks data: {closed_tasks_data}")

        return {
            'time_series': time_series,
            'latest_data': latest_data,
            'open_tasks_data': open_tasks_data,
            'closed_tasks_data': closed_tasks_data,  # Добавляем данные о закрытых задачах
            'latest_timestamp': latest_date,
            'has_raw_data': has_raw_data,
            'refresh_interval': refresh_interval
        }
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}", exc_info=True)
        return {
            'time_series': {'dates': [], 'actual_time_spent': [], 'projected_time_spent': []},
            'latest_data': None,
            'open_tasks_data': {},
            'closed_tasks_data': {},  # Пустой словарь как запасной вариант
            'latest_timestamp': None,
            'has_raw_data': False,
            'refresh_interval': DASHBOARD_REFRESH_INTERVAL
        }