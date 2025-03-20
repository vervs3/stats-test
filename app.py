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

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)