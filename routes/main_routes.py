import os
import logging
from datetime import datetime, timedelta
from flask import render_template, jsonify
from modules.utils import format_timestamp_for_display

# Get logger
logger = logging.getLogger(__name__)

# Global analysis state
analysis_state = {
    'is_running': False,
    'last_run': None,
    'progress': 0,
    'total_issues': 0,
    'status_message': '',
    'current_folder': None
}


def register_main_routes(app):
    """Register the main page routes"""

    @app.route('/')
    def index():
        """Render the main page"""
        # Get list of all analysis folders (sorted by date in reverse order)
        CHARTS_DIR = 'jira_charts'
        analysis_folders = []

        for folder in sorted(os.listdir(CHARTS_DIR), reverse=True):
            folder_path = os.path.join(CHARTS_DIR, folder)
            if os.path.isdir(folder_path) and folder != 'data':
                index_file = os.path.join(folder_path, 'index.json')
                info = {
                    'timestamp': folder,
                    'display_timestamp': format_timestamp_for_display(folder),
                    'charts_count': 0,
                    'total_issues': 0,
                    'date_from': None,
                    'date_to': None,
                    'analysis_type': 'jira'  # Default to 'jira' if not specified
                }

                if os.path.exists(index_file):
                    try:
                        import json
                        with open(index_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            info['charts_count'] = len(data.get('charts', {}))
                            info['total_issues'] = data.get('total_issues', 0)
                            info['date_from'] = data.get('date_from')
                            info['date_to'] = data.get('date_to')
                            # Include the data source type (jira or clm)
                            info['analysis_type'] = data.get('data_source', 'jira')
                    except Exception as e:
                        logger.error(f"Error reading index file {index_file}: {e}")

                analysis_folders.append(info)

        # Default date values (month ago - today)
        today = datetime.now().strftime('%Y-%m-%d')
        month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        return render_template('index.html',
                               analysis_state=analysis_state,
                               analysis_folders=analysis_folders,
                               default_from=month_ago,
                               default_to=today)

    @app.route('/status')
    def status():
        """Return the current analysis status"""
        return {
            'is_running': analysis_state['is_running'],
            'progress': analysis_state['progress'],
            'status_message': analysis_state['status_message'],
            'total_issues': analysis_state['total_issues']
        }

    @app.errorhandler(404)
    def page_not_found(e):
        """Handle 404 errors"""
        return render_template('error.html', error="Page not found"), 404

    @app.errorhandler(500)
    def server_error(e):
        """Handle 500 errors"""
        return render_template('error.html', error=f"Server error: {str(e)}"), 500