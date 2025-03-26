import os
import logging
from flask import Flask
from routes import register_routes
from modules.log_buffer import setup_log_buffer

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create directory for charts if it doesn't exist
CHARTS_DIR = 'jira_charts'
if not os.path.exists(CHARTS_DIR):
    os.makedirs(CHARTS_DIR)

# Create directory for dashboard data if it doesn't exist
DASHBOARD_DIR = 'nbss_data'
if not os.path.exists(DASHBOARD_DIR):
    os.makedirs(DASHBOARD_DIR)


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)

    # Setup log buffer
    setup_log_buffer()

    # Make sure template and static directories exist
    for directory in ['templates', 'static']:
        if not os.path.exists(directory):
            os.makedirs(directory)

    # Register all routes
    register_routes(app)

    # Check if dashboard has initial data, generate if not
    ensure_dashboard_data()

    return app


def ensure_dashboard_data():
    """
    Check if dashboard data exists, and if not, generate initial data
    """
    # Check if any data exists in the dashboard directory
    if not os.listdir(DASHBOARD_DIR):
        logger.info("No dashboard data found, generating initial sample data")
        try:
            from modules.dashboard_data_fix import generate_initial_dashboard_data
            result = generate_initial_dashboard_data()
            if result:
                logger.info("Successfully generated initial dashboard data")
            else:
                logger.warning("Failed to generate initial dashboard data")
        except Exception as e:
            logger.error(f"Error ensuring dashboard data: {e}", exc_info=True)
    else:
        logger.info(f"Dashboard data exists in {DASHBOARD_DIR}")


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)