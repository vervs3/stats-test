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
    'improvement_issues_count': 'Количество тикетов типа "Improvement from CLM"',
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