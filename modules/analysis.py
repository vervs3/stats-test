import os
import json
import logging
from datetime import datetime
from routes.main_routes import analysis_state
from modules.jira_analyzer import JiraAnalyzer
from modules.data_processor import get_improved_open_statuses, get_status_categories

# Get logger
logger = logging.getLogger(__name__)

# Directory for saving charts
CHARTS_DIR = 'jira_charts'


def prepare_chart_data(df, data_source='jira', use_filter=True, filter_id=None, jql_query=None,
                       date_from=None, date_to=None, clm_filter_id=None, clm_jql_query=None,
                       clm_metrics=None, clm_issues=None, est_issues=None, improvement_issues=None,
                       implementation_issues=None, filtered_issues=None, components_to_projects=None):
    """
    Prepare chart data for interactive charts with special attention to special charts

    Args:
        df (pandas.DataFrame): Processed data frame
        data_source (str): Data source ('jira' or 'clm')
        use_filter (bool): Whether filter ID was used
        filter_id: ID of the filter used
        jql_query: JQL query used
        date_from: From date
        date_to: To date
        clm_filter_id: ID of the CLM filter used
        clm_jql_query: CLM JQL query used
        clm_metrics: CLM-specific metrics
        clm_issues: List of CLM issues (optional)
        est_issues: List of EST issues (optional)
        improvement_issues: List of improvement issues (optional)
        implementation_issues: List of implementation issues (optional)
        filtered_issues: List of filtered issues (optional)
        components_to_projects: Mapping of EST components to projects (optional)

    Returns:
        dict: Chart data for interactive charts
    """
    import logging
    from modules.data_processor import get_status_categories, get_improved_open_statuses
    import json

    logger = logging.getLogger(__name__)

    try:
        # IMPROVED: If we're in CLM mode and have filtered_issues, use their keys for filtering
        if data_source == 'clm' and filtered_issues:
            # Get the keys of all filtered issues for CLM mode
            filtered_issue_keys = set([issue.get('key') for issue in filtered_issues if issue.get('key')])
            logger.info(f"Filtering chart data to {len(filtered_issue_keys)} CLM-related issues")

            # Filter the DataFrame to only include these issues
            if not df.empty and 'issue_key' in df.columns and filtered_issue_keys:
                # Apply the filter only if we have data
                filtered_df = df[df['issue_key'].isin(filtered_issue_keys)]
                logger.info(f"Filtered from {len(df)} to {len(filtered_df)} rows for chart data")
                # Use the filtered DataFrame for all subsequent operations
                df = filtered_df

        # Project data from the (potentially filtered) DataFrame
        project_counts = df['project'].value_counts().to_dict()
        project_estimates = df.groupby('project')['original_estimate_hours'].sum().to_dict()
        project_time_spent = df.groupby('project')['time_spent_hours'].sum().to_dict()

        # Generate the list of all projects
        all_projects = list(set(list(project_counts.keys()) +
                                list(project_estimates.keys()) +
                                list(project_time_spent.keys())))

        logger.info(f"Prepared basic chart data with {len(all_projects)} projects")

        # Extract issue keys by project for JQL generation
        project_issue_mapping = {}
        for project in all_projects:
            project_df = df[df['project'] == project]
            project_issue_mapping[project] = project_df['issue_key'].tolist()

        logger.info(f"Created project-to-issues mapping for {len(project_issue_mapping)} projects")

        # НОВОЕ: Добавление CLM оценок из EST тикетов
        project_clm_estimates = {}
        if data_source == 'clm' and est_issues and components_to_projects:
            logger.info(f"Calculating CLM estimates from {len(est_issues)} EST issues")

            # Используем указанное поле для Estimation man-days (cf[12307])
            est_estimation_field = 'customfield_12307'
            logger.info(f"Using specified EST estimation field: {est_estimation_field}")

            # Выводим информацию о маппинге компонентов
            logger.info("DEBUG: Component to project mapping: ")
            for component, projects in components_to_projects.items():
                if projects:  # только показываем компоненты, для которых есть проекты
                    logger.info(f"DEBUG: Component {component} maps to projects: {projects}")

            # Подробная информация о EST тикетах и их оценках
            for i, issue in enumerate(est_issues):
                issue_key = issue.get('key', 'unknown')
                components_raw = issue.get('fields', {}).get('components', [])
                components = [comp.get('name', '') for comp in components_raw if comp.get('name', '')]

                # Получаем значение поля customfield_12307
                estimation_raw = issue.get('fields', {}).get(est_estimation_field)
                est_value = None

                if estimation_raw is not None:
                    try:
                        est_value = float(estimation_raw)
                    except (ValueError, TypeError):
                        est_value = "Error: Non-numeric"

                logger.info(
                    f"DEBUG: EST issue #{i + 1}: {issue_key}, Components: {components}, Raw estimation: {estimation_raw}, Parsed: {est_value}")

            # Обработка каждого EST тикета
            for issue in est_issues:
                issue_key = issue.get('key', 'unknown')
                # Получаем компоненты задачи
                components = []
                for comp in issue.get('fields', {}).get('components', []):
                    comp_name = comp.get('name', '')
                    if comp_name:
                        components.append(comp_name)

                # Получаем оценку в человекоднях
                DEFAULT_MANDAYS = 3.0  # Значение по умолчанию для задач без оценки
                estimation_days = issue.get('fields', {}).get(est_estimation_field)

                # Если нет оценки в поле, используем значение по умолчанию
                if estimation_days is None:
                    estimation_days = DEFAULT_MANDAYS
                    logger.info(f"EST issue {issue_key} has no estimation, using default {DEFAULT_MANDAYS} man-days")

                try:
                    # Преобразуем значение в число (если строка или сложный объект)
                    if not isinstance(estimation_days, (int, float)):
                        try:
                            estimation_days = float(estimation_days)
                        except (ValueError, TypeError):
                            logger.warning(f"Cannot convert estimation value {estimation_days} to float, using default")
                            estimation_days = DEFAULT_MANDAYS

                    # Преобразуем человекодни в часы (1 человекодень = 8 часов)
                    estimation_hours = estimation_days * 8.0

                    # Для каждого компонента найдем связанные проекты
                    mapped_projects = set()
                    for component in components:
                        component_projects = components_to_projects.get(component, [])
                        if component_projects:
                            mapped_projects.update(component_projects)
                            logger.info(f"Mapped component {component} to projects: {component_projects}")

                    # Распределяем оценку по проектам, если маппинг найден
                    if mapped_projects:
                        hours_per_project = estimation_hours / len(mapped_projects)
                        logger.info(
                            f"EST {issue_key}: Distributing {estimation_hours} hours across {len(mapped_projects)} projects: {mapped_projects}")

                        for project in mapped_projects:
                            if project in project_clm_estimates:
                                project_clm_estimates[project] += hours_per_project
                            else:
                                project_clm_estimates[project] = hours_per_project

                except Exception as e:
                    logger.error(f"Error processing EST issue {issue_key}: {str(e)}", exc_info=True)

            # Выводим итоговые оценки по проектам
            if project_clm_estimates:
                logger.info(f"Final CLM estimates by project: {project_clm_estimates}")
            else:
                logger.warning("No CLM estimates were calculated for any project")

        # Special chart 1: No transitions tasks data (переименован в "Открытые задачи со списаниями")
        no_transitions_tasks = df[df['no_transitions'] == True]
        no_transitions_by_project = {}
        if not no_transitions_tasks.empty:
            try:
                no_transitions_by_project = no_transitions_tasks.groupby('project').size().to_dict()
                logger.info(f"Prepared open tasks with worklogs data with {len(no_transitions_by_project)} projects")

                # Store the open task issue keys by project
                open_tasks_by_project = {}
                for project in no_transitions_by_project.keys():
                    project_open_tasks = no_transitions_tasks[no_transitions_tasks['project'] == project]
                    open_tasks_by_project[project] = project_open_tasks['issue_key'].tolist()
            except Exception as e:
                logger.error(f"Error preparing open tasks with worklogs data: {str(e)}")
                # Provide an empty dict in case of error
                no_transitions_by_project = {}
                open_tasks_by_project = {}
        else:
            logger.info("Open tasks with worklogs dataset is empty")
            open_tasks_by_project = {}

        # Make sure we handle empty DataFrames gracefully
        no_transitions_count = len(no_transitions_tasks) if 'no_transitions_tasks' in locals() else 0

        # Save data for interactive charts
        chart_data = {
            'project_counts': project_counts,
            'project_estimates': project_estimates,
            'project_time_spent': project_time_spent,
            'project_clm_estimates': project_clm_estimates,  # Добавляем CLM оценки
            'projects': all_projects,
            'data_source': data_source,
            'filter_params': {
                'filter_id': filter_id if use_filter and data_source == 'jira' else None,
                'jql': jql_query if not use_filter and data_source == 'jira' else None,
                'clm_filter_id': clm_filter_id if use_filter and data_source == 'clm' else None,
                'clm_jql': clm_jql_query if not use_filter and data_source == 'clm' else None,
                'date_from': date_from,
                'date_to': date_to
            },
            # Add special chart data - ensure this is always included
            'special_charts': {
                'no_transitions': {
                    'title': 'Открытые задачи со списаниями',
                    'by_project': no_transitions_by_project,
                    'total': no_transitions_count,
                    'issue_keys_by_project': open_tasks_by_project if 'open_tasks_by_project' in locals() else {}
                }
            },
            # Add project to issue mapping for precise JQL generation
            'project_issue_mapping': project_issue_mapping
        }

        # Add CLM specific data if available
        if data_source == 'clm' and clm_metrics:
            chart_data['clm_metrics'] = clm_metrics

            # Add specific issue key collections if they exist
            if clm_issues:
                chart_data['clm_issue_keys'] = [issue.get('key') for issue in clm_issues if issue.get('key')]
            if est_issues:
                chart_data['est_issue_keys'] = [issue.get('key') for issue in est_issues if issue.get('key')]
            if improvement_issues:
                chart_data['improvement_issue_keys'] = [issue.get('key') for issue in improvement_issues if
                                                        issue.get('key')]
            if implementation_issues:
                chart_data['implementation_issue_keys'] = [issue.get('key') for issue in implementation_issues if
                                                           issue.get('key')]
            if filtered_issues:
                chart_data['filtered_issue_keys'] = [issue.get('key') for issue in filtered_issues if issue.get('key')]

        logger.info("Chart data preparation complete")
        return chart_data

    except Exception as e:
        logger.error(f"Error in prepare_chart_data: {str(e)}", exc_info=True)
        # Return a minimal valid structure if any error occurs
        return {
            'project_counts': {},
            'project_estimates': {},
            'project_time_spent': {},
            'projects': [],
            'data_source': data_source,
            'filter_params': {},
            'special_charts': {
                'no_transitions': {'title': 'Открытые задачи со списаниями', 'by_project': {}, 'total': 0}
            }
        }


