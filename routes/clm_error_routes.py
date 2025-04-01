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
        # Get subsystems for display
        subsystems = get_subsystems_for_product()

        return render_template('clm_error_creator.html',
                               subsystems=subsystems,
                               active_tab='clm_error')

    @app.route('/api/create-clm-errors', methods=['POST', 'GET'])  # Добавим GET для отладки
    def create_clm_errors():
        """Create CLM Error issues from given Jira issue keys"""
        try:
            # Логирование всех входящих данных
            logger.info(f"Request method: {request.method}")
            logger.info(f"Request form data: {request.form}")
            logger.info(f"Request args: {request.args}")
            logger.info(f"Request JSON: {request.json if request.is_json else None}")

            # Получаем ключи задач из разных возможных источников
            issue_keys = None

            if request.method == 'POST':
                # Из формы
                if 'issue_keys' in request.form:
                    issue_keys = request.form.get('issue_keys', '')
                    logger.info(f"Got issue keys from form: {issue_keys}")
                # Из JSON
                elif request.is_json and 'issue_keys' in request.json:
                    issue_keys = request.json.get('issue_keys', '')
                    logger.info(f"Got issue keys from JSON: {issue_keys}")

            # Из GET параметров (для отладки)
            if issue_keys is None and 'issue_keys' in request.args:
                issue_keys = request.args.get('issue_keys', '')
                logger.info(f"Got issue keys from URL args: {issue_keys}")

            if not issue_keys:
                logger.warning("No issue keys provided")
                return jsonify({
                    'success': False,
                    'error': 'No issue keys provided'
                })

            # Создаем CLM Error
            logger.info(f"Creating CLM Errors for keys: {issue_keys}")
            creator = ClmErrorCreator()

            # Проверим наличие API токена
            if not creator.api_token:
                logger.error("API token not available in creator")
                return jsonify({
                    'success': False,
                    'error': 'API token not available. Check config.py file.'
                })

            # Создаем CLM Errors
            results = creator.create_clm_errors(issue_keys)
            logger.info(f"Results: {results}")

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

    @app.route('/api/upload-subsystem-mapping', methods=['POST'])
    def upload_subsystem_mapping():
        """Upload subsystem mapping Excel file"""
        try:
            # Check if file was uploaded
            if 'mapping_file' not in request.files:
                return jsonify({
                    'success': False,
                    'error': 'No file uploaded'
                })

            # Get the file
            file = request.files['mapping_file']

            # Check if file is empty
            if file.filename == '':
                return jsonify({
                    'success': False,
                    'error': 'No file selected'
                })

            # Check if file is Excel
            if not file.filename.endswith(('.xlsx', '.xls')):
                return jsonify({
                    'success': False,
                    'error': 'File must be Excel (.xlsx or .xls)'
                })

            # Read file binary
            file_binary = file.read()

            # Save the file
            success = save_subsystem_mapping(file_binary)

            if not success:
                return jsonify({
                    'success': False,
                    'error': 'Error saving subsystem mapping'
                })

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
            # Get subsystems
            subsystems = get_subsystems_for_product()

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