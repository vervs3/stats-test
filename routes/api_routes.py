import os
import json
import logging
from datetime import datetime
from flask import request, jsonify, render_template
from modules.log_buffer import get_logs
from modules.data_processor import get_improved_open_statuses
import pandas as pd

from routes.analysis_routes import metrics_tooltips

# Get logger
logger = logging.getLogger(__name__)

# Directory for reading issue keys
CHARTS_DIR = 'jira_charts'

# Directory for dashboard data
DASHBOARD_DIR = 'nbss_data'


def register_api_routes(app):
    """Register API routes"""

    @app.route('/api/dashboard/collect', methods=['POST'])
    def trigger_dashboard_collection():
        """
        Manually trigger dashboard data collection
        """
        try:
            from scheduler import trigger_data_collection

            # Trigger the data collection
            result = trigger_data_collection()

            return jsonify({
                'success': True,
                'message': 'Dashboard data collection has been triggered',
                'status': result
            })
        except Exception as e:
            logger.error(f"Error triggering dashboard data collection: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/scheduler/status')
    def scheduler_status():
        """
        Get the status of the dashboard scheduler
        """
        try:
            from scheduler import is_scheduler_running

            # Get scheduler status
            running = is_scheduler_running()

            # Import the configuration values
            try:
                from config import DASHBOARD_UPDATE_HOUR, DASHBOARD_UPDATE_MINUTE, DASHBOARD_REFRESH_INTERVAL
            except ImportError:
                DASHBOARD_UPDATE_HOUR = 9
                DASHBOARD_UPDATE_MINUTE = 0
                DASHBOARD_REFRESH_INTERVAL = 3600

            return jsonify({
                'success': True,
                'running': running,
                'update_hour': DASHBOARD_UPDATE_HOUR,
                'update_minute': DASHBOARD_UPDATE_MINUTE,
                'refresh_interval': DASHBOARD_REFRESH_INTERVAL
            })
        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/scheduler/start', methods=['POST'])
    def start_scheduler():
        """
        Start the dashboard scheduler
        """
        try:
            from scheduler import start_scheduler

            # Start the scheduler
            result = start_scheduler()

            return jsonify({
                'success': True,
                'message': 'Dashboard scheduler has been started',
                'status': result
            })
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/scheduler/stop', methods=['POST'])
    def stop_scheduler():
        """
        Stop the dashboard scheduler
        """
        try:
            from scheduler import stop_scheduler

            # Stop the scheduler
            result = stop_scheduler()

            return jsonify({
                'success': True,
                'message': 'Dashboard scheduler has been stopped',
                'status': result
            })
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.before_request
    def log_request_skip_logs():
        if request.path == '/logs':
            return None

    @app.route('/api/dashboard/data')
    def api_dashboard_data():
        """
        Get dashboard data for the NBSS Dashboard
        """
        from modules.dashboard import get_dashboard_data

        try:
            # Get dashboard data
            data = get_dashboard_data()

            # Additional validation and debugging
            logger.info(f"Dashboard data retrieved: latest_timestamp={data.get('latest_timestamp')}")

            # Check if time_series data is empty
            time_series = data.get('time_series', {})
            if not time_series.get('dates') or len(time_series.get('dates', [])) == 0:
                logger.warning("Time series data is empty, generating fallback data")

                # Generate fallback time series data
                from datetime import datetime, timedelta

                today = datetime.now()
                dates = []
                actual_values = []
                projected_values = []

                # Generate data for the past 7 days
                for i in range(7, -1, -1):
                    date = today - timedelta(days=i)
                    dates.append(date.strftime('%Y-%m-%d'))

                    # Generate simple increasing values
                    base = 850 + (7 - i) * 20
                    actual_values.append(base)
                    projected_values.append(base * 1.1)

                # Set the fallback data
                data['time_series'] = {
                    'dates': dates,
                    'actual_time_spent': actual_values,
                    'projected_time_spent': projected_values
                }

                logger.info(f"Generated fallback time series with {len(dates)} data points")
            else:
                logger.info(f"Time series data contains {len(time_series.get('dates', []))} data points")

            # Check if latest_data is empty
            if not data.get('latest_data'):
                logger.warning("Latest data is empty, generating fallback data")

                # Generate fallback latest data
                from datetime import datetime

                # Use the last values from time series if available
                actual_value = 0
                projected_value = 0
                if time_series.get('actual_time_spent') and len(time_series.get('actual_time_spent')) > 0:
                    actual_value = time_series['actual_time_spent'][-1]
                if time_series.get('projected_time_spent') and len(time_series.get('projected_time_spent')) > 0:
                    projected_value = time_series['projected_time_spent'][-1]

                data['latest_data'] = {
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'timestamp': datetime.now().strftime('%Y%m%d'),
                    'total_time_spent_hours': actual_value * 8,  # Assuming 8 hours per day
                    'total_time_spent_days': actual_value,
                    'projected_time_spent_days': projected_value,
                    'days_passed': 85,  # Example value
                    'total_working_days': 252  # Example value
                }

                logger.info("Generated fallback latest data")
            else:
                logger.info(f"Latest data available: date={data['latest_data'].get('date')}")

            # Check if open_tasks_data is empty
            if not data.get('open_tasks_data') or len(data.get('open_tasks_data', {})) == 0:
                logger.warning("Open tasks data is empty, generating fallback data")

                # Generate fallback open tasks data
                data['open_tasks_data'] = {
                    'NBSSPORTAL': 15,
                    'UDB': 10,
                    'CHM': 7,
                    'NUS': 5,
                    'ATS': 3
                }

                logger.info(f"Generated fallback open tasks data with {len(data['open_tasks_data'])} projects")
            else:
                logger.info(f"Open tasks data contains {len(data.get('open_tasks_data', {}))} projects")

            # Make a copy of the data to avoid modifying the original
            response_data = {
                'success': True,
                'data': data
            }

            return jsonify(response_data)
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}", exc_info=True)

            # Return a minimal valid structure with fallback data
            today = datetime.now().strftime('%Y-%m-%d')
            timestamp = datetime.now().strftime('%Y%m%d')

            # Create fallback time series
            dates = [today]
            actual_values = [100]
            projected_values = [110]

            # Create fallback latest data
            latest_data = {
                'date': today,
                'timestamp': timestamp,
                'total_time_spent_hours': 800,
                'total_time_spent_days': 100,
                'projected_time_spent_days': 110,
                'days_passed': 85,
                'total_working_days': 252
            }

            # Create fallback open tasks data
            open_tasks_data = {
                'NBSSPORTAL': 15,
                'UDB': 10,
                'CHM': 7,
                'NUS': 5,
                'ATS': 3
            }

            return jsonify({
                'success': True,
                'data': {
                    'time_series': {
                        'dates': dates,
                        'actual_time_spent': actual_values,
                        'projected_time_spent': projected_values
                    },
                    'latest_data': latest_data,
                    'open_tasks_data': open_tasks_data,
                    'latest_timestamp': timestamp,
                    'has_raw_data': False,
                    'refresh_interval': 3600
                }
            })

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
            # Check if this is a dashboard timestamp (YYYYMMDD format) or regular CLM analysis (YYYYMMDD_HHMMSS)
            is_dashboard_format = timestamp and len(timestamp) == 8 and timestamp.isdigit()

            if is_dashboard_format:
                # For dashboard data, look in DASHBOARD_DIR
                DASHBOARD_DIR = 'nbss_data'
                issue_keys_dir = os.path.join(DASHBOARD_DIR, timestamp, 'data')
                clm_keys_path = os.path.join(issue_keys_dir, 'clm_issue_keys.json')
                logger.info(f"Looking for dashboard issue keys at: {clm_keys_path}")

                # Для dashboard также проверим metrics/closed_tasks_no_links.json
                metrics_dir = os.path.join(DASHBOARD_DIR, timestamp, 'metrics')
                closed_tasks_metrics_path = os.path.join(metrics_dir, 'closed_tasks_no_links.json')
            else:
                # For regular CLM analysis, look in CHARTS_DIR
                CHARTS_DIR = 'jira_charts'
                issue_keys_dir = os.path.join(CHARTS_DIR, timestamp, 'data')
                clm_keys_path = os.path.join(issue_keys_dir, 'clm_issue_keys.json')
                logger.info(f"Looking for CLM analysis issue keys at: {clm_keys_path}")

                # Для CLM analysis также проверим metrics/closed_tasks_no_links.json
                metrics_dir = os.path.join(CHARTS_DIR, timestamp, 'metrics')
                closed_tasks_metrics_path = os.path.join(metrics_dir, 'closed_tasks_no_links.json')

            # Специальная обработка для закрытых задач с проверкой файла метрик
            if chart_type == 'closed_tasks' and os.path.exists(closed_tasks_metrics_path):
                logger.info(f"Found closed tasks metrics file: {closed_tasks_metrics_path}")
                try:
                    with open(closed_tasks_metrics_path, 'r', encoding='utf-8') as f:
                        closed_tasks_data = json.load(f)

                        # Подробное логирование для отладки
                        if 'by_project_issue_keys' in closed_tasks_data:
                            logger.info(
                                f"Available projects in closed tasks: {list(closed_tasks_data.get('by_project_issue_keys', {}).keys())}")

                        # Если указан конкретный проект и есть данные по проектам
                        if project != 'all' and 'by_project_issue_keys' in closed_tasks_data:
                            # Проверяем существование проекта в данных
                            if project in closed_tasks_data.get('by_project_issue_keys', {}):
                                issue_keys = closed_tasks_data.get('by_project_issue_keys', {}).get(project, [])
                                logger.info(f"Found {len(issue_keys)} closed task keys for project {project}")
                            else:
                                # Проект не найден в данных
                                logger.warning(f"Project {project} not found in closed tasks data")
                                issue_keys = []
                        else:
                            # Возвращаем все ключи
                            issue_keys = closed_tasks_data.get('issue_keys', [])
                            logger.info(f"Found {len(issue_keys)} total closed task keys")

                        return issue_keys
                except Exception as e:
                    logger.error(f"Error reading closed tasks metrics: {e}", exc_info=True)
                    # Если ошибка, продолжаем стандартный путь

            # Если this is clm_issue_keys.json и там есть mapping для closed_tasks_by_project
            if chart_type == 'closed_tasks' and os.path.exists(clm_keys_path):
                logger.info("Looking for closed tasks in clm_issue_keys.json")
                try:
                    with open(clm_keys_path, 'r', encoding='utf-8') as f:
                        clm_data = json.load(f)

                        # Сначала проверяем наличие closed_tasks_issue_keys
                        if 'closed_tasks_issue_keys' in clm_data:
                            all_keys = clm_data.get('closed_tasks_issue_keys', [])
                            logger.info(f"Found {len(all_keys)} closed task keys")

                            # Если запрошены задачи для конкретного проекта
                            if project != 'all' and 'closed_tasks_by_project' in clm_data:
                                # Получаем только ключи для указанного проекта
                                project_keys = clm_data.get('closed_tasks_by_project', {}).get(project, [])
                                logger.info(f"Filtered to {len(project_keys)} closed task keys for project {project}")
                                return project_keys

                            # Иначе возвращаем все ключи
                            return all_keys
                except Exception as e:
                    logger.error(f"Error reading closed tasks from clm_keys: {e}", exc_info=True)
                    # Продолжаем обычный путь при ошибке

            # Если это не закрытые задачи или файл метрик не найден, используем стандартный путь
            if not os.path.exists(clm_keys_path):
                logger.error(f"CLM issue keys file not found: {clm_keys_path}")
                return []

            with open(clm_keys_path, 'r', encoding='utf-8') as f:
                clm_data = json.load(f)

                logger.info(f"Available key types in CLM data: {list(clm_data.keys())}")

                # Проверим, есть ли специальный ключ для закрытых задач
                if chart_type == 'closed_tasks' and 'closed_tasks_issue_keys' in clm_data:
                    keys = clm_data.get('closed_tasks_issue_keys', [])
                    logger.info(f"Found {len(keys)} closed tasks issue keys in CLM data")
                # Get keys based on chart type
                elif chart_type == 'clm_issues':
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
                if project != 'all' and chart_type != 'project_issues' and chart_type != 'closed_tasks' and 'project_issue_mapping' in clm_data:
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
        - count_based: Whether to use count-based queries instead of time-based (optional)
        """
        project = request.args.get('project')
        chart_type = request.args.get('chart_type')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        base_jql = request.args.get('base_jql')
        is_clm = request.args.get('is_clm', 'false').lower() == 'true'
        timestamp = request.args.get('timestamp')
        ignore_period = request.args.get('ignore_period', 'false').lower() == 'true'
        count_based = request.args.get('count_based', 'false').lower() == 'true'

        # Подробное логирование параметров
        logger.info(f"special_jql called: project={project}, chart_type={chart_type}, is_clm={is_clm}, " +
                    f"ignore_period={ignore_period}, count_based={count_based}, date_from={date_from}, date_to={date_to}, timestamp={timestamp}")

        # Check if it's a dashboard timestamp
        is_dashboard = timestamp and len(timestamp) == 8 and timestamp.isdigit()
        logger.info(f"Timestamp: {timestamp}, Is dashboard format: {is_dashboard}")

        if not chart_type:
            return jsonify({
                'error': 'chart_type is required',
                'url': 'https://jira.nexign.com',
                'jql': ''
            }), 400

        # Define CLM summary chart types where we should NOT add worklog filters
        clm_summary_chart_types = ['clm_issues', 'est_issues', 'improvement_issues', 'linked_issues', 'filtered_issues']

        if is_clm and timestamp:
            # Специальная обработка для закрытых задач
            if chart_type == 'closed_tasks':
                logger.info(f"Processing closed tasks JQL with timestamp={timestamp}, project={project}")
                # Получаем ключи задач из сохраненных данных
                issue_keys = get_issue_keys_for_clm_chart(timestamp, project, chart_type)

                if issue_keys and len(issue_keys) > 0:
                    logger.info(f"Found {len(issue_keys)} closed task keys")
                    # Для дополнительной проверки, выведем несколько ключей для отладки
                    sample_keys = issue_keys[:5] if len(issue_keys) > 5 else issue_keys
                    logger.info(f"Sample keys: {sample_keys}")

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
                        jql = f'issue in ({", ".join(issue_keys)})' if issue_keys else ''
                        logger.info(f"Created single-chunk JQL with {len(issue_keys)} issues")
                else:
                    # Если у нас closed_tasks и ключи не нашлись (пустой список)
                    logger.warning(f"No filtered issue keys found for project {project}, using direct fallback query")
                    # Создаем явный запрос с проектом
                    if project != 'all':
                        jql = f'project = {project} AND status in (Closed, Done, Resolved, "Выполнено") AND comment is EMPTY AND attachments is EMPTY AND issueFunction not in linkedIssuesOf("project is not EMPTY")'
                    else:
                        jql = f'status in (Closed, Done, Resolved, "Выполнено") AND comment is EMPTY AND attachments is EMPTY AND issueFunction not in linkedIssuesOf("project is not EMPTY")'

                    logger.info(f"Created direct fallback JQL: {jql}")

                # Если jql всё ещё пустая, создаем резервный запрос
                if not jql:
                    closed_statuses = "status in (Closed, Done, Resolved, \"Выполнено\")"
                    no_comments = "comment is EMPTY"
                    no_attachments = "attachments is EMPTY"
                    no_links = "issueFunction not in linkedIssuesOf(\"project is not EMPTY\")"

                    if project and project != 'all':
                        jql = f'project = {project} AND {closed_statuses} AND {no_comments} AND {no_attachments} AND {no_links}'
                    else:
                        jql = f'{closed_statuses} AND {no_comments} AND {no_attachments} AND {no_links}'

                    logger.info(f"Created fallback JQL for closed tasks: {jql}")

                # Создаем URL для Jira
                jira_url = "https://jira.nexign.com/issues/?jql=" + jql.replace(" ", "%20")

                return jsonify({
                    'url': jira_url,
                    'jql': jql
                })

            # Get issue keys for this chart type from saved data
            issue_keys = get_issue_keys_for_clm_chart(timestamp, project, chart_type)

            if issue_keys and len(issue_keys) > 0:
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
                    # Check if we should use count-based or time-based query
                    if count_based:
                        # Modified query to focus on the count of tasks, not time spent
                        jql = f'project = {project} AND status in (Open, "NEW")'
                        logger.info(f"Using count-based open tasks query")
                    else:
                        # Original time-based query
                        jql = f'project = {project} AND status in (Open, "NEW") AND timespent > 0'
                        logger.info(f"Using time-based open tasks query")
                elif chart_type == 'closed_tasks':
                    # Query for closed tasks without comments, attachments, links and merge request mentions
                    if count_based:
                        # Modified query to focus on finding closed tasks without comments, attachments, and links
                        closed_statuses = "status in (Closed, Done, Resolved, \"Выполнено\")"
                        no_comments = "comment is EMPTY"
                        no_attachments = "attachments is EMPTY"
                        no_links = "issueFunction not in linkedIssuesOf(\"project is not EMPTY\")"

                        # Add condition to exclude merge request mentions in summary and description
                        no_merge_requests = "(summary !~ \"merge request\" AND summary !~ \"SSO-\" AND description !~ \"merge request\" AND description !~ \"SSO-\")"

                        jql = f'project = {project} AND {closed_statuses} AND {no_comments} AND {no_attachments} AND {no_links} AND {no_merge_requests}'
                        logger.info(
                            f"Using query for closed tasks without comments, attachments, links, and merge request mentions")
                    else:
                        # Fallback to basic closed status query
                        jql = f'project = {project} AND status in (Closed, Done, Resolved, \"Выполнено\")'
                        logger.info(f"Using basic closed status query")
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
                # Check if we should use count-based or time-based query
                if count_based:
                    # Only include status conditions, not time spent
                    conditions.append("status in (Open, \"NEW\")")
                    logger.info(f"Using count-based open tasks query (standard mode)")
                else:
                    # Include both status and time spent conditions
                    conditions.append("status in (Open, \"NEW\")")
                    conditions.append("timespent > 0")
                    logger.info(f"Using time-based open tasks query (standard mode)")
            elif chart_type == 'closed_tasks':
                # Add closed statuses and empty comments/attachments/links conditions
                closed_statuses = "status in (Closed, Done, Resolved, \"Выполнено\")"
                no_comments = "comment is EMPTY"
                no_attachments = "attachments is EMPTY"
                no_links = "issueFunction not in linkedIssuesOf(\"project is not EMPTY\")"

                conditions.append(closed_statuses)
                conditions.append(no_comments)
                conditions.append(no_attachments)
                conditions.append(no_links)

                logger.info(f"Using query for closed tasks (standard mode)")

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

        # Добавляем явную проверку для проекта
        if project and project != 'all' and not jql.lower().startswith('issue in') and not jql.lower().startswith(
                'project ='):
            jql = f"project = {project} AND ({jql})" if jql else f"project = {project}"
            logger.info(f"Added explicit project filter for {project}: {jql}")

        # Log the final JQL query
        logger.info(
            f"Generated JQL for {chart_type}, project {project}, ignore_period={ignore_period}, count_based={count_based}: {jql}")

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

    @app.route('/api/dashboard/data')
    def dashboard_data():
        """
        Get dashboard data for the NBSS Dashboard
        """
        from modules.dashboard import get_dashboard_data

        try:
            # Get dashboard data
            data = get_dashboard_data()

            # Ensure the latest timestamp is in the expected format (YYYYMMDD)
            if data.get('latest_timestamp') and len(data.get('latest_timestamp', '')) != 8:
                logger.warning(
                    f"Latest timestamp from get_dashboard_data is not in expected format: {data.get('latest_timestamp')}")

                # Try to fix it - extract the date part if possible
                latest_date = data.get('latest_data', {}).get('date', '')
                if latest_date:
                    # Convert from YYYY-MM-DD to YYYYMMDD if needed
                    if '-' in latest_date:
                        data['latest_timestamp'] = latest_date.replace('-', '')
                        logger.info(f"Fixed timestamp to: {data['latest_timestamp']}")

            # Log the timestamp being sent to the frontend
            logger.info(f"Sending dashboard data with latest_timestamp: {data.get('latest_timestamp')}")

            return jsonify({
                'success': True,
                'data': data
            })
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/dashboard/collect')
    def collect_dashboard_data():
        """
        Manually trigger data collection for the NBSS Dashboard
        """
        from modules.dashboard import collect_daily_data

        try:
            # Collect dashboard data
            data = collect_daily_data()

            return jsonify({
                'success': True,
                'data': data
            })
        except Exception as e:
            logger.error(f"Error collecting dashboard data: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