def run_analysis(data_source='jira', use_filter=True, filter_id=114476, jql_query=None, date_from=None, date_to=None,
                 clm_filter_id=114473, clm_jql_query=None):
    """
    Run Jira data analysis in a separate thread

    FIXED: Proper handling of filter_id and JQL parameters

    Args:
        data_source (str): Data source ('jira' or 'clm')
        use_filter (bool): Whether to use filter ID or JQL query
        filter_id (str/int): ID of Jira filter to use
        jql_query (str): JQL query to use instead of filter ID
        date_from (str): Start date for worklog filtering (YYYY-MM-DD)
        date_to (str): End date for worklog filtering (YYYY-MM-DD)
        clm_filter_id (str/int): ID of CLM filter to use
        clm_jql_query (str): CLM JQL query to use instead of filter ID
    """
    global analysis_state

    # Инициализируем components_to_projects в начале функции, чтобы избежать ошибки
    # "referenced before assignment"
    components_to_projects = {}

    try:
        analysis_state['is_running'] = True
        analysis_state['progress'] = 0
        analysis_state['status_message'] = 'Initialization...'

        # Create timestamp folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(CHARTS_DIR, timestamp)
        analysis_state['current_folder'] = timestamp

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Create directory for JSON data
        data_dir = os.path.join(output_dir, 'data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        # Create directory for metrics
        metrics_dir = os.path.join(output_dir, 'metrics')
        if not os.path.exists(metrics_dir):
            os.makedirs(metrics_dir)

        # Initialize Jira analyzer
        analyzer = JiraAnalyzer()

        # Get the right query based on data source
        clm_metrics = None
        final_jql = ""

        # These variables will store issues for CLM mode
        clm_issues = []
        est_issues = []
        improvement_issues = []
        implementation_issues = []
        filtered_issues = []

        if data_source == 'jira':
            # Standard Jira analysis
            if use_filter:
                # Ensure filter_id is a string
                filter_id_str = str(filter_id)
                final_jql = f'filter={filter_id_str}'
                logger.info(f"JIRA mode: Using filter ID: {filter_id_str}")
            else:
                final_jql = jql_query or ""
                logger.info(f"JIRA mode: Using JQL query: {final_jql}")
        else:
            # CLM analysis
            analysis_state['status_message'] = 'Processing CLM data...'

            # Get CLM issues first
            if use_filter:
                # Ensure clm_filter_id is a string
                clm_filter_id_str = str(clm_filter_id)
                clm_query = f'project = CLM AND filter={clm_filter_id_str}'
                logger.info(f"CLM mode: Using filter ID: {clm_filter_id_str}")
            else:
                clm_query = clm_jql_query or "project = CLM"
                logger.info(f"CLM mode: Using JQL query: {clm_query}")

            analysis_state['status_message'] = f'Fetching CLM issues with query: {clm_query}'
            analysis_state['progress'] = 5

            # Get CLM issues
            clm_issues = analyzer.get_issues_by_filter(jql_query=clm_query)
            clm_count = len(clm_issues)
            analysis_state['status_message'] = f'Found {clm_count} CLM issues'

            # Get CLM issues
            clm_issues = analyzer.get_issues_by_filter(jql_query=clm_query)
            clm_count = len(clm_issues)
            analysis_state['status_message'] = f'Found {clm_count} CLM issues'

            if not clm_issues:
                analysis_state['status_message'] = "No CLM issues found. Check query or credentials."
                analysis_state['is_running'] = False
                return

            # Get related issues using the improved method
            analysis_state['status_message'] = 'Fetching related EST, Improvement and implementation issues...'
            analysis_state['progress'] = 25

            est_issues, improvement_issues, implementation_issues = analyzer.get_clm_related_issues(clm_issues)

            est_count = len(est_issues)
            improvement_count = len(improvement_issues)
            implementation_count = len(implementation_issues)

            analysis_state[
                'status_message'] = f'Found {est_count} EST issues, {improvement_count} Improvement issues, and {implementation_count} implementation issues'
            analysis_state['progress'] = 40

            # Extract all unique projects from implementation issues
            implementation_projects = set()
            for issue in implementation_issues:
                project_key = issue.get('fields', {}).get('project', {}).get('key', '')
                if project_key:
                    implementation_projects.add(project_key)

            analysis_state[
                'status_message'] = f'Found {len(implementation_projects)} unique projects in implementation issues'

            # Обновление проектов и их задач для более точного фильтрования
            project_issue_mapping = {}
            project_implementation_mapping = {}

            # Extract issue keys by project
            project_issue_mapping = {}
            for issue in implementation_issues:
                issue_key = issue.get('key')
                project_key = issue.get('fields', {}).get('project', {}).get('key', '')
                if issue_key and project_key:
                    if project_key not in project_issue_mapping:
                        project_issue_mapping[project_key] = []
                    project_issue_mapping[project_key].append(issue_key)

            # Store ALL implementation issues in raw_issues_all.json for later use
            raw_issues_all_path = os.path.join(output_dir, 'raw_issues_all.json')
            with open(raw_issues_all_path, 'w', encoding='utf-8') as f:
                json.dump(implementation_issues, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved all {len(implementation_issues)} implementation issues to {raw_issues_all_path}")

            # Get implementation issue keys
            implementation_keys = [issue.get('key') for issue in implementation_issues if issue.get('key')]

            # Filter by dates if specified
            if date_from or date_to:
                date_conditions = []
                if date_from:
                    date_conditions.append(f'worklogDate >= "{date_from}"')
                if date_to:
                    date_conditions.append(f'worklogDate <= "{date_to}"')

                date_query = ' AND '.join(date_conditions)

                # Get issues with worklog for the specified period across ALL implementation projects
                analysis_state['status_message'] = f'Filtering issues by worklog date: {date_query}'

                # For each project, get tasks with worklog in the specified period
                filtered_issues = []
                total_issues_count = 0
                batch_size = 50

                if implementation_keys:
                    # Делаем фильтрацию на основе ключей задач, а не только по проектам
                    # Это обеспечит, что мы получим только тикеты связанные с нашими CLM и их сабтаски
                    for i in range(0, len(implementation_keys), batch_size):
                        batch = implementation_keys[i:i + batch_size]

                        # Используем key IN для точного соответствия только нужным задачам
                        keys_condition = f'key in ({", ".join(batch)})'
                        batch_query = f'({keys_condition}) AND ({date_query})'

                        logger.info(f"Fetching filtered batch {i // batch_size + 1} with query: {batch_query}")
                        batch_issues = analyzer.get_issues_by_filter(jql_query=batch_query)
                        filtered_issues.extend(batch_issues)

                        total_issues_count += len(batch_issues)
                        analysis_state['progress'] = 30 + int((i + batch_size) / len(implementation_keys) * 10)
                        analysis_state[
                            'status_message'] = f'Filtered {i + min(batch_size, len(implementation_keys) - i)}/{len(implementation_keys)} implementation issues, found {total_issues_count} issues with worklogs'
                else:
                    # Если по какой-то причине implementation_keys пустой, используем поиск по проектам
                    logger.warning(
                        "No implementation issue keys found, falling back to project-based filtering")
                    for project in implementation_projects:
                        project_query = f'project = "{project}" AND ({date_query})'
                        project_issues = analyzer.get_issues_by_filter(jql_query=project_query)
                        filtered_issues.extend(project_issues)

                        total_issues_count += len(project_issues)
                        analysis_state[
                            'status_message'] = f'Processed {len(implementation_projects)} projects, found {total_issues_count} issues with worklogs'

                # MODIFIED: Save both filtered and all implementation issues in raw_issues.json
                # Combine both filtered issues and implementation issues into a single structure
                combined_issues = {
                    "filtered_issues": filtered_issues,
                    "all_implementation_issues": implementation_issues
                }

                raw_issues_path = os.path.join(output_dir, 'raw_issues.json')
                with open(raw_issues_path, 'w', encoding='utf-8') as f:
                    json.dump(combined_issues, f, indent=2, ensure_ascii=False)
                logger.info(
                    f"Saved combined issues data with {len(filtered_issues)} filtered issues and {len(implementation_issues)} total implementation issues to {raw_issues_path}")

                # Use the filtered issues for the current analysis
                issues = filtered_issues
            else:
                # Use all issues without date filtering
                issues = implementation_issues

                # In this case, filtered_issues and implementation_issues are identical
                # Still use the combined structure for consistency
                combined_issues = {
                    "filtered_issues": implementation_issues,
                    "all_implementation_issues": implementation_issues
                }

                raw_issues_path = os.path.join(output_dir, 'raw_issues.json')
                with open(raw_issues_path, 'w', encoding='utf-8') as f:
                    json.dump(combined_issues, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved combined issues data with {len(implementation_issues)} issues to {raw_issues_path}")

                filtered_issues = implementation_issues

            # Also save issue keys for later JQL generation
            clm_issue_keys = [issue.get('key') for issue in clm_issues if issue.get('key')]
            est_issue_keys = [issue.get('key') for issue in est_issues if issue.get('key')]
            improvement_issue_keys = [issue.get('key') for issue in improvement_issues if issue.get('key')]
            implementation_issue_keys = [issue.get('key') for issue in implementation_issues if issue.get('key')]
            filtered_issue_keys = [issue.get('key') for issue in filtered_issues if issue.get('key')]

            # Also extract open tasks with time spent
            open_tasks_issue_keys = []

            # Save all issue keys to a file
            clm_keys_data = {
                'clm_issue_keys': clm_issue_keys,
                'est_issue_keys': est_issue_keys,
                'improvement_issue_keys': improvement_issue_keys,
                'implementation_issue_keys': implementation_issue_keys,
                'filtered_issue_keys': filtered_issue_keys,
                'open_tasks_issue_keys': open_tasks_issue_keys,  # Will be populated later if needed
                'project_issue_mapping': project_issue_mapping
            }

            clm_keys_path = os.path.join(data_dir, 'clm_issue_keys.json')
            with open(clm_keys_path, 'w', encoding='utf-8') as f:
                json.dump(clm_keys_data, f, indent=4, ensure_ascii=False)

            # Prepare CLM metrics
            components_to_projects = map_components_to_projects(est_issues, implementation_issues)

            clm_metrics = {
                'clm_issues_count': clm_count,
                'est_issues_count': est_count,
                'improvement_issues_count': improvement_count,
                'linked_issues_count': len(implementation_issues),
                'filtered_issues_count': len(issues),
                'implementation_projects_count': len(implementation_projects),
                'components_mapping': components_to_projects
            }

            # Save CLM metrics
            clm_metrics_path = os.path.join(metrics_dir, 'clm_metrics.json')
            with open(clm_metrics_path, 'w', encoding='utf-8') as f:
                json.dump(clm_metrics, f, indent=4, ensure_ascii=False)

            # Create array of issue dictionaries for processing
            analysis_state['status_message'] = f'Processing {len(issues)} issues...'
            analysis_state['progress'] = 45

            # Set issues for further processing
            if not issues:
                # Create empty summary file with required fields
                summary_path = os.path.join(output_dir, 'summary.json')
                summary_data = {
                    'total_issues': 0,
                    'total_original_estimate_hours': 0,
                    'total_time_spent_hours': 0,
                    'projects_count': len(implementation_projects),
                    'projects': list(implementation_projects),
                    'avg_estimate_per_issue': 0,
                    'avg_time_spent_per_issue': 0,
                    'overall_efficiency': 0
                }
                summary_data.update(clm_metrics)

                with open(summary_path, 'w', encoding='utf-8') as f:
                    json.dump(summary_data, f, indent=4, ensure_ascii=False)

                # Create index file
                index_data = {
                    'timestamp': timestamp,
                    'total_issues': 0,
                    'charts': {},
                    'summary': summary_data,
                    'date_from': date_from,
                    'date_to': date_to,
                    'filter_id': None,
                    'jql_query': None,
                    'clm_filter_id': clm_filter_id if use_filter else None,
                    'clm_jql_query': clm_jql_query if not use_filter else None,
                    'data_source': data_source
                }

                index_path = os.path.join(output_dir, 'index.json')
                with open(index_path, 'w', encoding='utf-8') as f:
                    json.dump(index_data, f, indent=4, ensure_ascii=False)

                analysis_state[
                    'status_message'] = "No implementation issues found with time logged in the specified period."
                analysis_state['is_running'] = False
                return

        # Add date filtering if specified (for Jira mode or as additional condition for CLM)
        if data_source == 'jira' and (date_from or date_to):
            date_conditions = []
            if date_from:
                date_conditions.append(f'worklogDate >= "{date_from}"')
            if date_to:
                date_conditions.append(f'worklogDate <= "{date_to}"')

            if date_conditions:
                date_condition_str = ' AND '.join(date_conditions)

                if final_jql:
                    final_jql = f"({final_jql}) AND ({date_condition_str})"
                else:
                    final_jql = date_condition_str

                logger.info(f"Added date conditions: {date_condition_str}")

        if data_source == 'jira':
            analysis_state['status_message'] = f'Using query: {final_jql}'
            analysis_state['progress'] = 10

            # Fetch issues
            analysis_state['status_message'] = 'Fetching issues from Jira...'

            # Important: Pass jql_query and filter_id correctly based on use_filter
            if use_filter:
                issues = analyzer.get_issues_by_filter(filter_id=filter_id)
                logger.info(f"Fetching issues using filter ID: {filter_id}")
            else:
                issues = analyzer.get_issues_by_filter(jql_query=final_jql)
                logger.info(f"Fetching issues using JQL query: {final_jql}")

        analysis_state['total_issues'] = len(issues)
        analysis_state['status_message'] = f'Found {len(issues)} issues.'
        analysis_state['progress'] = 50

        if not issues:
            # Create empty summary file with required fields
            summary_path = os.path.join(output_dir, 'summary.json')
            summary_data = {
                'total_issues': 0,
                'total_original_estimate_hours': 0,
                'total_time_spent_hours': 0,
                'projects_count': 0,
                'projects': [],
                'avg_estimate_per_issue': 0,
                'avg_time_spent_per_issue': 0,
                'overall_efficiency': 0
            }

            # Add CLM metrics if available
            if clm_metrics:
                summary_data.update(clm_metrics)

            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=4, ensure_ascii=False)

            # Create index file
            index_data = {
                'timestamp': timestamp,
                'total_issues': 0,
                'charts': {},
                'summary': summary_data,
                'date_from': date_from,
                'date_to': date_to,
                'filter_id': filter_id if use_filter and data_source == 'jira' else None,
                'jql_query': jql_query if not use_filter and data_source == 'jira' else None,
                'clm_filter_id': clm_filter_id if use_filter and data_source == 'clm' else None,
                'clm_jql_query': clm_jql_query if not use_filter and data_source == 'clm' else None,
                'data_source': data_source
            }

            index_path = os.path.join(output_dir, 'index.json')
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, indent=4, ensure_ascii=False)

            analysis_state['status_message'] = "No issues found. Check query or credentials."
            analysis_state['is_running'] = False
            return

        # Process data
        analysis_state['status_message'] = 'Processing issue data...'
        analysis_state['progress'] = 60
        df = analyzer.process_issues_data(issues)

        # Save raw data for interactive charts
        raw_data_path = os.path.join(data_dir, 'raw_data.json')
        df.to_json(raw_data_path, orient='records')

        # If this is CLM mode, let's also identify and store open task issue keys for better JQL generation
        if data_source == 'clm':
            # Identify open tasks with time spent
            open_statuses = get_improved_open_statuses(df)
            open_tasks = df[df['status'].isin(open_statuses) & (df['time_spent_hours'] > 0)]

            if not open_tasks.empty:
                open_tasks_issue_keys = open_tasks['issue_key'].tolist()

                # Update the CLM keys data with open tasks
                try:
                    with open(clm_keys_path, 'r', encoding='utf-8') as f:
                        clm_keys_data = json.load(f)

                    clm_keys_data['open_tasks_issue_keys'] = open_tasks_issue_keys

                    with open(clm_keys_path, 'w', encoding='utf-8') as f:
                        json.dump(clm_keys_data, f, indent=4, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"Error updating CLM keys data with open tasks: {e}")

                    # Обновление проектов и их задач для более точного фильтрования
                    project_issue_mapping = {}
                    project_implementation_mapping = {}

                    # Составляем карту проектов и их задач из implementation_issues
                    for issue in implementation_issues:
                        issue_key = issue.get('key')
                        project_key = issue.get('fields', {}).get('project', {}).get('key', '')

                        if issue_key and project_key:
                            if project_key not in project_implementation_mapping:
                                project_implementation_mapping[project_key] = []
                            project_implementation_mapping[project_key].append(issue_key)

        # Create visualizations
        analysis_state['status_message'] = 'Creating visualizations...'
        analysis_state['progress'] = 70
        chart_paths = analyzer.create_visualizations(df, output_dir)

        # For CLM analysis, create additional CLM summary visualization
        if data_source == 'clm' and clm_metrics:
            analysis_state['status_message'] = 'Creating CLM summary visualization...'
            import matplotlib.pyplot as plt
            import seaborn as sns

            # Create CLM summary chart
            plt.figure(figsize=(10, 6))

            # Bar chart showing counts of different issue types
            counts = [
                clm_metrics['clm_issues_count'],
                clm_metrics['est_issues_count'],
                clm_metrics['improvement_issues_count'],
                clm_metrics['linked_issues_count'],
                clm_metrics['filtered_issues_count']
            ]
            labels = ['CLM Issues', 'EST Issues', 'Improvement Issues', 'Linked Issues', 'Filtered Issues']

            ax = sns.barplot(x=labels, y=counts)
            plt.title('CLM Analysis Summary')
            plt.ylabel('Count')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()

            # Save chart
            clm_summary_path = f"{output_dir}/clm_summary.png"
            plt.savefig(clm_summary_path)
            plt.close()

            # Add to chart paths
            chart_paths['clm_summary'] = clm_summary_path

        # Generate data for interactive charts
        analysis_state['status_message'] = 'Creating interactive charts...'
        analysis_state['progress'] = 80

        # Prepare chart data
        chart_data = prepare_chart_data(
            df,
            data_source=data_source,
            use_filter=use_filter,
            filter_id=filter_id,
            jql_query=jql_query,
            date_from=date_from,
            date_to=date_to,
            clm_filter_id=clm_filter_id,
            clm_jql_query=clm_jql_query,
            clm_metrics=clm_metrics,
            clm_issues=clm_issues,
            est_issues=est_issues,
            improvement_issues=improvement_issues,
            implementation_issues=implementation_issues,
            filtered_issues=filtered_issues,
            components_to_projects=components_to_projects
        )

        chart_data_path = os.path.join(data_dir, 'chart_data.json')
        with open(chart_data_path, 'w', encoding='utf-8') as f:
            json.dump(chart_data, f, indent=4, ensure_ascii=False)

        # Create index file with chart information
        index_data = {
            'timestamp': timestamp,
            'total_issues': len(issues),
            'charts': chart_paths,
            'summary': {},
            'date_from': date_from,
            'date_to': date_to,
            'filter_id': filter_id if use_filter and data_source == 'jira' else None,
            'jql_query': jql_query if not use_filter and data_source == 'jira' else None,
            'clm_filter_id': clm_filter_id if use_filter and data_source == 'clm' else None,
            'clm_jql_query': clm_jql_query if not use_filter and data_source == 'clm' else None,
            'data_source': data_source
        }

        # Load summary data if available
        summary_path = chart_paths.get('summary')
        if summary_path and os.path.exists(summary_path):
            try:
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary_data = json.load(f)

                    # Add CLM metrics to summary if available
                    if clm_metrics:
                        summary_data.update(clm_metrics)

                    # Ensure all required fields exist
                    if 'total_original_estimate_hours' not in summary_data:
                        summary_data['total_original_estimate_hours'] = 0

                    if 'total_time_spent_hours' not in summary_data:
                        summary_data['total_time_spent_hours'] = 0

                    if 'avg_estimate_per_issue' not in summary_data:
                        summary_data['avg_estimate_per_issue'] = 0

                    if 'avg_time_spent_per_issue' not in summary_data:
                        summary_data['avg_time_spent_per_issue'] = 0

                    if 'overall_efficiency' not in summary_data:
                        summary_data['overall_efficiency'] = 0

                    index_data['summary'] = summary_data

                    # Write updated summary back to file
                    with open(summary_path, 'w', encoding='utf-8') as f:
                        json.dump(summary_data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Error reading summary: {e}")

                # Create default summary
                index_data['summary'] = {
                    'total_issues': len(issues),
                    'total_original_estimate_hours': 0,
                    'total_time_spent_hours': 0,
                    'projects_count': len(df['project'].unique()) if not df.empty else 0,
                    'avg_estimate_per_issue': 0,
                    'avg_time_spent_per_issue': 0,
                    'overall_efficiency': 0
                }

                # Add CLM metrics if available
                if clm_metrics:
                    index_data['summary'].update(clm_metrics)

        # Save index file
        index_path = os.path.join(output_dir, 'index.json')
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=4, ensure_ascii=False)

        analysis_state['status_message'] = f'Analysis complete. Charts saved to {output_dir}.'
        analysis_state['progress'] = 100
        analysis_state['last_run'] = timestamp

        # Save raw issues for diagnostics - no longer needed since we already saved the combined issues
        if data_source != 'clm':
            # Only for Jira mode - for CLM mode we already saved a more comprehensive structure
            raw_issues_path = os.path.join(output_dir, 'raw_issues.json')
            with open(raw_issues_path, 'w', encoding='utf-8') as f:
                json.dump(issues, f, indent=2, ensure_ascii=False)
            logger.info(f"Raw issue data saved to {raw_issues_path}")


    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)
        analysis_state['status_message'] = f"An error occurred: {str(e)}"
    finally:
        analysis_state['is_running'] = False


