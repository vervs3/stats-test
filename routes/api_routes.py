import logging
from flask import request, jsonify
from modules.log_buffer import get_logs
from modules.data_processor import get_improved_open_statuses
import pandas as pd

# Get logger
logger = logging.getLogger(__name__)


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

    @app.route('/jql/project/<project>')
    def jql_by_project(project):
        """Generate JQL for filtering by project and redirect to Jira"""
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        base_jql = request.args.get('base_jql')
        is_clm = request.args.get('is_clm', 'false').lower() == 'true'

        if is_clm:
            # В режиме CLM используем другую логику формирования запроса
            if base_jql and base_jql.startswith('filter='):
                # Извлекаем ID фильтра из base_jql
                clm_filter_id = base_jql.replace('filter=', '')

                # Формируем JQL для проекта, связанного с CLM
                jql = f'project = {project} AND issue in linkedIssuesOfRecursive("filter = {clm_filter_id}")'

                # Добавляем фильтрацию по дате, если указана
                if date_from or date_to:
                    date_parts = []
                    if date_from:
                        date_parts.append(f'worklogDate >= "{date_from}"')
                    if date_to:
                        date_parts.append(f'worklogDate <= "{date_to}"')

                    if date_parts:
                        jql += f' AND ({" AND ".join(date_parts)})'
            else:
                # Если нет фильтра CLM, используем обычный запрос по проекту
                jql = f'project = {project}'

                if date_from or date_to:
                    date_parts = []
                    if date_from:
                        date_parts.append(f'worklogDate >= "{date_from}"')
                    if date_to:
                        date_parts.append(f'worklogDate <= "{date_to}"')

                    if date_parts:
                        jql += f' AND ({" AND ".join(date_parts)})'
        else:
            # Стандартная логика для обычного режима Jira
            # Start with project
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
        - chart_type: Type of chart (open_tasks)
        - date_from: Start date (optional)
        - date_to: End date (optional)
        - base_jql: Base JQL query (optional)
        - is_clm: Whether this is a CLM analysis (optional)
        """
        project = request.args.get('project')
        chart_type = request.args.get('chart_type')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        base_jql = request.args.get('base_jql')
        is_clm = request.args.get('is_clm', 'false').lower() == 'true'

        if not project or not chart_type:
            return jsonify({
                'error': 'Project and chart_type are required',
                'url': 'https://jira.nexign.com',
                'jql': ''
            }), 400

        if is_clm:
            # Логика для режима CLM
            if base_jql and base_jql.startswith('filter='):
                # Извлекаем ID фильтра из base_jql
                clm_filter_id = base_jql.replace('filter=', '')

                if chart_type == 'open_tasks':
                    # Запрос для "Открытые задачи со списаниями" в режиме CLM
                    jql = f'project = {project} AND issue in linkedIssuesOfRecursive("filter = {clm_filter_id}") AND status in (Open, "NEW") AND timespent > 0'

                    if date_from or date_to:
                        date_parts = []
                        if date_from:
                            date_parts.append(f'worklogDate >= "{date_from}"')
                        if date_to:
                            date_parts.append(f'worklogDate <= "{date_to}"')

                        if date_parts:
                            jql += f' AND ({" AND ".join(date_parts)})'
                else:
                    # Для других типов графиков в режиме CLM
                    jql = f'project = {project} AND issue in linkedIssuesOfRecursive("filter = {clm_filter_id}")'

                    if date_from or date_to:
                        date_parts = []
                        if date_from:
                            date_parts.append(f'worklogDate >= "{date_from}"')
                        if date_to:
                            date_parts.append(f'worklogDate <= "{date_to}"')

                        if date_parts:
                            jql += f' AND ({" AND ".join(date_parts)})'
            else:
                # Если нет фильтра CLM, используем обычный запрос по проекту
                if chart_type == 'open_tasks':
                    jql = f'project = {project} AND status in (Open, "NEW") AND timespent > 0'
                else:
                    jql = f'project = {project}'

                if date_from or date_to:
                    date_parts = []
                    if date_from:
                        date_parts.append(f'worklogDate >= "{date_from}"')
                    if date_to:
                        date_parts.append(f'worklogDate <= "{date_to}"')

                    if date_parts:
                        jql += f' AND ({" AND ".join(date_parts)})'
        else:
            # Стандартная логика для обычного режима
            # Условия для проекта
            conditions = [f"project = {project}"]

            # Добавление условий в зависимости от типа графика
            if chart_type == 'open_tasks':
                # Запрос для "Открытые задачи со списаниями"
                # Используем функцию из data_processor для получения открытых статусов
                # Для получения списка открытых статусов нам нужны данные
                # Создадим пустой DataFrame с нужными колонками, просто чтобы использовать функцию
                try:
                    # Стандартный список открытых статусов для резервного использования
                    default_open_statuses = ["Open", "NEW"]

                    # Форматируем список статусов для JQL
                    status_condition = "status in (" + ", ".join(
                        [f'"{status}"' for status in default_open_statuses]) + ")"
                    conditions.append(status_condition)
                except Exception as e:
                    logger.error(f"Error generating open statuses for JQL: {str(e)}")
                    # В случае ошибки используем стандартный набор
                    conditions.append("status in (Open, \"NEW\")")

                conditions.append("timespent > 0")

                # Добавление временных ограничений для списаний
                if date_from or date_to:
                    temp_conditions = []
                    if date_from:
                        temp_conditions.append(f"worklogDate >= \"{date_from}\"")
                    if date_to:
                        temp_conditions.append(f"worklogDate <= \"{date_to}\"")
                    conditions.append(f"({' AND '.join(temp_conditions)})")

            # Если есть базовый JQL, добавляем его условия
            if base_jql:
                final_jql = f"({base_jql}) AND ({' AND '.join(conditions)})"
            else:
                final_jql = ' AND '.join(conditions)

            jql = final_jql

        # Создаем URL для Jira
        jira_url = "https://jira.nexign.com/issues/?jql=" + jql.replace(" ", "%20")

        # Логирование созданного запроса
        logger.info(f"Generated special JQL for {chart_type}, project {project}: {jql}")

        return jsonify({
            'url': jira_url,
            'jql': jql
        })