import os
import logging
from flask import render_template, request, jsonify, redirect, url_for
from modules.clm_error_creator import ClmErrorCreator
from modules.excel_reader import save_subsystem_mapping, get_subsystems_for_product

# Get logger
logger = logging.getLogger(__name__)


def register_clm_error_routes(app):
    """Register routes for CLM Error creation"""

    @app.route('/clm-error-creator', methods=['GET'])
    def clm_error_creator():
        """Render the CLM Error creator page"""
        logger.info("Rendering CLM Error creator page")

        # Get subsystems for display
        subsystems = get_subsystems_for_product()
        logger.info(f"Loaded {len(subsystems)} subsystems for display")

        # Get previous creation results
        creator = ClmErrorCreator()
        creation_results = creator.get_creation_results()
        logger.info(f"Retrieved {len(creation_results)} previous CLM error creation results")

        return render_template('clm_error_creator.html',
                               subsystems=subsystems,
                               creation_results=creation_results,
                               active_tab='clm_error')

    @app.route('/api/clm-error-results', methods=['GET'])
    def get_clm_error_results():
        """Get all CLM Error creation results"""
        try:
            creator = ClmErrorCreator()
            results = creator.get_creation_results()

            return jsonify({
                'success': True,
                'results': results
            })
        except Exception as e:
            logger.error(f"Error getting CLM Error results: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            })

    @app.route('/api/upload-subsystem-mapping', methods=['POST'])
    def upload_subsystem_mapping():
        """Upload subsystem mapping Excel file"""
        try:
            logger.info("Handling subsystem mapping file upload")

            # Check if file was uploaded
            if 'mapping_file' not in request.files:
                logger.warning("No file uploaded")
                return jsonify({
                    'success': False,
                    'error': 'No file uploaded'
                })

            # Get the file
            file = request.files['mapping_file']

            # Check if file is empty
            if file.filename == '':
                logger.warning("Empty filename provided")
                return jsonify({
                    'success': False,
                    'error': 'No file selected'
                })

            # Check if file is Excel
            if not file.filename.endswith(('.xlsx', '.xls')):
                logger.warning(f"Invalid file type: {file.filename}")
                return jsonify({
                    'success': False,
                    'error': 'File must be Excel (.xlsx or .xls)'
                })

            logger.info(f"Processing uploaded file: {file.filename}")

            # Read file binary
            file_binary = file.read()

            # Save the file
            success = save_subsystem_mapping(file_binary)

            if not success:
                logger.error("Failed to save subsystem mapping")
                return jsonify({
                    'success': False,
                    'error': 'Error saving subsystem mapping'
                })

            logger.info("Successfully saved subsystem mapping")
            return jsonify({
                'success': True,
                'message': 'Subsystem mapping uploaded successfully'
            })
        except Exception as e:
            logger.error(f"Error uploading subsystem mapping: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            })

    @app.route('/api/get-subsystems', methods=['GET'])
    def get_subsystems():
        """Get subsystems for DIGITAL_BSS product"""
        try:
            logger.info("Fetching subsystems for DIGITAL_BSS product")

            # Get subsystems
            subsystems = get_subsystems_for_product()
            logger.info(f"Found {len(subsystems)} subsystems")

            return jsonify({
                'success': True,
                'subsystems': subsystems
            })
        except Exception as e:
            logger.error(f"Error getting subsystems: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            })

    @app.route('/api/create-clm-errors', methods=['POST', 'GET'])  # Keep GET for debugging
    def create_clm_errors():
        """Create CLM Error issues from given Jira issue keys"""
        try:
            # Log all incoming data for debugging
            logger.info("=" * 40)
            logger.info("API REQUEST: create-clm-errors")
            logger.info(f"Request method: {request.method}")
            logger.info(f"Request form data: {request.form}")
            logger.info(f"Request args: {request.args}")
            logger.info(f"Request JSON: {request.json if request.is_json else None}")
            logger.info(f"Request headers: {request.headers}")
            logger.info("=" * 40)

            # Get issue keys from different possible sources
            issue_keys = None

            if request.method == 'POST':
                # From form
                if 'issue_keys' in request.form:
                    issue_keys = request.form.get('issue_keys', '')
                    logger.info(f"Got issue keys from form: {issue_keys}")
                # From JSON
                elif request.is_json and 'issue_keys' in request.json:
                    issue_keys = request.json.get('issue_keys', '')
                    logger.info(f"Got issue keys from JSON: {issue_keys}")

            # From GET parameters (for debugging)
            if issue_keys is None and 'issue_keys' in request.args:
                issue_keys = request.args.get('issue_keys', '')
                logger.info(f"Got issue keys from URL args: {issue_keys}")

            if not issue_keys:
                logger.warning("No issue keys provided in the request")
                return jsonify({
                    'success': False,
                    'error': 'No issue keys provided'
                })

            # Create CLM Error
            logger.info(f"Creating CLM Errors for keys: {issue_keys}")
            creator = ClmErrorCreator()

            # Check if API token is available
            if not creator.api_token:
                logger.error("API token not available in creator")
                return jsonify({
                    'success': False,
                    'error': 'API token not available. Check config.py file.'
                })

            # Create CLM Errors
            logger.info("Calling CLM Error creator...")
            results = creator.create_clm_errors(issue_keys)
            logger.info(f"CLM Error creation results: {results}")

            # Check if we have any successful creations
            success_count = sum(1 for key, value in results.items() if value is not None)
            logger.info(f"Successfully created {success_count} out of {len(results)} CLM Errors")

            return jsonify({
                'success': True,
                'results': results
            })
        except Exception as e:
            logger.error(f"Error creating CLM Errors: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            })