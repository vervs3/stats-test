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
                    keys = [key for key in keys if key in project_issues]

                logger.info(f"Found {len(keys)} issue keys for chart type {chart_type}, project {project}")
                return keys

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

        # Add detailed logging to debug the issue
        logger.info(
            f"jql_by_project called with project={project}, date_from={date_from}, date_to={date_to}, is_clm={is_clm}")

        if is_clm and timestamp:
            # Get issue keys for this project from saved data
            issue_keys = get_issue_keys_for_clm_chart(timestamp, project, 'project_issues')

            # Additional logging
            logger.info(f"CLM mode: Found {len(issue_keys)} issue keys for project {project}")

            if issue_keys:
                # Create JQL with issue keys
                if len(issue_keys) > 100:
                    # For many issues, use a simplified JQL
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
                    # For a reasonable number of issues, explicitly list them
                    jql = f'issue in ({", ".join(issue_keys)})'
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

                    # Add date filters if specified and not ignoring period
                    if (date_from or date_to) and not ignore_period:
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

                    # If not ignoring period, add date filters
                    if (date_from or date_to) and not ignore_period:
                        date_parts = []
                        if date_from:
                            date_parts.append(f'worklogDate >= "{date_from}"')
                        if date_to:
                            date_parts.append(f'worklogDate <= "{date_to}"')

                        if date_parts:
                            jql += f' AND ({" AND ".join(date_parts)})'
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

                # Add date filters if specified and not ignoring period
                if (date_from or date_to) and not ignore_period:
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

            # Add time filters if specified and not ignoring period
            if (date_from or date_to) and not ignore_period:
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

            # Загрузка сырых данных задач
            with open(raw_issues_path, 'r', encoding='utf-8') as f:
                raw_issues = json.load(f)

            # Обрабатываем все задачи для получения полных данных
            import pandas as pd
            from modules.data_processor import process_issues_data

            # Используем функцию process_issues_data для обработки данных
            df = process_issues_data(raw_issues)

            # Готовим данные для графика
            project_estimates = df.groupby('project')['original_estimate_hours'].sum().to_dict()
            project_time_spent = df.groupby('project')['time_spent_hours'].sum().to_dict()

            # Получаем проекты для EST задач и компонентов
            project_clm_estimates = {}
            est_issue_keys = clm_keys_data.get('est_issue_keys', [])
            implementation_issue_keys = clm_keys_data.get('implementation_issue_keys', [])
            components_to_projects = {}

            # Попробуем загрузить компоненты из summary.json
            summary_path = os.path.join(folder_path, 'summary.json')
            if os.path.exists(summary_path):
                try:
                    with open(summary_path, 'r', encoding='utf-8') as f:
                        summary_data = json.load(f)
                        components_to_projects = summary_data.get('components_mapping', {})
                except Exception as e:
                    logger.error(f"Error reading summary for components mapping: {e}")

            # Если не нашли компоненты, попробуем загрузить из metrics
            if not components_to_projects:
                clm_metrics_path = os.path.join(folder_path, 'metrics', 'clm_metrics.json')
                if os.path.exists(clm_metrics_path):
                    try:
                        with open(clm_metrics_path, 'r', encoding='utf-8') as f:
                            clm_metrics = json.load(f)
                            components_to_projects = clm_metrics.get('components_mapping', {})
                    except Exception as e:
                        logger.error(f"Error reading CLM metrics for components mapping: {e}")

            # Если все еще нет компонентов, используем пустой словарь
            if not components_to_projects:
                components_to_projects = {}

            # Подгрузим chart_data.json для получения дополнительной информации
            chart_data_path = os.path.join(folder_path, 'data', 'chart_data.json')
            if os.path.exists(chart_data_path):
                try:
                    with open(chart_data_path, 'r', encoding='utf-8') as f:
                        chart_data = json.load(f)
                        # Используем имеющиеся данные CLM оценок, если они есть
                        if 'project_clm_estimates' in chart_data:
                            project_clm_estimates = chart_data['project_clm_estimates']
                except Exception as e:
                    logger.error(f"Error reading chart data: {e}")

            # Соберем полный набор проектов
            all_projects = set()
            all_projects.update(project_estimates.keys())
            all_projects.update(project_time_spent.keys())
            all_projects.update(project_clm_estimates.keys())

            # Результат
            result = {
                'success': True,
                'project_estimates': project_estimates,
                'project_time_spent': project_time_spent,
                'project_clm_estimates': project_clm_estimates,
                'projects': list(all_projects),
                'data_source': 'clm'
            }

            return jsonify(result)

        except Exception as e:
            logger.error(f"Error fetching CLM chart data: {str(e)}", exc_info=True)
            return jsonify({
                'error': str(e),
                'success': False
            }), 500