def map_components_to_projects(est_issues, implementation_issues, all_related_issues=None):
    """
    Create mapping between EST components and implementation project keys
    with special exception rules for specific components.
    Logic: First try to find matches via parsing, if that fails, use exceptions.
    For DOC component, find all Documentation type issues in related issues.

    Args:
        est_issues (list): List of EST issue dictionaries
        implementation_issues (list): List of implementation issue dictionaries
        all_related_issues (list, optional): All issues related to CLM for DOC component mapping

    Returns:
        dict: Mapping from components to projects
    """
    import logging
    logger = logging.getLogger(__name__)

    # Extract all component names from EST issues
    components = set()
    for issue in est_issues:
        comps = issue.get('fields', {}).get('components', [])
        for comp in comps:
            comp_name = comp.get('name', '')
            if comp_name:
                components.add(comp_name)

    # Extract all projects from implementation issues
    projects = set()
    for issue in implementation_issues:
        project_key = issue.get('fields', {}).get('project', {}).get('key', '')
        if project_key:
            projects.add(project_key)

    # Special exceptions for specific component mappings
    special_mappings = {
        # Базовые правила
        'UNIGUI': ['NBSSPORTAL'],
        'PRAIM_INV': ['CHM'],
        'PRAIM': ['CHM'],
        'NBSS': ['NBSSPORTAL', 'NUS'],
        'NUS': ['NBSSPORTAL', 'NUS'],
        'UDB_INV': ['UDB', 'ATS', 'SSO'],
        'UDB': ['UDB', 'ATS', 'SSO'],

        # Новые исключения
        'BILLING': ['TUDBRES', 'BFAM', 'UDB'],
        'BIN': ['SAM', 'EPM', 'MBUS', 'TOMCAT'],
        'CAM+CPM+CIA': ['TLRDAPIMF', 'MCCA'],
        'CBDDevOps': ['UFMNX', 'LCM', 'DMS'],
        'CBSS_BIS': ['FIM', 'COMMON'],
        'CBSS_M2M': ['TLRKCELL', 'UZTK', 'IOTCMPRTK', 'IOTCMP', 'KYRGTLCM', 'TME', 'UCELL1'],
        'CBSS_PAYS': ['RIM', 'CDRSERVER'],
        'CCM': ['TLRDAPIMF'],
        'CNC': ['RE', 'ODPS', 'DGS', 'CDM'],
        'CompoziteYota': ['BPMY'],
        'CSI': ['ELASTICSCH'],
        'DGS_INV': ['PASS'],
        'INQ': ['WPSEC', 'ELASTICSCH', 'KAFKA', 'OSAMEGAFON'],
        'INT+BIS': ['PSCCFGMF', 'OPENAPIESB', 'TLROSAMF', 'ESIMMNG', 'REFDATA', 'FASOL', 'RDMF', 'TLRDAPIMF', 'TMFPCS'],
        'ISL_RSS': ['PRMCLSCHGT', 'PRMCL', 'PRMTELE2'],
        'LCCM+LIS': ['SORM', 'TLRDAPIMF', 'CRMDCS'],
        'M2M': ['IOTCMPGF'],
        'MFACTORY_APIRATION': ['BSP'],
        'MFACTORY_ARTCODE': ['BSP'],
        'MFACTORY_FASTDEV': ['BSP'],
        'MFACTORY_JSONBORN': ['BSP'],
        'MFACTORY_ORANGE': ['BSP'],
        'MFACTORY_PIEDPIPER': ['BSP'],
        'MFACTORY_RAICOM': ['BSP'],
        'MFACTORY_RAWDATA': ['BSP'],
        'MFACTORY_STIG': ['BSP'],
        'MFACTORY_WHITERABBIT': ['BSP'],
        'MNP_FMC': ['CRMSOLMF'],
        'MON': ['ELOG'],
        'OAPI': ['SLSTNTMF', 'ZOOKEEPER', 'BSSPE', 'TMFPCS', 'OPENAPIESB', 'SLSTNT'],
        'OMS': ['CRABMF'],
        'ORION': ['CRABMFML', 'TMMF', 'MOPS', 'BSSORDER', 'PIC'],
        'PAYS': ['SPP', 'UNIBLP', 'PPS', 'FPM'],
        'Perforator': ['GFPERFTEST'],
        'PSC': ['TRFMF'],
        'SCC': ['B2BMFUI', 'BBDATAMART'],
        'SSDEV': ['BSP', 'TLROSAMF'],
        'SSO+NGINX': ['HEX', 'TNT', 'APIGW', 'APACHE', 'COUCHBASE', 'HAS', 'TNTMF', 'CLHS'],
        'TDP': ['ODPS', 'CDM', 'RE', 'DGS', 'RS'],
        'UFM+LCM': ['DMS'],
        'RM_DELIVERY': ['TUDS'],
        'RM_ARH': ['TUDS'],
        'UFMDevOps': ['DMS']
    }

    # Create mapping based on substring matching and special rules
    mapping = {}

    # Специальная обработка для компонента DOC - поиск тикетов типа Documentation
    if 'DOC' in components:
        # Default empty list for DOC component
        mapping['DOC'] = []
        logger.info("Processing DOC component specifically")

        # Try to find Documentation issue types
        if all_related_issues:
            doc_projects = set()
            doc_issues_found = False

            # Check all related issues for Documentation type
            for issue in all_related_issues:
                issue_type = issue.get('fields', {}).get('issuetype', {}).get('name', '')
                if issue_type == 'Documentation':
                    doc_issues_found = True
                    project_key = issue.get('fields', {}).get('project', {}).get('key', '')
                    if project_key and project_key in projects:
                        doc_projects.add(project_key)
                        logger.info(f"Found Documentation issue {issue.get('key', 'unknown')} in project {project_key}")

            # If we found projects with Documentation issues, use them
            if doc_projects:
                mapping['DOC'] = list(doc_projects)
                logger.info(f"Mapped DOC component to projects with Documentation issues: {list(doc_projects)}")
            else:
                # No projects with Documentation issues found
                if doc_issues_found:
                    logger.warning("Found Documentation issues but couldn't extract valid project keys")
                else:
                    logger.warning("No Documentation issue types found among related issues")

                # Use all projects as fallback for DOC component
                if projects:
                    # To avoid over-assignment, use at most 3 projects or all if fewer
                    project_list = list(projects)
                    if len(project_list) > 3:
                        mapping['DOC'] = project_list[:3]
                    else:
                        mapping['DOC'] = project_list
                    logger.info(f"Using fallback: assigned projects {mapping['DOC']} to DOC component")
        else:
            logger.warning("No related issues provided to check for Documentation type")
            # Fallback - assign the DOC component to all available projects
            if projects:
                mapping['DOC'] = list(projects)[:3] if len(projects) > 3 else list(projects)
                logger.info(f"Using all available projects for DOC component: {mapping['DOC']}")

    # Обработка остальных компонентов
    for component in components:
        # Skip DOC as it's already processed
        if component == 'DOC':
            continue

        # Проверяем сначала специальные правила
        if component in special_mappings:
            # Фильтруем только проекты, которые существуют в нашем списке проектов
            predefined_projects = [proj for proj in special_mappings[component] if proj in projects]
            if predefined_projects:
                mapping[component] = predefined_projects
                logger.info(f"Applied special mapping rule: Component '{component}' → {predefined_projects}")
                continue

        # If no predefined projects matched, try substring matching
        matched_projects = []
        for project in projects:
            if (len(component) >= 3 and len(project) >= 3 and
                    (component[:3].lower() in project.lower() or project[:3].lower() in component.lower() or
                     component.lower() in project.lower() or project.lower() in component.lower())):
                matched_projects.append(project)

        if matched_projects:
            mapping[component] = matched_projects
            logger.info(f"Found match via substring: Component '{component}' → {matched_projects}")
        else:
            # No matches found, just provide an empty list
            mapping[component] = []
            logger.info(f"No matches found for component '{component}'")

    # Count matches for logging
    match_count = sum(1 for comp in mapping if mapping[comp])
    logger.info(f"Mapped {match_count} components to projects out of {len(components)} total components")

    return mapping