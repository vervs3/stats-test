import logging
from flask import render_template, request, jsonify
from modules.jira_estimation import get_latest_estimation_results, collect_estimation_data

# Get logger
logger = logging.getLogger(__name__)


def register_estimation_routes(app):
    """Register routes for Jira estimation data access"""

    @app.route('/estimation-results')
    def view_estimation_results():
        """View Jira estimation results"""
        logger.info("Rendering Jira estimation results page")

        # Get query parameters
        sprint_filter = request.args.get('sprint_filter', 'true').lower() == 'false'
        all_tasks = request.args.get('all_tasks', 'true').lower() == 'false'
        force_refresh = request.args.get('refresh', 'false').lower() == 'true'

        # Get the results
        if force_refresh:
            logger.info("Forcing refresh of Jira estimation data")
            filter_id = request.args.get('filter_id', '114924')
            results = collect_estimation_data(
                filter_id=filter_id,
                sprint_filter=sprint_filter,
                all_tasks=all_tasks
            )
        else:
            logger.info("Loading latest Jira estimation data")
            results = get_latest_estimation_results(
                sprint_filter=sprint_filter,
                all_tasks=all_tasks
            )

        # Render the template with results
        return render_template('estimation_results.html',
                               results=results,
                               sprint_filter=sprint_filter,
                               all_tasks=all_tasks,
                               active_tab='dashboard')  # Set active tab to dashboard

    @app.route('/api/estimation-results')
    def api_estimation_results():
        """API endpoint to get Jira estimation results"""
        try:
            # Get query parameters
            sprint_filter = request.args.get('sprint_filter', 'true').lower() == 'false'
            all_tasks = request.args.get('all_tasks', 'true').lower() == 'false'
            force_refresh = request.args.get('refresh', 'false').lower() == 'true'

            # Get the results
            if force_refresh:
                logger.info("API: Forcing refresh of Jira estimation data")
                filter_id = request.args.get('filter_id', '114924')
                results = collect_estimation_data(
                    filter_id=filter_id,
                    sprint_filter=sprint_filter,
                    all_tasks=all_tasks
                )
            else:
                logger.info("API: Loading latest Jira estimation data")
                results = get_latest_estimation_results(
                    sprint_filter=sprint_filter,
                    all_tasks=all_tasks
                )

            if not results:
                return jsonify({
                    'success': False,
                    'error': 'No estimation results available'
                }), 404

            return jsonify({
                'success': True,
                'data': results
            })
        except Exception as e:
            logger.error(f"Error getting estimation results: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/run-estimation')
    def api_run_estimation():
        """API endpoint to run Jira estimation analysis"""
        try:
            # Get query parameters
            filter_id = request.args.get('filter_id', '114924')
            sprint_filter = request.args.get('sprint_filter', 'true').lower() == 'false'
            all_tasks = request.args.get('all_tasks', 'true').lower() == 'false'

            logger.info(
                f"Running estimation analysis with filter_id={filter_id}, sprint_filter={sprint_filter}, all_tasks={all_tasks}")

            # Run analysis
            results = collect_estimation_data(
                filter_id=filter_id,
                sprint_filter=sprint_filter,
                all_tasks=all_tasks
            )

            if not results:
                return jsonify({
                    'success': False,
                    'error': 'Failed to run estimation analysis'
                }), 500

            return jsonify({
                'success': True,
                'message': 'Estimation analysis completed successfully',
                'data': results
            })
        except Exception as e:
            logger.error(f"Error running estimation analysis: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500