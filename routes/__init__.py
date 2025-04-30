from .main_routes import register_main_routes
from .analysis_routes import register_analysis_routes
from .api_routes import register_api_routes
from .clm_error_routes import register_clm_error_routes
from .estimation_routes import register_estimation_routes

def register_routes(app):
    """Register all routes with the Flask application"""
    register_main_routes(app)
    register_analysis_routes(app)
    register_api_routes(app)
    register_clm_error_routes(app)
    register_estimation_routes(app)  # Добавлено
