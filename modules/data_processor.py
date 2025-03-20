import pandas as pd
import json
import logging

# Get logger
logger = logging.getLogger(__name__)


def process_issues_data(issues):
    """
    Process issue data into a structured DataFrame with improved status handling.
    Added transitions analysis to identify issues that never changed status.

    Args:
        issues (list): List of issue dictionaries

    Returns:
        pandas.DataFrame: Processed data
    """
    processed_data = []

    # Output the first issue for debugging
    if issues:
        first_issue = issues[0]
        status_raw = first_issue.get('fields', {}).get('status', {})
        logger.info(f"Example status field structure: {json.dumps(status_raw, indent=2, ensure_ascii=False)}")

        # Check changelog structure
        if 'changelog' in first_issue:
            changelog_sample = first_issue.get('changelog', {})
            logger.info(f"Changelog structure: {json.dumps(changelog_sample, indent=2, ensure_ascii=False)[:500]}...")

    for issue in issues:
        issue_key = issue.get('key')
        fields = issue.get('fields', {})

        project = fields.get('project', {}).get('key', 'Unknown')
        issue_type = fields.get('issuetype', {}).get('name', 'Unknown')
        original_estimate = fields.get('timeoriginalestimate', 0) or 0  # Convert None to 0
        time_spent = fields.get('timespent', 0) or 0  # Convert None to 0
        created_date = fields.get('created', '')

        # Get issue status (with debugging info)
        status_obj = fields.get('status', {})
        status = status_obj.get('name', 'Unknown')
        status_id = status_obj.get('id', 'Unknown')
        status_category = status_obj.get('statusCategory', {}).get('name', 'Unknown')

        # Check for comments
        comments = fields.get('comment', {}).get('comments', [])
        has_comments = len(comments) > 0

        # Check for attachments
        attachments = fields.get('attachment', [])
        has_attachments = len(attachments) > 0

        # Convert seconds to hours
        original_estimate_hours = original_estimate / 3600 if original_estimate else 0
        time_spent_hours = time_spent / 3600 if time_spent else 0

        # Analyze changelog for transitions
        # Look for status changes in history
        no_transitions = True  # Default assumption: no transitions

        if 'changelog' in issue and 'histories' in issue['changelog']:
            for history in issue['changelog']['histories']:
                for item in history.get('items', []):
                    if item.get('field') == 'status':
                        # Found status transition
                        no_transitions = False
                        break
                if not no_transitions:
                    break

        # Log info about issues without transitions
        if no_transitions:
            logger.info(f"Issue {issue_key} has no status transitions (possibly new), current status: {status}")

        processed_data.append({
            'issue_key': issue_key,
            'project': project,
            'issue_type': issue_type,
            'original_estimate_hours': original_estimate_hours,
            'time_spent_hours': time_spent_hours,
            'status': status,
            'status_id': status_id,
            'status_category': status_category,
            'has_comments': has_comments,
            'has_attachments': has_attachments,
            'created_date': created_date,
            'no_transitions': no_transitions
        })

    # Create DataFrame
    df = pd.DataFrame(processed_data)

    # Output unique statuses for debugging
    unique_statuses = df['status'].unique()
    logger.info(f"Unique issue statuses: {unique_statuses}")

    # Output count of issues without transitions
    no_transitions_count = df['no_transitions'].sum()
    logger.info(f"Found {no_transitions_count} issues without transitions")

    return df


def get_improved_open_statuses(df):
    """
    Improved detection of open statuses

    Args:
        df (pandas.DataFrame): Processed data

    Returns:
        list: List of status names identified as 'open'
    """
    logger.info("IMPROVED OPEN STATUS DETECTION")

    # Common open status terms (expanded)
    open_terms = [
        'OPEN', 'NEW'
    ]

    # Get all unique statuses
    all_statuses = df['status'].unique().tolist()
    logger.info(f"ALL UNIQUE STATUSES: {all_statuses}")

    # Identify open statuses
    open_statuses = []
    for status in all_statuses:
        status_lower = status.lower()
        for term in open_terms:
            if term.lower() in status_lower:
                open_statuses.append(status)
                logger.info(f"Status '{status}' identified as OPEN (matches '{term}')")
                break

    # If none found, use a default approach
    if not open_statuses:
        logger.warning("NO OPEN STATUSES FOUND! Using default 'Open' status only.")
        open_statuses = ['Open']

    return open_statuses


