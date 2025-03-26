import os
import json
import logging
import shutil
import threading
from flask import render_template, request, redirect, url_for, send_from_directory
from modules.analysis import run_analysis
from routes.main_routes import analysis_state
from modules.utils import format_timestamp_for_display

# Get logger
logger = logging.getLogger(__name__)

# Dictionary with metrics tooltips
metrics_tooltips = {
    'projects_count': 'Количество уникальных проектов, найденных в анализируемых задачах',
    'total_original_estimate_hours': 'Суммарная оценка времени для всех задач в часах, указанная в Original Estimate',
    'total_time_spent_hours': 'Суммарное фактически затраченное время на все задачи в часах, указанное в Time Spent',
    'avg_estimate_per_issue': 'Средняя оценка времени на одну задачу в часах',
    'avg_time_spent_per_issue': 'Среднее фактически затраченное время на одну задачу в часах',
    'overall_efficiency': 'Отношение затраченного времени к оценке (Коэффициент > 1 означает превышение оценки)',
    'no_transitions_tasks_count': 'Количество задач, которые никогда не меняли статус (вероятно все еще новые задачи)',
    'clm_issues_count': 'Количество найденных тикетов CLM',
    'est_issues_count': 'Количество связанных тикетов EST',
    'improvement_issues_count': 'Количество тикетов типа "Improvement from CLM" и "Analyzing from CLM"',
    'linked_issues_count': 'Общее количество связанных задач'
}


