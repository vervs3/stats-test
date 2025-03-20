import os
import json
import logging
from flask import request, jsonify
from modules.log_buffer import get_logs
from modules.data_processor import get_improved_open_statuses
import pandas as pd

# Get logger
logger = logging.getLogger(__name__)

# Directory for reading issue keys
CHARTS_DIR = 'jira_charts'


def register_api_routes(app):
    """Register API routes"""

    # Add decorator to disable basic request logging for /logs to prevent log flooding
    @app.before_request
    def log_request_skip_logs():
        if request.path == '/logs':
            return None

    @app.route('/logs')
    def get_logs_route():
        """Return log entries from the buffer"""
        limit = request.args.get('limit', default=50, type=int)
        return jsonify(get_logs(limit))

    def get_issue_keys_for_clm_chart(timestamp, project, chart_type):
        """Get issue keys for CLM chart from saved data

        Args:
            timestamp (str): Analysis timestamp folder
            project (str): Project key or 'all' for all projects
            chart_type (str): Type of chart to get issue keys for

        Returns:
            list: List of issue keys
        """
        try:
            # Path to the issue keys file
            issue_keys_dir = os.path.join(CHARTS_DIR, timestamp, 'data')

            # First try to load the raw_issues.json file if it exists
            raw_issues_path = os.path.join(CHARTS_DIR, timestamp, 'raw_issues.json')
            filtered_issues = []

            if os.path.exists(raw_issues_path):
                with open(raw_issues_path, 'r', encoding='utf-8') as f:
                    issues = json.load(f)
                    # Filter by project if specified
                    if project != 'all':
                        filtered_issues = [issue['key'] for issue in issues
                                           if issue.get('fields', {}).get('project', {}).get('key') == project]
                    else:
                        filtered_issues = [issue['key'] for issue in issues if 'key' in issue]

            # If no raw issues found or the file doesn't exist, check for CLM-specific issue keys
            if not filtered_issues:
                clm_keys_path = os.path.join(issue_keys_dir, 'clm_issue_keys.json')
                if os.path.exists(clm_keys_path):
                    with open(clm_keys_path, 'r', encoding='utf-8') as f:
                        clm_data = json.load(f)

                        # Depending on the chart type, return different sets of issue keys
                        if chart_type == 'clm_issues':
                            keys = clm_data.get('clm_issue_keys', [])
                        elif chart_type == 'est_issues':
                            keys = clm_data.get('est_issue_keys', [])
                        elif chart_type == 'improvement_issues':
                            keys = clm_data.get('improvement_issue_keys', [])
                        elif chart_type == 'linked_issues':
                            keys = clm_data.get('implementation_issue_keys', [])
                        elif chart_type == 'filtered_issues':
                            keys = clm_data.get('filtered_issue_keys', [])
                        elif chart_type == 'open_tasks':
                            # For open tasks, filter for tasks that are in an open status and have time spent
                            # This could be pre-computed and stored separately
                            open_keys = clm_data.get('open_tasks_issue_keys', [])
                            if not open_keys and 'filtered_issue_keys' in clm_data:
                                # If we don't have specific open_tasks keys, use raw data filtering
                                raw_data_path = os.path.join(issue_keys_dir, 'raw_data.json')
                                if os.path.exists(raw_data_path):
                                    try:
                                        with open(raw_data_path, 'r', encoding='utf-8') as f:
                                            raw_data = json.load(f)
                                            df = pd.DataFrame(raw_data)
                                            # Filter for open tasks with time spent
                                            open_tasks = df[(df['status'].isin(['Open', 'NEW'])) &
                                                            (df['time_spent_hours'] > 0)]
                                            if project != 'all':
                                                open_tasks = open_tasks[open_tasks['project'] == project]
                                            open_keys = open_tasks['issue_key'].tolist()
                                    except Exception as e:
                                        logger.error(f"Error filtering open tasks: {e}")
                            return open_keys
                        elif chart_type == 'project_issues':
                            # For project-specific issues, return all implementation issues for this project
                            keys = []
                            # Get filtered issues for this project
                            for issue_key in clm_data.get('filtered_issue_keys', []):
                                raw_data_path = os.path.join(issue_keys_dir, 'raw_data.json')
                                if os.path.exists(raw_data_path):
                                    try:
                                        with open(raw_data_path, 'r', encoding='utf-8') as f:
                                            raw_data = json.load(f)
                                            df = pd.DataFrame(raw_data)
                                            # Filter for the specific project
                                            if project != 'all':
                                                project_issues = df[df['project'] == project]
                                                keys = project_issues['issue_key'].tolist()
                                            else:
                                                keys = df['issue_key'].tolist()
                                    except Exception as e:
                                        logger.error(f"Error filtering project issues: {e}")
                                break  # We only need to process once
                        else:
                            # Default to all filtered issues
                            keys = clm_data.get('filtered_issue_keys', [])

                        # Filter by project if specified and we have project info
                        if project != 'all' and 'project_issue_mapping' in clm_data:
                            project_mapping = clm_data.get('project_issue_mapping', {})
                            if project in project_mapping:
                                keys = [key for key in keys if key in project_mapping.get(project, [])]

                        return keys

            return filtered_issues

        except Exception as e:
            logger.error(f"Error getting issue keys for CLM chart: {e}")
            return []

    @app.route('/jql/project/<project>')
    def jql_by_project(project):
        """Generate JQL for filtering by project and redirect to Jira"""
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        base_jql = request.args.get('base_jql')
        is_clm = request.args.get('is_clm', 'false').lower() == 'true'
        timestamp = request.args.get('timestamp')

        if is_clm and timestamp:
            # Get issue keys for this project from saved data
            issue_keys = get_issue_keys_for_clm_chart(timestamp, project, 'project_issues')

            if issue_keys:
                # Create JQL with issue keys
                if len(issue_keys) > 100:
                    # For many issues, use a simplified JQL
                    jql = f'project = {project}'

                    # Add date filters if specified
                    if date_from or date_to:
                        date_parts = []
                        if date_from:
                            date_parts.append(f'worklogDate >= "{date_from}"')
                        if date_to:
                            date_parts.append(f'worklogDate <= "{date_to}"')

                        if date_parts:
                            jql += f' AND ({" AND ".join(date_parts)})'
                else:
                    # For a reasonable number of issues, explicitly list them
                    jql = f'issue in ({", ".join(issue_keys)})'
            else:
                # If no issue keys found, use a simple project filter
                jql = f'project = {project}'

                # Add date filters if specified
                if date_from or date_to:
                    date_parts = []
                    if date_from:
                        date_parts.append(f'worklogDate >= "{date_from}"')
                    if date_to:
                        date_parts.append(f'worklogDate <= "{date_to}"')

                    if date_parts:
                        jql += f' AND ({" AND ".join(date_parts)})'
        elif is_clm:
            # CLM analysis without timestamp - use linkedIssuesOfRecursive
            if base_jql and base_jql.startswith('filter='):
                # Extract filter ID
                clm_filter_id = base_jql.replace('filter=', '')

                # Create JQL for linked issues
                jql = f'project = {project} AND issue in linkedIssuesOfRecursive("filter = {clm_filter_id}")'

                # Add date filters if specified
                if date_from or date_to:
                    date_parts = []
                    if date_from:
                        date_parts.append(f'worklogDate >= "{date_from}"')
                    if date_to:
                        date_parts.append(f'worklogDate <= "{date_to}"')

                    if date_parts:
                        jql += f' AND ({" AND ".join(date_parts)})'
            else:
                # If no filter ID, use simple project filter
                jql = f'project = {project}'

                # Add date filters if specified
                if date_from or date_to:
                    date_parts = []
                    if date_from:
                        date_parts.append(f'worklogDate >= "{date_from}"')
                    if date_to:
                        date_parts.append(f'worklogDate <= "{date_to}"')

                    if date_parts:
                        jql += f' AND ({" AND ".join(date_parts)})'
        else:
            # Standard Jira mode
            conditions = [f"project = {project}"]

            # Add time filters if specified
            if date_from:
                conditions.append(f"worklogDate >= \"{date_from}\"")
            if date_to:
                conditions.append(f"worklogDate <= \"{date_to}\"")

            # If there's a base JQL, add it as a separate condition
            if base_jql:
                final_jql = f"({base_jql}) AND {' AND '.join(conditions)}"
            else:
                final_jql = ' AND '.join(conditions)

            jql = final_jql

        # Create URL for Jira
        jira_url = "https://jira.nexign.com/issues/?jql=" + jql.replace(" ", "%20")

        # Return JSON with URL and JQL
        return jsonify({
            'url': jira_url,
            'jql': jql
        })

    @app.route('/jql/special')
    def special_jql():
        """
        Generate special JQL for specific chart types

        Query params:
        - project: Project key
        - chart_type: Type of chart (open_tasks, clm_issues, etc.)
        - date_from: Start date (optional)
        - date_to: End date (optional)
        - base_jql: Base JQL query (optional)
        - is_clm: Whether this is a CLM analysis (optional)
        - timestamp: Analysis timestamp folder (optional)
        """
        project = request.args.get('project')
        chart_type = request.args.get('chart_type')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        base_jql = request.args.get('base_jql')
        is_clm = request.args.get('is_clm', 'false').lower() == 'true'
        timestamp = request.args.get('timestamp')

        if not chart_type:
            return jsonify({
                'error': 'chart_type is required',
                'url': 'https://jira.nexign.com',
                'jql': ''
            }), 400

        if is_clm and timestamp:
            # Get issue keys for this chart type from saved data
            issue_keys = get_issue_keys_for_clm_chart(timestamp, project, chart_type)

            if issue_keys:
                # If we have a lot of issues, it's better to use a more general query
                if len(issue_keys) > 100:
                    # For many issues, use a simplified JQL
                    if chart_type == 'open_tasks':
                        jql = f'project = {project} AND status in (Open, "NEW") AND timespent > 0'
                    elif chart_type == 'clm_issues':
                        jql = 'project = CLM'
                    elif chart_type == 'est_issues':
                        jql = 'project = EST'
                    elif chart_type == 'improvement_issues':
                        jql = 'issuetype = "Improvement from CLM"'
                    elif chart_type in ['linked_issues', 'filtered_issues', 'project_issues']:
                        if project != 'all':
                            jql = f'project = {project}'
                        else:
                            jql = 'project in ()'  # Add the relevant projects here
                    else:
                        jql = 'issue in ()'  # Fallback empty query

                    # Add date filters if specified
                    if date_from or date_to:
                        date_parts = []
                        if date_from:
                            date_parts.append(f'worklogDate >= "{date_from}"')
                        if date_to:
                            date_parts.append(f'worklogDate <= "{date_to}"')

                        if date_parts and jql != 'issue in ()':
                            jql += f' AND ({" AND ".join(date_parts)})'
                else:
                    # For a reasonable number of issues, explicitly list them
                    jql = f'issue in ({", ".join(issue_keys)})'
            else:
                # If no issue keys found, use a fallback query
                if chart_type == 'open_tasks':
                    jql = f'project = {project} AND status in (Open, "NEW") AND timespent > 0'
                elif chart_type == 'clm_issues':
                    jql = 'project = CLM'
                elif chart_type == 'est_issues':
                    jql = 'project = EST'
                elif chart_type == 'improvement_issues':
                    jql = 'issuetype = "Improvement from CLM"'
                elif chart_type in ['linked_issues', 'filtered_issues', 'project_issues']:
                    if project != 'all':
                        jql = f'project = {project}'
                    else:
                        jql = ''  # Empty query as fallback
                else:
                    jql = ''  # Empty query as fallback

                # Add date filters if specified
                if date_from or date_to:
                    date_parts = []
                    if date_from:
                        date_parts.append(f'worklogDate >= "{date_from}"')
                    if date_to:
                        date_parts.append(f'worklogDate <= "{date_to}"')

                    if date_parts and jql:
                        jql += f' AND ({" AND ".join(date_parts)})'

                # If still empty, use a default query
                if not jql:
                    jql = 'project = CLM'  # Default to CLM project
        elif is_clm:
            # CLM analysis without timestamp
            if base_jql and base_jql.startswith('filter='):
                # Extract filter ID
                clm_filter_id = base_jql.replace('filter=', '')

                if chart_type == 'open_tasks':
                    # Query for open tasks with time spent
                    jql = f'project = {project} AND issue in linkedIssuesOfRecursive("filter = {clm_filter_id}") AND status in (Open, "NEW") AND timespent > 0'
                else:
                    # Query for other chart types
                    jql = f'project = {project} AND issue in linkedIssuesOfRecursive("filter = {clm_filter_id}")'

                # Add date filters if specified
                if date_from or date_to:
                    date_parts = []
                    if date_from:
                        date_parts.append(f'worklogDate >= "{date_from}"')
                    if date_to:
                        date_parts.append(f'worklogDate <= "{date_to}"')

                    if date_parts:
                        jql += f' AND ({" AND ".join(date_parts)})'
            else:
                # If no filter ID, use simple queries
                if chart_type == 'open_tasks':
                    jql = f'project = {project} AND status in (Open, "NEW") AND timespent > 0'
                else:
                    jql = f'project = {project}'

                # Add date filters if specified
                if date_from or date_to:
                    date_parts = []
                    if date_from:
                        date_parts.append(f'worklogDate >= "{date_from}"')
                    if date_to:
                        date_parts.append(f'worklogDate <= "{date_to}"')

                    if date_parts:
                        jql += f' AND ({" AND ".join(date_parts)})'
        else:
            # Standard Jira mode
            conditions = []

            if project != 'all':
                conditions.append(f"project = {project}")

            # Add conditions based on chart type
            if chart_type == 'open_tasks':
                # Use default open statuses
                conditions.append("status in (Open, \"NEW\")")
                conditions.append("timespent > 0")

            # Add time filters if specified
            if date_from or date_to:
                date_parts = []
                if date_from:
                    date_parts.append(f"worklogDate >= \"{date_from}\"")
                if date_to:
                    date_parts.append(f"worklogDate <= \"{date_to}\"")

                if date_parts:
                    conditions.append(f"({' AND '.join(date_parts)})")

            # If there's a base JQL, add it as a separate condition
            if base_jql:
                if conditions:
                    final_jql = f"({base_jql}) AND ({' AND '.join(conditions)})"
                else:
                    final_jql = base_jql
            else:
                final_jql = ' AND '.join(conditions) if conditions else ''

            jql = final_jql

        # Create URL for Jira
        jira_url = "https://jira.nexign.com/issues/?jql=" + jql.replace(" ", "%20")

        # Log the generated query
        logger.info(f"Generated special JQL for {chart_type}, project {project}: {jql}")

        return jsonify({
            'url': jira_url,
            'jql': jql
        })