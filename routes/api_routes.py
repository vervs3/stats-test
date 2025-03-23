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
            clm_keys_path = os.path.join(issue_keys_dir, 'clm_issue_keys.json')

            if not os.path.exists(clm_keys_path):
                logger.error(f"CLM issue keys file not found: {clm_keys_path}")
                return []

            with open(clm_keys_path, 'r', encoding='utf-8') as f:
                clm_data = json.load(f)

                logger.info(f"Available key types in CLM data: {list(clm_data.keys())}")

                # Get keys based on chart type
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
                    # Use pre-computed open task keys if available
                    keys = clm_data.get('open_tasks_issue_keys', [])
                elif chart_type == 'project_issues':
                    # IMPROVED: Use the project_issue_mapping directly
                    if project != 'all' and 'project_issue_mapping' in clm_data:
                        keys = clm_data.get('project_issue_mapping', {}).get(project, [])
                    else:
                        keys = clm_data.get('filtered_issue_keys', [])
                else:
                    # Default to filtered issues
                    keys = clm_data.get('filtered_issue_keys', [])

                # If we need to filter by project and we're not already using project mapping
                if project != 'all' and chart_type != 'project_issues' and 'project_issue_mapping' in clm_data:
                    # Get all issues for this project
                    project_issues = clm_data.get('project_issue_mapping', {}).get(project, [])
                    # Filter the keys to only those in this project
                    filtered_keys = [key for key in keys if key in project_issues]
                    logger.info(f"Filtered from {len(keys)} to {len(filtered_keys)} keys for project {project}")
                    keys = filtered_keys

                logger.info(f"Found {len(keys)} issue keys for chart type {chart_type}, project {project}")
                return keys

        except Exception as e:
            logger.error(f"Error getting issue keys for CLM chart: {e}", exc_info=True)
            return []

    @app.route('/jql/project/<project>')
    def jql_by_project(project):
        """Generate JQL for filtering by project and redirect to Jira"""
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        base_jql = request.args.get('base_jql')
        is_clm = request.args.get('is_clm', 'false').lower() == 'true'
        timestamp = request.args.get('timestamp')

        # Add detailed logging to debug the issue
        logger.info(
            f"jql_by_project called with project={project}, date_from={date_from}, date_to={date_to}, is_clm={is_clm}")

        if is_clm and timestamp:
            # Get issue keys for this project from saved data
            issue_keys = get_issue_keys_for_clm_chart(timestamp, project, 'project_issues')

            # Additional logging
            logger.info(f"CLM mode: Found {len(issue_keys)} issue keys for project {project}")

            if issue_keys:
                # ENHANCED: Always use issue in (...) format with chunking for large sets
                chunk_size = 100  # Jira typically has limits on JQL length

                if len(issue_keys) > chunk_size:
                    # For many issues, split into chunks and join with OR
                    logger.info(f"Chunking {len(issue_keys)} issue keys into groups of {chunk_size}")
                    chunks = [issue_keys[i:i + chunk_size] for i in range(0, len(issue_keys), chunk_size)]

                    # Create a JQL with multiple "issue in (...)" clauses
                    jql_parts = [f'issue in ({", ".join(chunk)})' for chunk in chunks]
                    jql = ' OR '.join(jql_parts)

                    logger.info(f"Created chunked JQL with {len(chunks)} chunks")
                else:
                    # For a reasonable number of issues, use a single clause
                    jql = f'issue in ({", ".join(issue_keys)})'

                    logger.info(f"Created single-chunk JQL with {len(issue_keys)} issues")

                # Add date filters if specified
                if date_from or date_to:
                    date_parts = []
                    if date_from:
                        date_parts.append(f'worklogDate >= "{date_from}"')
                    if date_to:
                        date_parts.append(f'worklogDate <= "{date_to}"')

                    if date_parts:
                        jql = f'({jql}) AND ({" AND ".join(date_parts)})'
            else:
                # If no issue keys found, use a simple project filter
                jql = f'project = "{project}"'  # Ensure project is quoted

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
            conditions = [f'project = "{project}"']  # Ensure project is quoted

            # Add time filters if specified
            if date_from:
                conditions.append(f'worklogDate >= "{date_from}"')
            if date_to:
                conditions.append(f'worklogDate <= "{date_to}"')

            # If there's a base JQL, add it as a separate condition
            if base_jql:
                final_jql = f"({base_jql}) AND {' AND '.join(conditions)}"
            else:
                final_jql = ' AND '.join(conditions)

            jql = final_jql

        # Log the final JQL for debugging
        logger.info(f"Generated JQL for project {project}: {jql}")

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
        - ignore_period: Whether to ignore date filters (optional)
        """
        project = request.args.get('project')
        chart_type = request.args.get('chart_type')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        base_jql = request.args.get('base_jql')
        is_clm = request.args.get('is_clm', 'false').lower() == 'true'
        timestamp = request.args.get('timestamp')
        ignore_period = request.args.get('ignore_period', 'false').lower() == 'true'

        # Log the received parameters including ignore_period
        logger.info(f"special_jql called: project={project}, chart_type={chart_type}, is_clm={is_clm}, " +
                    f"ignore_period={ignore_period}, date_from={date_from}, date_to={date_to}")

        if not chart_type:
            return jsonify({
                'error': 'chart_type is required',
                'url': 'https://jira.nexign.com',
                'jql': ''
            }), 400

        # Define CLM summary chart types where we should NOT add worklog filters
        clm_summary_chart_types = ['clm_issues', 'est_issues', 'improvement_issues', 'linked_issues', 'filtered_issues']

        if is_clm and timestamp:
            # Get issue keys for this chart type from saved data
            issue_keys = get_issue_keys_for_clm_chart(timestamp, project, chart_type)

            if issue_keys:
                # ENHANCED: Always use issue in (...) format with chunking for large sets
                chunk_size = 100  # Jira typically has limits on JQL length

                if len(issue_keys) > chunk_size:
                    # For many issues, split into chunks and join with OR
                    logger.info(f"Chunking {len(issue_keys)} issue keys into groups of {chunk_size}")
                    chunks = [issue_keys[i:i + chunk_size] for i in range(0, len(issue_keys), chunk_size)]

                    # Create a JQL with multiple "issue in (...)" clauses
                    jql_parts = [f'issue in ({", ".join(chunk)})' for chunk in chunks]
                    jql = ' OR '.join(jql_parts)

                    logger.info(f"Created chunked JQL with {len(chunks)} chunks")
                else:
                    # For a reasonable number of issues, use a single clause
                    jql = f'issue in ({", ".join(issue_keys)})'

                    logger.info(f"Created single-chunk JQL with {len(issue_keys)} issues")

                # If not ignoring period and not a CLM summary chart type, add date filters
                if (date_from or date_to) and not ignore_period and chart_type not in clm_summary_chart_types:
                    date_parts = []
                    if date_from:
                        date_parts.append(f'worklogDate >= "{date_from}"')
                    if date_to:
                        date_parts.append(f'worklogDate <= "{date_to}"')

                    if date_parts:
                        jql = f'({jql}) AND ({" AND ".join(date_parts)})'
                        logger.info(f"Added date filters to JQL")
                elif chart_type in clm_summary_chart_types:
                    logger.info(f"Skipping date filters for CLM summary chart type: {chart_type}")
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

                logger.info(f"No issue keys found, using fallback query: {jql}")

                # Add date filters if specified and not ignoring period and not a CLM summary chart type
                if (date_from or date_to) and not ignore_period and chart_type not in clm_summary_chart_types:
                    date_parts = []
                    if date_from:
                        date_parts.append(f'worklogDate >= "{date_from}"')
                    if date_to:
                        date_parts.append(f'worklogDate <= "{date_to}"')

                    if date_parts and jql:
                        jql += f' AND ({" AND ".join(date_parts)})'
                elif chart_type in clm_summary_chart_types:
                    logger.info(f"Skipping date filters for CLM summary chart type (fallback): {chart_type}")

                # If still empty, use a default query
                if not jql:
                    jql = 'project = CLM'  # Default to CLM project
        else:
            # Standard Jira mode or CLM without timestamp
            conditions = []

            if project != 'all':
                conditions.append(f"project = {project}")

            # Add conditions based on chart type
            if chart_type == 'open_tasks':
                # Use default open statuses
                conditions.append("status in (Open, \"NEW\")")
                conditions.append("timespent > 0")

            # Add time filters if specified and not ignoring period and not a CLM summary chart type
            if (date_from or date_to) and not ignore_period and chart_type not in clm_summary_chart_types:
                date_parts = []
                if date_from:
                    date_parts.append(f"worklogDate >= \"{date_from}\"")
                if date_to:
                    date_parts.append(f"worklogDate <= \"{date_to}\"")

                if date_parts:
                    conditions.append(f"({' AND '.join(date_parts)})")
            elif chart_type in clm_summary_chart_types:
                logger.info(f"Skipping date filters for CLM summary chart type (standard mode): {chart_type}")

            # If there's a base JQL, add it as a separate condition
            if base_jql:
                if conditions:
                    final_jql = f"({base_jql}) AND ({' AND '.join(conditions)})"
                else:
                    final_jql = base_jql
            else:
                final_jql = ' AND '.join(conditions) if conditions else ''

            jql = final_jql

        # Log the final JQL query
        logger.info(f"Generated JQL for {chart_type}, project {project}, ignore_period={ignore_period}: {jql}")

        # Create URL for Jira
        jira_url = "https://jira.nexign.com/issues/?jql=" + jql.replace(" ", "%20")

        return jsonify({
            'url': jira_url,
            'jql': jql
        })

    @app.route('/api/clm-chart-data/<timestamp>')
    def clm_chart_data(timestamp):
        """
        Get full chart data for CLM analysis without period filtering
        Updated to work with the new raw_issues.json format that contains both
        filtered and all implementation issues.

        Args:
            timestamp (str): Analysis timestamp folder

        Returns:
            JSON with full chart data
        """
        try:
            # Проверка существования папки анализа
            folder_path = os.path.join(CHARTS_DIR, timestamp)
            if not os.path.exists(folder_path):
                return jsonify({
                    'error': 'Analysis not found',
                    'success': False
                }), 404

            # Путь к файлу raw_issues.json
            raw_issues_path = os.path.join(folder_path, 'raw_issues.json')
            if not os.path.exists(raw_issues_path):
                return jsonify({
                    'error': 'Raw issues data not found',
                    'success': False
                }), 404

            # Путь к файлу clm_issue_keys.json
            clm_keys_path = os.path.join(folder_path, 'data', 'clm_issue_keys.json')
            if not os.path.exists(clm_keys_path):
                return jsonify({
                    'error': 'CLM keys data not found',
                    'success': False
                }), 404

            # Загрузка данных о CLM задачах
            with open(clm_keys_path, 'r', encoding='utf-8') as f:
                clm_keys_data = json.load(f)

            # Получаем ключи implementation issues и filtered issues
            implementation_issue_keys = clm_keys_data.get('implementation_issue_keys', [])
            filtered_issue_keys = clm_keys_data.get('filtered_issue_keys', [])

            logger.info(f"Found {len(implementation_issue_keys)} implementation issue keys")
            logger.info(f"Found {len(filtered_issue_keys)} filtered issue keys")

            # Load raw issues with the new format (contains both filtered and all implementation issues)
            with open(raw_issues_path, 'r', encoding='utf-8') as f:
                raw_issues_data = json.load(f)

            # Check if we have the new format
            if isinstance(raw_issues_data,
                          dict) and 'filtered_issues' in raw_issues_data and 'all_implementation_issues' in raw_issues_data:
                # New format
                logger.info("Found new raw_issues.json format with both filtered and implementation issues")
                all_implementation_issues = raw_issues_data.get('all_implementation_issues', [])
                filtered_issues = raw_issues_data.get('filtered_issues', [])

                logger.info(
                    f"Loaded {len(all_implementation_issues)} implementation issues and {len(filtered_issues)} filtered issues")
            else:
                # Old format (just an array of filtered issues)
                logger.info("Found old raw_issues.json format, treating as filtered issues only")
                filtered_issues = raw_issues_data if isinstance(raw_issues_data, list) else []

                # Fall back to a copy of filtered issues for implementation issues
                all_implementation_issues = filtered_issues.copy()

                logger.info(f"Loaded {len(filtered_issues)} filtered issues, no separate implementation issues")

            # Process implementation issues to get all data
            from modules.data_processor import process_issues_data

            if all_implementation_issues:
                df_all = process_issues_data(all_implementation_issues)
                all_project_estimates = df_all.groupby('project')['original_estimate_hours'].sum().to_dict()
                all_project_time_spent = df_all.groupby('project')['time_spent_hours'].sum().to_dict()

                # IMPORTANT: Calculate the project counts based on the actual implementation issues
                all_project_counts = df_all['project'].value_counts().to_dict()

                logger.info(f"Processed implementation issues dataframe with {len(df_all)} rows")
                logger.info(
                    f"Implementation data: {len(all_project_estimates)} projects with estimates, {len(all_project_time_spent)} projects with time spent, {len(all_project_counts)} projects with counts")

                # Log first 5 projects with highest counts
                for i, (project, value) in enumerate(sorted(all_project_counts.items(), key=lambda x: -x[1])):
                    if i >= 5: break
                    logger.info(f"Project {project} implementation count: {value}")

                # Log first 5 projects with highest estimates
                for i, (project, value) in enumerate(sorted(all_project_estimates.items(), key=lambda x: -x[1])):
                    if i >= 5: break
                    logger.info(f"Project {project} implementation estimate: {value}")
            else:
                all_project_estimates = {}
                all_project_time_spent = {}
                all_project_counts = {}
                logger.warning("No implementation issues found")

            # Process filtered issues
            if filtered_issues:
                df_filtered = process_issues_data(filtered_issues)
                filtered_project_estimates = df_filtered.groupby('project')['original_estimate_hours'].sum().to_dict()
                filtered_project_time_spent = df_filtered.groupby('project')['time_spent_hours'].sum().to_dict()

                # Also calculate project counts for filtered data
                filtered_project_counts = df_filtered['project'].value_counts().to_dict()

                logger.info(f"Processed filtered issues dataframe with {len(df_filtered)} rows")
                logger.info(
                    f"Filtered data: {len(filtered_project_estimates)} projects with estimates, {len(filtered_project_time_spent)} projects with time spent, {len(filtered_project_counts)} projects with counts")

                # Log first 5 projects with highest counts in filtered data
                for i, (project, value) in enumerate(sorted(filtered_project_counts.items(), key=lambda x: -x[1])):
                    if i >= 5: break
                    logger.info(f"Project {project} filtered count: {value}")

                # Log first 5 projects with highest estimates
                for i, (project, value) in enumerate(sorted(filtered_project_estimates.items(), key=lambda x: -x[1])):
                    if i >= 5: break
                    logger.info(f"Project {project} filtered estimate: {value}")

                # Compare totals between implementation and filtered data
                impl_total_est = sum(all_project_estimates.values())
                impl_total_spent = sum(all_project_time_spent.values())
                impl_total_count = sum(all_project_counts.values())

                filtered_total_est = sum(filtered_project_estimates.values())
                filtered_total_spent = sum(filtered_project_time_spent.values())
                filtered_total_count = sum(filtered_project_counts.values())

                logger.info(
                    f"Implementation total: Estimate={impl_total_est}, Time Spent={impl_total_spent}, Count={impl_total_count}")
                logger.info(
                    f"Filtered total: Estimate={filtered_total_est}, Time Spent={filtered_total_spent}, Count={filtered_total_count}")
                logger.info(
                    f"Difference: Estimate={impl_total_est - filtered_total_est}, Time Spent={impl_total_spent - filtered_total_spent}, Count={impl_total_count - filtered_total_count}")
            else:
                filtered_project_estimates = {}
                filtered_project_time_spent = {}
                filtered_project_counts = {}
                logger.warning("No filtered issues found")

            # Get CLM estimates
            project_clm_estimates = {}

            # Load chart data for CLM estimates and original project order
            chart_data_path = os.path.join(folder_path, 'data', 'chart_data.json')
            existing_projects = []

            if os.path.exists(chart_data_path):
                try:
                    with open(chart_data_path, 'r', encoding='utf-8') as f:
                        chart_data = json.load(f)

                        # Get CLM estimates
                        if 'project_clm_estimates' in chart_data:
                            project_clm_estimates = chart_data['project_clm_estimates']

                        # Get original project order
                        if 'projects' in chart_data:
                            existing_projects = chart_data['projects']
                except Exception as e:
                    logger.error(f"Error reading chart data: {e}")

            # Combine all projects
            all_projects = set()
            all_projects.update(all_project_estimates.keys())
            all_projects.update(all_project_time_spent.keys())
            all_projects.update(all_project_counts.keys())
            all_projects.update(filtered_project_estimates.keys())
            all_projects.update(filtered_project_time_spent.keys())
            all_projects.update(filtered_project_counts.keys())
            all_projects.update(project_clm_estimates.keys())

            # Maintain order from existing projects list as much as possible
            ordered_projects = []
            for project in existing_projects:
                if project in all_projects:
                    ordered_projects.append(project)
                    all_projects.remove(project)

            # Add any remaining projects
            ordered_projects.extend(sorted(all_projects))

            # Result
            result = {
                'success': True,
                'project_estimates': all_project_estimates,
                'project_time_spent': all_project_time_spent,
                'project_counts': all_project_counts,
                'filtered_project_estimates': filtered_project_estimates,
                'filtered_project_time_spent': filtered_project_time_spent,
                'filtered_project_counts': filtered_project_counts,
                'project_clm_estimates': project_clm_estimates,
                'projects': ordered_projects,
                'data_source': 'clm',
                'implementation_count': len(all_implementation_issues),
                'filtered_count': len(filtered_issues)
            }

            return jsonify(result)

        except Exception as e:
            logger.error(f"Error fetching CLM chart data: {str(e)}", exc_info=True)
            return jsonify({
                'error': str(e),
                'success': False
            }), 500