def register_analysis_routes(app):
    """Register routes for analysis operation and viewing"""

    @app.route('/start_analysis', methods=['POST'])
    def start_analysis():
        """Handle starting a new analysis"""
        if analysis_state['is_running']:
            return redirect(url_for('index'))

        # Get data source (jira or clm)
        data_source = request.form.get('data_source', 'jira')

        # Common parameters
        use_filter = request.form.get('use_filter') == 'yes'
        date_from = request.form.get('date_from', '')
        date_to = request.form.get('date_to', '')

        # Ensure valid date formats
        date_from = date_from if date_from else None
        date_to = date_to if date_to else None

        # Source-specific parameters
        if data_source == 'jira':
            # Standard Jira analysis
            filter_id = request.form.get('filter_id', '114476')
            jql_query = request.form.get('jql_query', '')
            clm_filter_id = None
            clm_jql_query = None
        else:
            # CLM analysis
            filter_id = None
            jql_query = None
            clm_filter_id = request.form.get('clm_filter_id', '114473')
            clm_jql_query = request.form.get('clm_jql_query', '')

        # Start analysis in a separate thread
        analysis_thread = threading.Thread(
            target=run_analysis,
            args=(data_source, use_filter, filter_id, jql_query, date_from, date_to, clm_filter_id, clm_jql_query)
        )
        analysis_thread.daemon = True
        analysis_thread.start()

        return redirect(url_for('index'))

    @app.route('/view/<timestamp>')
    def view_analysis(timestamp):
        """View analysis results by timestamp"""
        CHARTS_DIR = 'jira_charts'
        folder_path = os.path.join(CHARTS_DIR, timestamp)

        if not os.path.exists(folder_path):
            return "Analysis not found", 404

        # Data for interactive charts
        chart_data = {}
        chart_data_path = os.path.join(folder_path, 'data', 'chart_data.json')

        if os.path.exists(chart_data_path):
            try:
                with open(chart_data_path, 'r', encoding='utf-8') as f:
                    chart_data = json.load(f)
            except Exception as e:
                logger.error(f"Error reading chart data: {e}")
                chart_data = {}  # Ensure it's initialized even on error

        # Find all images in the folder
        chart_files = {}

        # Initialize special chart files
        special_chart_files = {
            'open_tasks': None,
            'completed_tasks_no_comments': None,
            'no_transitions_tasks': None
        }

        # Look for special charts by exact names first
        for filename in os.listdir(folder_path):
            filepath = os.path.join(folder_path, filename)
            if os.path.isfile(filepath) and filename.endswith('.png'):
                if 'open_tasks_time_spent.png' == filename:
                    special_chart_files['open_tasks'] = os.path.join(timestamp, filename)
                elif 'completed_tasks_no_comments.png' == filename:
                    special_chart_files['completed_tasks_no_comments'] = os.path.join(timestamp, filename)
                elif 'no_transitions_tasks.png' == filename:
                    special_chart_files['no_transitions_tasks'] = os.path.join(timestamp, filename)

        # If exact matches not found, look for partial matches
        if not all(special_chart_files.values()):
            for filename in os.listdir(folder_path):
                filepath = os.path.join(folder_path, filename)
                if os.path.isfile(filepath) and filename.endswith('.png'):
                    if not special_chart_files['open_tasks'] and (
                            'open_tasks' in filename.lower() or 'progress' in filename.lower()):
                        special_chart_files['open_tasks'] = os.path.join(timestamp, filename)
                    elif not special_chart_files['completed_tasks_no_comments'] and (
                            'completed' in filename.lower() or 'no_comments' in filename.lower()):
                        special_chart_files['completed_tasks_no_comments'] = os.path.join(timestamp, filename)
                    elif not special_chart_files['no_transitions_tasks'] and (
                            'no_transitions' in filename.lower() or 'new_tasks' in filename.lower()):
                        special_chart_files['no_transitions_tasks'] = os.path.join(timestamp, filename)

        # Add found special charts to the main dictionary
        for chart_type, chart_path in special_chart_files.items():
            if chart_path:
                chart_files[chart_type] = chart_path

        # Look for remaining charts
        for filename in os.listdir(folder_path):
            filepath = os.path.join(folder_path, filename)
            if os.path.isfile(filepath) and filename.endswith('.png'):
                # Determine chart type from filename
                chart_type = None
                if 'project_distribution_pie' in filename:
                    chart_type = 'project_pie'
                elif 'project_distribution' in filename and 'pie' not in filename:
                    chart_type = 'project_distribution'
                elif 'original_estimate' in filename:
                    chart_type = 'original_estimate'
                elif 'time_spent' in filename and 'open_tasks' not in filename:
                    chart_type = 'time_spent'
                elif 'estimate_vs_spent' in filename:
                    chart_type = 'comparison'
                elif 'efficiency_ratio' in filename:
                    chart_type = 'efficiency'
                elif 'clm_summary' in filename:
                    chart_type = 'clm_summary'

                # Add chart only if type is determined and not already added
                if chart_type and chart_type not in chart_files:
                    chart_files[chart_type] = os.path.join(timestamp, filename)

        # Load summary data if available
        summary_data = {}
        summary_file = os.path.join(folder_path, 'summary.json')
        if os.path.exists(summary_file):
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary_data = json.load(f)
            except Exception as e:
                logger.error(f"Error reading summary file: {e}")

        # Check metrics directory for additional data
        metrics_dir = os.path.join(folder_path, 'metrics')
        if os.path.exists(metrics_dir):
            # Look for open tasks metrics
            open_tasks_metrics = os.path.join(metrics_dir, 'open_tasks.json')
            if os.path.exists(open_tasks_metrics):
                try:
                    with open(open_tasks_metrics, 'r', encoding='utf-8') as f:
                        open_tasks_data = json.load(f)
                        if 'count' in open_tasks_data:
                            summary_data['open_tasks_count'] = open_tasks_data['count']
                        if 'total_time_spent' in open_tasks_data:
                            summary_data['open_tasks_time_spent_hours'] = open_tasks_data['total_time_spent']
                except Exception as e:
                    logger.error(f"Error loading open tasks metrics: {e}")

            # Check for closed tasks metrics
            closed_tasks_metrics = os.path.join(metrics_dir, 'closed_tasks.json')
            if os.path.exists(closed_tasks_metrics):
                try:
                    with open(closed_tasks_metrics, 'r', encoding='utf-8') as f:
                        closed_tasks_data = json.load(f)
                        if 'count' in closed_tasks_data:
                            summary_data['completed_tasks_no_comments_count'] = closed_tasks_data['count']
                except Exception as e:
                    logger.error(f"Error loading closed tasks metrics: {e}")

            # Check for no transitions tasks metrics
            no_transitions_metrics = os.path.join(metrics_dir, 'no_transitions_tasks.json')
            if os.path.exists(no_transitions_metrics):
                try:
                    with open(no_transitions_metrics, 'r', encoding='utf-8') as f:
                        no_transitions_data = json.load(f)
                        if 'count' in no_transitions_data:
                            summary_data['no_transitions_tasks_count'] = no_transitions_data['count']
                except Exception as e:
                    logger.error(f"Error loading no transitions tasks metrics: {e}")

            # Check for CLM metrics
            clm_metrics = os.path.join(metrics_dir, 'clm_metrics.json')
            if os.path.exists(clm_metrics):
                try:
                    with open(clm_metrics, 'r', encoding='utf-8') as f:
                        clm_data = json.load(f)
                        for key, value in clm_data.items():
                            summary_data[key] = value
                except Exception as e:
                    logger.error(f"Error loading CLM metrics: {e}")

        # Load index file if available
        index_data = {}
        index_file = os.path.join(folder_path, 'index.json')
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
            except Exception as e:
                logger.error(f"Error reading index file: {e}")

        # Create placeholder chart references if metrics exist but charts don't
        if (summary_data.get('open_tasks_count') is not None or
                summary_data.get('open_tasks_time_spent_hours') is not None):
            if 'open_tasks' not in chart_files:
                chart_files['open_tasks'] = 'placeholder'

        if summary_data.get('completed_tasks_no_comments_count') is not None:
            if 'completed_tasks_no_comments' not in chart_files:
                chart_files['completed_tasks_no_comments'] = 'placeholder'

        if summary_data.get('no_transitions_tasks_count') is not None:
            if 'no_transitions_tasks' not in chart_files:
                chart_files['no_transitions_tasks'] = 'placeholder'

        # Create data for display
        analysis_data = {
            'timestamp': timestamp,
            'display_timestamp': format_timestamp_for_display(timestamp),
            'total_issues': summary_data.get('total_issues', 0),
            'charts': chart_files,
            'summary': summary_data,
            'date_from': index_data.get('date_from'),
            'date_to': index_data.get('date_to'),
            'filter_id': index_data.get('filter_id'),
            'jql_query': index_data.get('jql_query'),
            'clm_filter_id': index_data.get('clm_filter_id'),
            'clm_jql_query': index_data.get('clm_jql_query'),
            'data_source': index_data.get('data_source', 'jira'),
            'chart_data': chart_data,
            'tooltips': metrics_tooltips
        }

        return render_template('view.html',
                               timestamp=timestamp,
                               data=analysis_data)

    @app.route('/charts/<path:filename>')
    def charts(filename):
        """Serve chart images"""
        CHARTS_DIR = 'jira_charts'
        # Handle nested paths like "timestamp/chart.png"
        parts = filename.split('/')

        if len(parts) == 1:
            # Simple filename
            return send_from_directory(CHARTS_DIR, filename)
        else:
            # Path with directory, like "timestamp/chart.png"
            dir_path = os.path.join(CHARTS_DIR, os.path.dirname(filename))
            basename = os.path.basename(filename)
            return send_from_directory(dir_path, basename)

    @app.route('/delete_reports', methods=['POST'])
    def delete_reports():
        """Handle request to delete selected reports"""
        CHARTS_DIR = 'jira_charts'
        selected_reports = request.form.getlist('selected_reports')

        if not selected_reports:
            return redirect(url_for('index'))

        for report_id in selected_reports:
            report_path = os.path.join(CHARTS_DIR, report_id)

            if os.path.exists(report_path) and os.path.isdir(report_path):
                try:
                    # Recursively delete the report directory
                    shutil.rmtree(report_path)
                    logger.info(f"Deleted report: {report_id}")
                except Exception as e:
                    logger.error(f"Error deleting report {report_id}: {str(e)}")

        return redirect(url_for('index'))

    @app.route('/view/dashboard/<date_str>')
    def view_dashboard_analysis(date_str):
        """
        View dashboard analysis for a specific date
        Improved to handle missing JSON data file
        """
        logger.info(f"Accessing dashboard view for date: {date_str}")

        DASHBOARD_DIR = 'nbss_data'
        folder_path = os.path.join(DASHBOARD_DIR, date_str)

        # Check if the folder exists
        if not os.path.exists(folder_path):
            logger.error(f"Dashboard folder not found: {folder_path}")
            return f"Dashboard analysis folder not found for date {date_str}", 404

        # Check for raw_issues.json (this is the critical file)
        raw_issues_path = os.path.join(folder_path, 'raw_issues.json')
        if not os.path.exists(raw_issues_path):
            logger.error(f"Raw issues file not found: {raw_issues_path}")
            return f"Raw issues file not found for date {date_str}", 404

        # Check for the summary.json file (create if missing)
        summary_path = os.path.join(folder_path, 'summary.json')
        dashboard_data = None

        if not os.path.exists(summary_path):
            logger.warning(f"Dashboard summary file not found: {summary_path}, generating from raw data")

            # Generate basic dashboard data from raw issues
            try:
                with open(raw_issues_path, 'r', encoding='utf-8') as f:
                    raw_issues = json.load(f)

                    # Extract issues based on the standardized format
                    if isinstance(raw_issues, dict):
                        filtered_issues = raw_issues.get('filtered_issues', [])
                        implementation_issues = raw_issues.get('all_implementation_issues', filtered_issues)

                        # Check for extra data in the new standardized format
                        additional_data = raw_issues.get('additional_data', {})
                        clm_issues = additional_data.get('clm_issues', [])
                        est_issues = additional_data.get('est_issues', [])
                        improvement_issues = additional_data.get('improvement_issues', [])
                    else:
                        # Fallback if raw_issues is a list
                        filtered_issues = raw_issues
                        implementation_issues = raw_issues
                        clm_issues = []
                        est_issues = []
                        improvement_issues = []

                    # Calculate time spent
                    total_time_spent_hours = 0
                    for issue in filtered_issues:
                        time_spent = issue.get('fields', {}).get('timespent', 0) or 0
                        total_time_spent_hours += time_spent / 3600

                    total_time_spent_days = total_time_spent_hours / 8
                    projected_time_spent_days = total_time_spent_days * 1.2  # Simple estimate

                    # Create basic dashboard data
                    dashboard_data = {
                        'date': f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
                        'timestamp': date_str,
                        'total_time_spent_hours': float(total_time_spent_hours),
                        'total_time_spent_days': float(total_time_spent_days),
                        'projected_time_spent_days': float(projected_time_spent_days),
                        'clm_issues_count': len(clm_issues),
                        'est_issues_count': len(est_issues),
                        'improvement_issues_count': len(improvement_issues),
                        'implementation_issues_count': len(implementation_issues),
                        'filtered_issues_count': len(filtered_issues)
                    }

                    # Save for future use
                    try:
                        with open(summary_path, 'w', encoding='utf-8') as f:
                            json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
                        logger.info(f"Created dashboard summary file: {summary_path}")
                    except Exception as e:
                        logger.error(f"Error saving dashboard data: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Error generating dashboard data: {e}", exc_info=True)
                return f"Error generating dashboard data: {e}", 500
        else:
            # Load the existing summary file
            try:
                with open(summary_path, 'r', encoding='utf-8') as f:
                    dashboard_data = json.load(f)
                    logger.info(f"Successfully loaded dashboard data from {summary_path}")
            except Exception as e:
                logger.error(f"Error reading dashboard data: {e}", exc_info=True)
                return f"Error reading dashboard data: {e}", 500

        # Process the raw issues
        try:
            with open(raw_issues_path, 'r', encoding='utf-8') as f:
                raw_issues = json.load(f)

            # Extract issues based on the standardized format
            if isinstance(raw_issues, dict):
                if 'filtered_issues' in raw_issues and 'all_implementation_issues' in raw_issues:
                    # Standard format
                    filtered_issues = raw_issues.get('filtered_issues', [])
                    all_implementation_issues = raw_issues.get('all_implementation_issues', filtered_issues)
                else:
                    # Old format or non-standard structure
                    filtered_issues = raw_issues.get('filtered_issues', []) if 'filtered_issues' in raw_issues else []
                    all_implementation_issues = raw_issues.get('all_implementation_issues',
                                                               []) if 'all_implementation_issues' in raw_issues else []

                    # If no standard fields found, search for values at root level
                    if not filtered_issues and not all_implementation_issues:
                        # Try to use any array field as implementation_issues
                        for key, value in raw_issues.items():
                            if isinstance(value, list) and value:
                                all_implementation_issues = value
                                filtered_issues = value
                                logger.info(f"Using field '{key}' as implementation issues")
                                break
            else:
                # Fallback if raw_issues is a list
                filtered_issues = raw_issues
                all_implementation_issues = raw_issues

            # Use the Jira analyzer to process the data
            from modules.jira_analyzer import JiraAnalyzer
            analyzer = JiraAnalyzer()

            # Process implementation issues to get a dataframe
            df = analyzer.process_issues_data(all_implementation_issues)

            # Create temporary directory for charts
            temp_dir = os.path.join(folder_path, 'charts')
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            # Create visualizations
            chart_paths = analyzer.create_visualizations(df, temp_dir)

            # Prepare chart data for the view
            chart_files = {}
            for chart_type, chart_path in chart_paths.items():
                if chart_path and os.path.exists(chart_path):
                    # Convert absolute path to relative path
                    rel_path = os.path.relpath(chart_path, folder_path)
                    chart_files[chart_type] = os.path.join(date_str, rel_path)

            # Create issue keys data if it doesn't exist
            data_dir = os.path.join(folder_path, 'data')
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)

            # Calculate project counts, estimates and time spent
            project_counts = df['project'].value_counts().to_dict()
            project_estimates = df.groupby('project')['original_estimate_hours'].sum().to_dict()
            project_time_spent = df.groupby('project')['time_spent_hours'].sum().to_dict()

            # Calculate open tasks
            from modules.data_processor import get_improved_open_statuses
            open_statuses = get_improved_open_statuses(df)
            open_tasks = df[df['status'].isin(open_statuses) & (df['time_spent_hours'] > 0)]
            no_transitions_by_project = {}

            if not open_tasks.empty:
                no_transitions_by_project = open_tasks.groupby('project').size().to_dict()

            # Extract issue keys from raw issues using standardized format
            clm_issue_keys = []
            est_issue_keys = []
            improvement_issue_keys = []
            implementation_issue_keys = []
            filtered_issue_keys = []

            # Extract issue keys from the additional_data field if it exists
            if isinstance(raw_issues, dict):
                additional_data = raw_issues.get('additional_data', {})

                # Extract from standardized structure
                clm_issues = additional_data.get('clm_issues', [])
                est_issues = additional_data.get('est_issues', [])
                improvement_issues = additional_data.get('improvement_issues', [])

                # Extract keys
                clm_issue_keys = [issue.get('key') for issue in clm_issues if issue.get('key')]
                est_issue_keys = [issue.get('key') for issue in est_issues if issue.get('key')]
                improvement_issue_keys = [issue.get('key') for issue in improvement_issues if issue.get('key')]
                implementation_issue_keys = [issue.get('key') for issue in all_implementation_issues if
                                             issue.get('key')]
                filtered_issue_keys = [issue.get('key') for issue in filtered_issues if issue.get('key')]

            # Group issue keys by project
            project_issue_mapping = {}
            for issue in all_implementation_issues:
                issue_key = issue.get('key')
                project_key = issue.get('fields', {}).get('project', {}).get('key', '')
                if issue_key and project_key:
                    if project_key not in project_issue_mapping:
                        project_issue_mapping[project_key] = []
                    project_issue_mapping[project_key].append(issue_key)

            # Prepare special charts data
            open_tasks_issue_keys = open_tasks['issue_key'].tolist() if not open_tasks.empty else []
            open_tasks_by_project = {}
            for project in no_transitions_by_project:
                project_open_tasks = open_tasks[open_tasks['project'] == project]
                open_tasks_by_project[project] = project_open_tasks['issue_key'].tolist()

            # Create chart data
            chart_data = {
                'project_counts': project_counts,
                'project_estimates': project_estimates,
                'project_time_spent': project_time_spent,
                'projects': list(set(list(project_counts.keys()) + list(project_estimates.keys()) + list(
                    project_time_spent.keys()))),
                'data_source': 'clm',  # Always use CLM data source for dashboard data
                'filter_params': {
                    'date_from': dashboard_data.get('date'),
                    'date_to': dashboard_data.get('date')
                },
                'special_charts': {
                    'no_transitions': {
                        'title': 'Открытые задачи со списаниями',
                        'by_project': no_transitions_by_project,
                        'total': len(open_tasks),
                        'issue_keys_by_project': open_tasks_by_project
                    }
                },
                'project_issue_mapping': project_issue_mapping,
                'clm_issue_keys': clm_issue_keys,
                'est_issue_keys': est_issue_keys,
                'improvement_issue_keys': improvement_issue_keys,
                'implementation_issue_keys': implementation_issue_keys,
                'filtered_issue_keys': filtered_issue_keys
            }

            # Save chart data
            chart_data_path = os.path.join(data_dir, 'chart_data.json')
            with open(chart_data_path, 'w', encoding='utf-8') as f:
                json.dump(chart_data, f, indent=4, ensure_ascii=False)

            # Save issue keys
            keys_data = {
                'clm_issue_keys': clm_issue_keys,
                'est_issue_keys': est_issue_keys,
                'improvement_issue_keys': improvement_issue_keys,
                'implementation_issue_keys': implementation_issue_keys,
                'filtered_issue_keys': filtered_issue_keys,
                'open_tasks_issue_keys': open_tasks_issue_keys,
                'project_issue_mapping': project_issue_mapping
            }

            clm_keys_path = os.path.join(data_dir, 'clm_issue_keys.json')
            with open(clm_keys_path, 'w', encoding='utf-8') as f:
                json.dump(keys_data, f, indent=4, ensure_ascii=False)

            # Calculate summary metrics
            total_issues = len(df)
            total_original_estimate_hours = df['original_estimate_hours'].sum()
            total_time_spent_hours = df['time_spent_hours'].sum()
            projects_count = len(df['project'].unique())
            avg_estimate_per_issue = df['original_estimate_hours'].mean() if len(df) > 0 else 0
            avg_time_spent_per_issue = df['time_spent_hours'].mean() if len(df) > 0 else 0
            overall_efficiency = (
                        total_time_spent_hours / total_original_estimate_hours) if total_original_estimate_hours > 0 else 0

            # Create summary data
            summary_data = {
                'total_issues': total_issues,
                'total_original_estimate_hours': float(total_original_estimate_hours),
                'total_time_spent_hours': float(total_time_spent_hours),
                'projects_count': projects_count,
                'avg_estimate_per_issue': float(avg_estimate_per_issue),
                'avg_time_spent_per_issue': float(avg_time_spent_per_issue),
                'overall_efficiency': float(overall_efficiency),
                'no_transitions_tasks_count': len(open_tasks),
                'clm_issues_count': len(clm_issue_keys),
                'est_issues_count': len(est_issue_keys),
                'improvement_issues_count': len(improvement_issue_keys),
                'linked_issues_count': len(implementation_issue_keys)
            }

            # Create data for display
            analysis_data = {
                'timestamp': date_str,
                'display_timestamp': f"Dashboard {dashboard_data.get('date', date_str)}",
                'total_issues': total_issues,
                'charts': chart_files,
                'summary': summary_data,
                'date_from': dashboard_data.get('date'),
                'date_to': dashboard_data.get('date'),
                'clm_filter_id': "dashboard",  # Placeholder for dashboard data
                'data_source': 'clm',  # Always use CLM data source
                'chart_data': chart_data,
                'tooltips': metrics_tooltips
            }

            return render_template('view.html',
                                   timestamp=date_str,
                                   data=analysis_data)

        except Exception as e:
            logger.error(f"Error processing dashboard analysis: {e}", exc_info=True)
            return f"Error processing dashboard analysis: {e}", 500

    @app.route('/dashboard/<path:filename>')
    def dashboard_files(filename):
        """Serve files from the dashboard directory"""
        DASHBOARD_DIR = 'nbss_data'
        # Handle nested paths like "timestamp/chart.png"
        parts = filename.split('/')

        if len(parts) == 1:
            # Simple filename
            return send_from_directory(DASHBOARD_DIR, filename)
        else:
            # Path with directory, like "timestamp/chart.png"
            dir_path = os.path.join(DASHBOARD_DIR, os.path.dirname(filename))
            basename = os.path.basename(filename)
            return send_from_directory(dir_path, basename)

    # Register view_dashboard_analysis explicitly (make sure this is present)
    app.add_url_rule('/view/dashboard/<date_str>', 'view_dashboard_analysis', view_dashboard_analysis)

    # Log registered routes for debugging
    logger.info("Registered analysis routes:")
    for rule in app.url_map.iter_rules():
        logger.info(f"Route: {rule}, Endpoint: {rule.endpoint}")