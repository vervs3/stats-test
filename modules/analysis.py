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
                       clm_metrics=None):
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

    Returns:
        dict: Chart data for interactive charts
    """
    import logging
    from modules.data_processor import get_status_categories, get_improved_open_statuses

    logger = logging.getLogger(__name__)

    try:
        # Project data
        project_counts = df['project'].value_counts().to_dict()
        project_estimates = df.groupby('project')['original_estimate_hours'].sum().to_dict()
        project_time_spent = df.groupby('project')['time_spent_hours'].sum().to_dict()

        # Generate the list of all projects
        all_projects = list(set(list(project_counts.keys()) +
                                list(project_estimates.keys()) +
                                list(project_time_spent.keys())))

        logger.info(f"Prepared basic chart data with {len(all_projects)} projects")

        # Special chart 1: No transitions tasks data (переименован в "Открытые задачи со списаниями")
        no_transitions_tasks = df[df['no_transitions'] == True]
        no_transitions_by_project = {}
        if not no_transitions_tasks.empty:
            try:
                no_transitions_by_project = no_transitions_tasks.groupby('project').size().to_dict()
                logger.info(f"Prepared open tasks with worklogs data with {len(no_transitions_by_project)} projects")
            except Exception as e:
                logger.error(f"Error preparing open tasks with worklogs data: {str(e)}")
                # Provide an empty dict in case of error
                no_transitions_by_project = {}
        else:
            logger.info("Open tasks with worklogs dataset is empty")

        # Make sure we handle empty DataFrames gracefully
        no_transitions_count = len(no_transitions_tasks) if 'no_transitions_tasks' in locals() else 0

        # Save data for interactive charts
        chart_data = {
            'project_counts': project_counts,
            'project_estimates': project_estimates,
            'project_time_spent': project_time_spent,
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
                    'total': no_transitions_count
                }
            }
        }

        # Add CLM specific data if available
        if data_source == 'clm' and clm_metrics:
            chart_data['clm_metrics'] = clm_metrics

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
                final_jql = f'filter={filter_id}'
            else:
                final_jql = jql_query or ""
        else:
            # CLM analysis
            analysis_state['status_message'] = 'Processing CLM data...'

            # Get CLM issues first
            if use_filter:
                clm_query = f'project = CLM AND filter={clm_filter_id}'
            else:
                clm_query = clm_jql_query or "project = CLM"

            analysis_state['status_message'] = f'Fetching CLM issues with query: {clm_query}'
            analysis_state['progress'] = 5

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

            # Составляем карту проектов и их задач из implementation_issues
            for issue in implementation_issues:
                issue_key = issue.get('key')
                project_key = issue.get('fields', {}).get('project', {}).get('key', '')

                if issue_key and project_key:
                    if project_key not in project_implementation_mapping:
                        project_implementation_mapping[project_key] = []
                    project_implementation_mapping[project_key].append(issue_key)

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

                for project in implementation_projects:
                    project_query = f'project = "{project}" AND ({date_query})'
                    project_issues = analyzer.get_issues_by_filter(jql_query=project_query)
                    filtered_issues.extend(project_issues)

                    total_issues_count += len(project_issues)
                    analysis_state[
                        'status_message'] = f'Processed {len(implementation_projects)} projects, found {total_issues_count} issues with worklogs'

                # Use the final filtered issues
                issues = filtered_issues

                # Если есть фильтрация по датам, составляем отдельную карту для filtered_issues
                for issue in filtered_issues:
                    issue_key = issue.get('key')
                    project_key = issue.get('fields', {}).get('project', {}).get('key', '')

                    if issue_key and project_key:
                        if project_key not in project_issue_mapping:
                            project_issue_mapping[project_key] = []
                        project_issue_mapping[project_key].append(issue_key)
            else:
                # Use all issues without date filtering
                issues = implementation_issues
                filtered_issues = implementation_issues
                # Без фильтрации используем карту implementation_issues
                project_issue_mapping = project_implementation_mapping

            # Получить только open задачи
            open_tasks_issue_keys = []
            for issue in filtered_issues:
                # Проверка статуса (используем непосредственно поле status вместо анализа transitions)
                status = issue.get('fields', {}).get('status', {}).get('name', '')
                time_spent = issue.get('fields', {}).get('timespent', 0) or 0

                if status in ['Open', 'NEW'] and time_spent > 0:
                    open_tasks_issue_keys.append(issue.get('key'))

            # Сохранение ключей задач для использования в JQL-запросах
            clm_issue_keys = [issue.get('key') for issue in clm_issues if issue.get('key')]
            est_issue_keys = [issue.get('key') for issue in est_issues if issue.get('key')]
            improvement_issue_keys = [issue.get('key') for issue in improvement_issues if issue.get('key')]
            implementation_issue_keys = [issue.get('key') for issue in implementation_issues if issue.get('key')]
            filtered_issue_keys = [issue.get('key') for issue in filtered_issues if issue.get('key')]

            clm_keys_data = {
                'clm_issue_keys': clm_issue_keys,
                'est_issue_keys': est_issue_keys,
                'improvement_issue_keys': improvement_issue_keys,
                'implementation_issue_keys': implementation_issue_keys,
                'filtered_issue_keys': filtered_issue_keys,
                'open_tasks_issue_keys': open_tasks_issue_keys,
                'project_issue_mapping': project_issue_mapping,
                'project_implementation_mapping': project_implementation_mapping
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
                if final_jql:
                    final_jql = f"({final_jql}) AND ({' AND '.join(date_conditions)})"
                else:
                    final_jql = ' AND '.join(date_conditions)

        if data_source == 'jira':
            analysis_state['status_message'] = f'Using query: {final_jql}'
            analysis_state['progress'] = 10

            # Fetch issues
            analysis_state['status_message'] = 'Fetching issues from Jira...'
            issues = analyzer.get_issues_by_filter(jql_query=final_jql)

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

            # Also update project-to-issues mapping from the processed data
            project_to_issues = {}
            for _, row in df.iterrows():
                project = row['project']
                issue_key = row['issue_key']

                if project not in project_to_issues:
                    project_to_issues[project] = []

                project_to_issues[project].append(issue_key)

            # Update the CLM keys data with project mapping
            try:
                with open(clm_keys_path, 'r', encoding='utf-8') as f:
                    clm_keys_data = json.load(f)

                clm_keys_data['project_issue_mapping'] = project_to_issues

                with open(clm_keys_path, 'w', encoding='utf-8') as f:
                    json.dump(clm_keys_data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Error updating CLM keys data with project mapping: {e}")

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

        # Use the prepare_chart_data function instead of inline code
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
            clm_metrics=clm_metrics
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

        # Save raw issues for diagnostics
        raw_issues_path = os.path.join(output_dir, 'raw_issues.json')
        with open(raw_issues_path, 'w', encoding='utf-8') as f:
            json.dump(issues, f, indent=2, ensure_ascii=False)
        logger.info(f"Raw issue data saved to {raw_issues_path}")

    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)
        analysis_state['status_message'] = f"An error occurred: {str(e)}"
    finally:
        analysis_state['is_running'] = False


def map_components_to_projects(est_issues, implementation_issues):
    """
    Create mapping between EST components and implementation project keys

    Args:
        est_issues (list): List of EST issue dictionaries
        implementation_issues (list): List of implementation issue dictionaries

    Returns:
        dict: Mapping from components to projects
    """
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

    # Create mapping based on substring matching
    mapping = {}
    for component in components:
        matched_projects = []

        # For each component, find projects with at least 3 matching characters
        for project in projects:
            if len(component) >= 3 and len(project) >= 3:
                if component[:3].lower() in project.lower() or project[:3].lower() in component.lower():
                    matched_projects.append(project)

        if matched_projects:
            mapping[component] = matched_projects

    # Count matches for logging
    match_count = sum(1 for comp in mapping if mapping[comp])
    logger.info(f"Mapped {match_count} components to projects out of {len(components)} total components")

    return mapping