def get_status_categories(df):
    """
    Get status categories (open, closed, unknown)

    Args:
        df (pandas.DataFrame): Processed data

    Returns:
        dict: Dictionary with categorized statuses
    """
    # Get all unique statuses
    all_statuses = df['status'].unique().tolist()
    logger.info(f"ALL STATUSES IN DATASET: {all_statuses}")

    # Terms for detecting open and closed statuses - expanded list with Russian terms
    open_terms = [
        'OPEN', 'NEW'
    ]

    closed_terms = [
        'CLOSED', 'RESOLVED', 'DONE'
    ]

    # Initialize categories
    open_statuses = []
    closed_statuses = []
    unknown_statuses = []

    # Log every status matching decision for debugging
    for status in all_statuses:
        status_lower = status.lower()
        matched = False

        # Check if it matches open terms
        for term in open_terms:
            if term.lower() in status_lower:
                open_statuses.append(status)
                logger.info(f"STATUS '{status}' categorized as OPEN (matched term: '{term}')")
                matched = True
                break

        if not matched:
            # Check if it matches closed terms
            for term in closed_terms:
                if term.lower() in status_lower:
                    closed_statuses.append(status)
                    logger.info(f"STATUS '{status}' categorized as CLOSED (matched term: '{term}')")
                    matched = True
                    break

        # If it doesn't match any known pattern, consider it unknown
        if not matched:
            unknown_statuses.append(status)
            logger.info(f"STATUS '{status}' NOT CATEGORIZED (no matching terms)")

    logger.info(f"OPEN STATUSES: {open_statuses}")
    logger.info(f"CLOSED STATUSES: {closed_statuses}")
    logger.info(f"UNKNOWN STATUSES: {unknown_statuses}")

    # Return categorization
    return {
        'all_statuses': all_statuses,
        'open_statuses': open_statuses,
        'closed_statuses': closed_statuses,
        'unknown_statuses': unknown_statuses
    }


def diagnose_issues_data(df, status_mapping=None):
    """
    Diagnose issue data to identify problems with special chart display

    Args:
        df (pandas.DataFrame): Processed data
        status_mapping (dict): Optional mapping of statuses to categories

    Returns:
        dict: Diagnostic report
    """
    logger.info("=== ISSUE DATA DIAGNOSTICS ===")

    # Get statuses using extended method
    status_categories = get_status_categories(df)
    open_statuses = status_categories['open_statuses']
    closed_statuses = status_categories['closed_statuses']
    unknown_statuses = status_categories['unknown_statuses']

    # 1. Check all unique statuses
    unique_statuses = df['status'].unique()
    logger.info(f"Unique statuses in dataset: {unique_statuses}")

    # 2. Count issues by status
    status_counts = df['status'].value_counts()
    logger.info(f"Issue distribution by status:\n{status_counts}")

    # 3. Check issues with logged time
    tasks_with_time = df[df['time_spent_hours'] > 0]
    status_with_time = tasks_with_time['status'].value_counts()
    logger.info(f"Statuses of issues with logged time:\n{status_with_time}")

    # 4. Check issues without comments and attachments
    tasks_no_comments_attachments = df[(~df['has_comments']) & (~df['has_attachments'])]
    status_no_comments = tasks_no_comments_attachments['status'].value_counts()
    logger.info(f"Statuses of issues without comments and attachments:\n{status_no_comments}")

    # 5. Find open issues with logged time
    open_tasks = df[df['status'].isin(open_statuses) & (df['time_spent_hours'] > 0)]
    logger.info(f"Found {len(open_tasks)} open issues with logged time")
    if not open_tasks.empty:
        open_by_project = open_tasks.groupby('project')['time_spent_hours'].sum()
        logger.info(f"Distribution by project:\n{open_by_project}")

    # 6. Find closed issues without comments and attachments
    closed_tasks = df[df['status'].isin(closed_statuses) & (~df['has_comments']) & (~df['has_attachments'])]
    logger.info(f"Found {len(closed_tasks)} closed issues without comments and attachments")
    if not closed_tasks.empty:
        closed_by_project = closed_tasks.groupby('project').size()
        logger.info(f"Distribution by project:\n{closed_by_project}")

    # 7. Diagnose issues without transitions
    no_transitions_tasks = df[df['no_transitions'] == True]
    logger.info(f"Found {len(no_transitions_tasks)} issues without transitions (likely new)")
    if not no_transitions_tasks.empty:
        no_transitions_by_project = no_transitions_tasks.groupby('project').size()
        logger.info(f"Distribution of issues without transitions by project:\n{no_transitions_by_project}")

    return {
        "unique_statuses": unique_statuses.tolist(),
        "open_statuses": open_statuses,
        "closed_statuses": closed_statuses,
        "unknown_statuses": unknown_statuses,
        "total_issues": len(df),
        "open_tasks_count": len(open_tasks),
        "closed_tasks_no_comments_count": len(closed_tasks),
        "no_transitions_tasks_count": len(no_transitions_tasks)
    }