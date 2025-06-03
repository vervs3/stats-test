"""
CLM Status Transition Module
Handles automatic transitions of CLM Error tickets through different statuses
Переиспользует логику ClmErrorCreator для работы с Jira API
"""
import json
import os
import time
import threading
import re
import logging
from datetime import datetime, timedelta

import pandas as pd
import requests

logger = logging.getLogger(__name__)


class ClmStatusTransitioner:
    """
    Class for automating the status transitions of CLM Error tickets
    Created in response to requirements to transition tickets through statuses
    automatically after creation.
    """

    def __init__(self, clm_creator, time_delay=300):  # 300 seconds = 5 minutes
        """
        Initialize the CLM Status Transitioner

        Args:
            clm_creator (ClmErrorCreator): The CLM Error Creator instance
            time_delay (int): Delay in seconds before transitioning to Studying
        """
        self.clm_creator = clm_creator
        self.time_delay = time_delay
        self.running = False
        self.transition_thread = None
        self.jira_url = 'https://jira.nexign.com'
        logger.info(f"Initializing ClmErrorCreator with Jira URL: {self.jira_url}")

        # Use token from config
        try:
            import config
            if hasattr(config, 'api_token') and config.api_token:
                token_preview = config.api_token[:5] + "*****" if config.api_token else "None"
                self.headers = {
                    "Authorization": f"Bearer {config.api_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
                self.api_token = config.api_token
                logger.info(f"API token loaded from config (token preview: {token_preview})")
            else:
                logger.error("API token not found in config file or is empty")
                self.api_token = None
                self.headers = {}
        except ImportError:
            logger.error("config.py file not found. Create a config.py file with an api_token variable")
            self.api_token = None
            self.headers = {}

        # Initialize cache for field options to avoid repeated API calls
        self.field_options_cache = {}
        # Load subsystem mapping from Excel file
        self.subsystem_mapping = self._load_subsystem_mapping()

        # Get metadata for CLM project to identify fields and options
        self.create_meta = self.get_create_meta()
        self.field_ids = self._get_field_ids()

        # Initialize tracking for CLM Errors that have been in Received status
        self.received_tracking_file = os.path.join('data', 'clm_results', 'received_tracking.json')
        self.received_tracking = self._load_received_tracking()

    def _load_received_tracking(self):
        """
        Load tracking data for CLM Errors that have been in Received status

        Returns:
            dict: Dictionary with CLM Error keys and timestamps when they were first moved to Received
        """
        try:
            if os.path.exists(self.received_tracking_file):
                with open(self.received_tracking_file, 'r', encoding='utf-8') as f:
                    tracking_data = json.load(f)
                    logger.info(f"Loaded received tracking data for {len(tracking_data)} CLM Errors")
                    return tracking_data
            else:
                logger.info("No received tracking file found, creating new tracking")
                return {}
        except Exception as e:
            logger.error(f"Error loading received tracking data: {e}", exc_info=True)
            return {}

    def _save_received_tracking(self):
        """
        Save tracking data for CLM Errors that have been in Received status
        """
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.received_tracking_file), exist_ok=True)

            with open(self.received_tracking_file, 'w', encoding='utf-8') as f:
                json.dump(self.received_tracking, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved received tracking data for {len(self.received_tracking)} CLM Errors")
        except Exception as e:
            logger.error(f"Error saving received tracking data: {e}", exc_info=True)

    def _mark_as_received(self, clm_key):
        """
        Mark a CLM Error as having been in Received status

        Args:
            clm_key (str): CLM Error issue key
        """
        self.received_tracking[clm_key] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self._save_received_tracking()
        logger.info(f"Marked {clm_key} as having been in Received status")

    def _was_in_received(self, clm_key):
        """
        Check if a CLM Error has been in Received status before

        Args:
            clm_key (str): CLM Error issue key

        Returns:
            bool: True if the CLM Error has been in Received status before
        """
        return clm_key in self.received_tracking

    def _is_created_recently(self, created_time, max_hours=3):
        """
        Check if a CLM Error was created within the specified number of hours

        Args:
            created_time (datetime): Creation time of the CLM Error
            max_hours (int): Maximum number of hours (default: 3)

        Returns:
            bool: True if created within max_hours, False otherwise
        """
        time_since_creation = datetime.now() - created_time
        hours_since_creation = time_since_creation.total_seconds() / 3600

        logger.debug(f"Hours since creation: {hours_since_creation:.2f}, max allowed: {max_hours}")
        return hours_since_creation <= max_hours

    def _get_component_mapping_data(self, component):
        """
        Get Product Group and Subsystem mapping data for a given component.
        Enhanced to support specific component to Product Group and Subsystem mappings.

        Args:
            component (str): Component name from the source issue

        Returns:
            tuple: (product_group_id, subsystem_id, subsystem_name, subsystem_version_id)
        """
        # Default values
        default_product_group_id = "1011"  # DIGITAL_BSS
        default_subsystem_id = "1011"  # NBSS_CORE
        default_subsystem_name = "NBSS_CORE"
        default_version_id = "22550"  # Default version ID

        # If no component provided, return defaults
        if not component:
            logger.warning(f"No component provided, using defaults (DIGITAL_BSS/NBSS_CORE)")
            return default_product_group_id, default_subsystem_id, default_subsystem_name, default_version_id

        # Convert component to lowercase for case-insensitive matching
        component_lower = component.lower()
        logger.info(f"Getting mapping data for component '{component}'")

        # ВАЖНО: Специальная проверка для компонентов tailored.xxx
        if component_lower.startswith("tailored."):
            tailored_product_group_id = "1011"  # DIGITAL_BSS (можно изменить при необходимости)
            tailored_subsystem_id = "27227"  # ID для TAILORED_NBSS 2 (используйте правильный ID)
            tailored_subsystem_name = "TAILORED_NBSS 2"
            tailored_version_id = "2.1.0"  # ID версии для TAILORED_NBSS 2 (используйте правильный ID)

            logger.info(f"Component '{component}' matched as tailored component, mapping to TAILORED_NBSS 2")
            return tailored_product_group_id, tailored_subsystem_id, tailored_subsystem_name, tailored_version_id

        # Specific component mappings as provided
        component_mappings = {
            # Format: component_pattern: (product_group_id, subsystem_id, subsystem_name, version_id)
            # Original mappings
            "lis": ("992", "27228", "LIS 8", "8.9.1"),  # RND, LIS 8
            "cnc": ("992", "14257", "CNC 9", "11.8.0"),  # RND, CNC 9
            "crab": ("992", "23636", "CRAB 9", "9.19.0"),  # RND, CRAB 9
            "fpm": ("992", "23967", "FPM 3", "3.2.2"),  # RND, FPM 3
            "praim": ("992", "23921", "PRAIM 1", "1.3.0"),  # RND, PRAIM 1
            "cpm": ("952", "14250", "CPM 10", "11.6.0"),  # CRM, CPM 10
            "sso": ("974", "23635", "SSO 10", "10.17.0"),  # ISEM, SSO 10
            "ats": ("974", "23635", "SSO 10", "10.17.0"),  # ISEM, SSO 10

            # DIGITAL_BSS mappings (kept from original logic)
            "udb": ("1011", "23924", "UDB", "2.7.0"),
            "nus": ("1011", "23932", "NUS", "1.5.2"),
            "nbssportal": ("1011", "27398", "NBSSPORTAL", "1.0.0"),
            "chm": ("1011", "23923", "CHM", "22550"),
            "apc": ("1011", "23923", "APC", "1.5.0"),
            "csm": ("1011", "23817", "CSM", "1.5.1"),
            "ecs": ("1011", "14187", "ECS", "22550"),
            "npm": ("1011", "27400", "NPM_PORTAL", "22550"),
            "nsg": ("1011", "27373", "NSG", "1.0.0"),
            "pass": ("1011", "23764", "PASS", "1.5.3"),
            "payment": ("1011", "14274", "PAYMENT_MANAGEMENT", "3.2.3"),
            "vms": ("1011", "23767", "VMS", "1.2.0"),

            # New mappings
            "gus": ("980", "23920", "GUS 4", "4.11.1"),  # BFAM, GUS 4
            "uniblp": ("973", "14263", "UNIBLP 2", "2.18.0"),  # PAYS, UNIBLP 2
            "dms": ("1010", "27464", "DMS 2", "1.6.13"),  # UFM, DMS 2
            "nlm": ("1010", "23815", "NLM 1", "1.3.0"),  # UFM, NLM 1
            "osa": ("974", "23635", "SSO 10", "4.10.0"),  # ISEM, SSO 10
            "dgs": ("967", "24119", "DGS 3", "3.3.3"),  # TDP, DGS 3
            "lam": ("981", "23799", "LAM 1", "1.2.0"),  # RIM, LAM 1
            "tailored": ("1011", "27227", "TAILORED_NBSS 2", "2.1.0"),  # DIGITAL_BSS, TAILORED_NBSS 2
            "tailored.": ("1011", "27227", "TAILORED_NBSS 2", "2.1.0"),  # Match any tailored.xxx component
            "psc": ("988", "23625", "PSC 10", "10.12.2"),  # PSC, PSC 10
            "pic": ("949", "23657", "PIC 4", "4.12.1"),  # BIN, PIC 4
            "sam": ("955", "14278", "SAM 1", "1.10.0")  # HEX, SAM 1
        }

        # Check for direct matches in component mappings
        for pattern, mapping in component_mappings.items():
            if pattern in component_lower:
                logger.info(f"Found direct mapping for component '{component}' using pattern '{pattern}'")
                return mapping

        # If no specific mapping found, use default DIGITAL_BSS and NBSS_CORE
        logger.warning(f"No specific mapping found for component '{component}', using defaults")
        return default_product_group_id, default_subsystem_id, default_subsystem_name, default_version_id

    def _get_field_ids(self):
        """
        Get field IDs for CLM project from the create metadata

        Returns:
            dict: Mapping of field names to field IDs
        """
        try:
            logger.info("Extracting field IDs from create metadata")
            field_mappings = {
                'Product Group': None,
                'Subsystem': None,
                'Urgency': None,
                'Company': None,
                'Production/Test': None
            }

            # If we have metadata, extract field IDs
            if self.create_meta:
                fields = self.create_meta.get('fields', {})

                # Map field names to IDs
                for field_id, field_info in fields.items():
                    name = field_info.get('name', '')
                    if name in field_mappings:
                        field_mappings[name] = field_id
                        logger.info(f"Mapped field '{name}' to ID '{field_id}'")

                        # Check if this is a multi-select field
                        schema = field_info.get('schema', {})
                        field_type = schema.get('type', '')
                        is_array = schema.get('custom',
                                              '') == 'com.atlassian.jira.plugin.system.customfieldtypes:multiselect'

                        if is_array or field_type == 'array':
                            logger.info(f"Field '{name}' is a multi-select field")

                        # Check for allowedValues
                        allowed_values = field_info.get('allowedValues', [])
                        if allowed_values:
                            self.field_options_cache[field_id] = allowed_values
                            logger.info(f"Cached {len(allowed_values)} options for field '{name}'")

            # Fallback to API call if needed
            if not all(field_mappings.values()):
                logger.info("Some field IDs not found in metadata, fetching from API")

                if not self.api_token:
                    logger.error("Cannot fetch field metadata: API token not available")
                    return field_mappings

                url = f"{self.jira_url}/rest/api/2/field"
                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=30
                )

                if response.status_code != 200:
                    logger.error(f"Error fetching field metadata: {response.status_code}")
                    return field_mappings

                api_fields = response.json()
                logger.info(f"Successfully fetched {len(api_fields)} fields from Jira API")

                # Map field names to IDs
                for field in api_fields:
                    name = field.get('name', '')
                    id = field.get('id', '')
                    if name in field_mappings and field_mappings[name] is None:
                        field_mappings[name] = id
                        logger.info(f"Mapped field '{name}' to ID '{id}' from API")

            # Log the final mappings
            logger.info(f"Final field ID mappings: {json.dumps(field_mappings)}")

            # Fallback to hardcoded values if not found
            if not field_mappings['Product Group']:
                field_mappings['Product Group'] = 'customfield_12311'
            if not field_mappings['Subsystem']:
                field_mappings['Subsystem'] = 'customfield_12312'
            if not field_mappings['Urgency']:
                field_mappings['Urgency'] = 'customfield_13004'
            if not field_mappings['Company']:
                field_mappings['Company'] = 'customfield_12374'
            if not field_mappings['Production/Test']:
                field_mappings['Production/Test'] = 'customfield_12401'

            return field_mappings
        except Exception as e:
            logger.error(f"Error getting field IDs: {e}", exc_info=True)
            # Return default mappings
            return {
                'Product Group': 'customfield_10509',
                'Subsystem': 'customfield_14900',
                'Urgency': 'customfield_13004',
                'Company': 'customfield_16300',
                'Production/Test': 'customfield_17200'
            }

    def get_field_options(self, field_id):
        """
        Get options for a field from the create metadata or API

        Args:
            field_id (str): Field ID

        Returns:
            list: List of option objects with id and value
        """
        # Check if we have cached options
        if field_id in self.field_options_cache:
            logger.info(f"Using cached options for field {field_id}")
            return self.field_options_cache[field_id]

        # Check if we have options in the create metadata
        if self.create_meta and 'fields' in self.create_meta:
            field_info = self.create_meta['fields'].get(field_id, {})
            allowed_values = field_info.get('allowedValues', [])

            if allowed_values:
                self.field_options_cache[field_id] = allowed_values
                logger.info(f"Got {len(allowed_values)} options for field {field_id} from metadata")
                return allowed_values

        # Try to get options from Jira API
        try:
            if not self.api_token:
                logger.error(f"Cannot fetch options for field {field_id}: API token not available")
                return []

            # For custom fields, we can get options with the /field/{id}/option API
            if field_id.startswith('customfield_'):
                url = f"{self.jira_url}/rest/api/2/field/{field_id}/option"
                logger.info(f"Fetching options for field {field_id} from {url}")

                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=30
                )

                if response.status_code != 200:
                    logger.error(f"Error fetching options for field {field_id}: {response.status_code}")
                    return []

                options_data = response.json()
                options = options_data.get('values', [])

                # Cache the options
                self.field_options_cache[field_id] = options
                logger.info(f"Got {len(options)} options for field {field_id} from API")

                return options
        except Exception as e:
            logger.error(f"Error fetching options for field {field_id}: {e}", exc_info=True)

        return []

    def start_transition_monitor(self):
        """Start the transition monitor thread if not already running"""
        if self.running:
            logger.info("Transition monitor is already running")
            return

        self.running = True
        self.transition_thread = threading.Thread(target=self._monitor_transitions)
        self.transition_thread.daemon = True
        self.transition_thread.start()
        logger.info("Started CLM Error transition monitor thread")

    def stop_transition_monitor(self):
        """Stop the transition monitor thread"""
        self.running = False
        if self.transition_thread:
            self.transition_thread.join(timeout=1.0)
            logger.info("Stopped CLM Error transition monitor thread")

    def _monitor_transitions(self):
        """Main monitoring loop that checks for CLM Errors that need transitions
        С поддержкой перехода из статуса Authorized и ограничением по времени создания"""
        logger.info("CLM Error transition monitor started")

        while self.running:
            try:
                # Get creation results
                results = self.clm_creator.get_creation_results()

                # Process each successful CLM Error creation
                successful_results = [r for r in results if r.get('status') == 'success' and r.get('clm_error_key')]
                logger.info(f"Found {len(successful_results)} successful CLM Error creations to check")

                for result in successful_results:
                    clm_key = result.get('clm_error_key')
                    created_time_str = result.get('timestamp')

                    # Skip if no timestamp
                    if not created_time_str:
                        continue

                    # Parse creation time
                    try:
                        created_time = datetime.strptime(created_time_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        logger.error(f"Could not parse timestamp for {clm_key}: {created_time_str}")
                        continue

                    # NEW: Check if CLM Error was created within 3 hours
                    if not self._is_created_recently(created_time, max_hours=3):
                        logger.debug(f"Skipping {clm_key}: created more than 3 hours ago ({created_time_str})")
                        continue

                    # Get current status
                    issue_details = self._get_issue_details(clm_key)
                    if not issue_details:
                        continue

                    current_status = issue_details.get('status')
                    if not current_status:
                        continue

                    logger.info(f"Processing {clm_key}, current status: {current_status}, created: {created_time_str}")

                    # Calculate time since creation
                    time_since_creation = datetime.now() - created_time

                    # Check if we need to transition to Studying
                    # Добавляем поддержку перехода из статуса Authorized
                    if current_status in ['Authorized'] and time_since_creation.total_seconds() >= self.time_delay:
                        logger.info(f"Time to transition {clm_key} to Studying from {current_status}")
                        self._transition_to_studying(clm_key)

                    # Check if we need to transition to Received
                    if current_status in ['Studying']:
                        # NEW: Check if this CLM Error has already been in Received status
                        if self._was_in_received(clm_key):
                            logger.info(
                                f"Skipping transition to Received for {clm_key}: already was in Received status before")
                            continue

                        # If more than 10 minutes passed since creation, try to transition to Received
                        if time_since_creation.total_seconds() >= (self.time_delay * 2):
                            logger.info(f"Time to transition {clm_key} to Received from {current_status}")
                            success = self._transition_to_received(clm_key)

                            # NEW: Mark as having been in Received if transition was successful
                            if success:
                                self._mark_as_received(clm_key)

            except Exception as e:
                logger.error(f"Error in CLM transition monitor: {e}", exc_info=True)

            # Sleep for a while before checking again
            time.sleep(300)  # Check every 5 minutes

    def _get_issue_details(self, issue_key):
        """
        Get the current status of a Jira issue by reusing ClmErrorCreator's method

        Args:
            issue_key (str): Jira issue key

        Returns:
            dict: Issue details including status or None if error
        """
        try:
            # Reuse the existing method from ClmErrorCreator
            issue_details = self.clm_creator.get_issue_details(issue_key)

            if not issue_details:
                logger.error(f"Could not get issue details for {issue_key}")
                return None

            # The original method might not include status, check and add if needed
            if 'status' not in issue_details:
                # Make a separate API call to get status or extract it from the issue data
                # For simplicity, we'll make another API call using the same API
                url = f"{self.clm_creator.jira_url}/rest/api/2/issue/{issue_key}?fields=status"

                response = self._make_api_request('GET', url)

                if not response or 'fields' not in response:
                    logger.error(f"Could not get status for {issue_key}")
                    return issue_details

                status_name = response.get('fields', {}).get('status', {}).get('name')
                issue_details['status'] = status_name

            logger.info(f"Current status of {issue_key}: {issue_details.get('status')}")
            return issue_details

        except Exception as e:
            logger.error(f"Error getting status for {issue_key}: {e}", exc_info=True)
            return None

    def _make_api_request(self, method, url, data=None):
        """
        Выполняет API запрос с улучшенной обработкой ошибок и логированием

        Args:
            method (str): HTTP метод (GET, POST и т.д.)
            url (str): URL для запроса
            data (dict, optional): Данные для запроса (для POST)

        Returns:
            dict: Результат запроса в виде JSON или None в случае ошибки
        """
        try:
            import requests
            import json
            import re

            # Извлекаем ключ задачи из URL для логирования
            issue_key = None
            match = re.search(r'/issue/([A-Z]+-\d+)/', url)
            if match:
                issue_key = match.group(1)

            # Логируем запрос (без заголовков авторизации)
            safe_headers = {k: v for k, v in self.clm_creator.headers.items() if k.lower() != 'authorization'}
            logger.info(f"Making {method} request to {url}")
            if data:
                logger.info(f"Request data: {json.dumps(data)}")

            # Выполняем запрос
            if method.upper() == 'GET':
                response = requests.get(
                    url,
                    headers=self.clm_creator.headers,
                    timeout=30
                )
            elif method.upper() == 'POST':
                response = requests.post(
                    url,
                    headers=self.clm_creator.headers,
                    json=data,
                    timeout=30
                )
            else:
                logger.error(f"Unsupported HTTP method: {method}")
                return None

            # Проверяем статус ответа
            if response.status_code not in [200, 201, 204]:
                logger.error(f"API request failed with status code: {response.status_code}")

                # Логируем детали ошибки для отладки
                try:
                    error_data = response.json()
                    error_message = error_data.get('errorMessages', [])
                    error_fields = error_data.get('errors', {})

                    if error_message:
                        logger.error(f"Error messages: {error_message}")
                    if error_fields:
                        logger.error(f"Field errors: {error_fields}")

                    # Сохраняем ошибку в хранилище для последующего анализа
                    if issue_key:
                        if not hasattr(self, '_last_errors'):
                            self._last_errors = {}
                        self._last_errors[issue_key] = error_data
                        logger.info(f"Saved error details for issue {issue_key}")
                except Exception as e:
                    logger.error(f"Could not parse error response: {e}")
                    logger.error(f"Response text: {response.text[:500]}...")

                return None

            # Обрабатываем успешный ответ
            if response.status_code == 204:  # No content
                return {}

            try:
                return response.json()
            except json.JSONDecodeError:
                logger.warning(f"Could not parse JSON response: {response.text[:500]}...")
                # Возвращаем пустой объект для успешных запросов без JSON
                return {}

        except Exception as e:
            logger.error(f"Exception during API request: {e}", exc_info=True)
            return None

    def _get_transition_id(self, issue_key, transition_name):
        """
        Get transition ID for a given transition name

        Args:
            issue_key (str): Jira issue key
            transition_name (str): Name of the transition

        Returns:
            str: Transition ID or None if not found
        """
        try:
            url = f"{self.clm_creator.jira_url}/rest/api/2/issue/{issue_key}/transitions"

            transitions_data = self._make_api_request('GET', url)

            if not transitions_data or 'transitions' not in transitions_data:
                logger.error(f"No transitions found for {issue_key}")
                return None

            transitions = transitions_data.get('transitions', [])

            # Find transition by name
            transition = next((t for t in transitions if t.get('name') == transition_name), None)

            if not transition:
                logger.error(f"No transition '{transition_name}' found for {issue_key}")
                return None

            transition_id = transition.get('id')
            logger.info(f"Found transition '{transition_name}' for {issue_key}: {transition_id}")
            return transition_id

        except Exception as e:
            logger.error(f"Error getting transition ID: {e}", exc_info=True)
            return None

    def _get_latest_version(self):
        """
        Получить ID последней версии для поля Subsystem version (customfield_12408)
        с улучшенной логикой определения подходящей версии

        Returns:
            str: ID последней версии или "22550" по умолчанию
        """
        try:
            # Запрашиваем доступные опции для поля customfield_12408
            url = f"{self.clm_creator.jira_url}/rest/api/2/field/customfield_12408/option"

            response = requests.get(
                url,
                headers=self.clm_creator.headers,
                timeout=30
            )

            if response.status_code != 200:
                logger.warning(f"Could not fetch options for customfield_12408: {response.status_code}")
                # Возвращаем значение по умолчанию в случае ошибки
                return "22550"

            options_data = response.json()
            available_options = options_data.get('values', [])

            if not available_options:
                logger.warning("No options found for customfield_12408")
                return "22550"

            # Ищем опцию с максимальной версией в имени
            latest_version = None
            latest_id = None

            for option in available_options:
                option_value = option.get('value', '')
                option_id = option.get('id')

                # Пропускаем опцию "Please select"
                if "please select" in option_value.lower():
                    continue

                # Извлекаем номер версии с помощью регулярного выражения
                import re
                match = re.search(r'(\d+(\.\d+)+)', option_value)

                if match:
                    version_str = match.group(1)
                    try:
                        # Разбиваем версию на компоненты (например, "5.3.1" -> [5, 3, 1])
                        version_parts = [int(part) for part in version_str.split('.')]

                        # Если это первая найденная версия или она больше текущей последней
                        if latest_version is None or version_parts > latest_version:
                            latest_version = version_parts
                            latest_id = option_id
                            logger.info(f"Found newer version: {option_value} (ID: {option_id})")
                    except (ValueError, TypeError):
                        # Пропускаем опции с некорректным форматом версии
                        continue

            if latest_id:
                logger.info(f"Selected latest version with ID: {latest_id}")
                return latest_id
            else:
                # Если не найдено подходящих версий, возвращаем значение по умолчанию
                logger.warning("No suitable version found, using default")
                return "22550"

        except Exception as e:
            logger.error(f"Error getting latest version: {e}", exc_info=True)
            # Возвращаем значение по умолчанию в случае ошибки
            return "22550"

    def _get_field_options_for_issue(self, issue_key):
        """
        Get field options for specific issue, especially for version fields

        Args:
            issue_key (str): Jira issue key

        Returns:
            dict: Dictionary of field options by field ID
        """
        try:
            # Используем кэш, если он уже существует
            if hasattr(self, 'field_options_cache'):
                return self.field_options_cache

            # Иначе инициализируем пустой словарь кэша
            self.field_options_cache = {}

            # Заполняем опции на основе данных со скриншота
            # Для поля customfield_12408 (Subsystem version)

            # Другие поля с жестко заданными значениями
            self.field_options_cache['customfield_12409'] = [
                {"id": "35200", "value": "Default Subtype"}
            ]

            self.field_options_cache['customfield_12415'] = [
                {"id": "12030", "value": "Default Workaround"}
            ]

            return self.field_options_cache

        except Exception as e:
            logger.error(f"Error getting field options for issue {issue_key}: {e}", exc_info=True)
            # Возвращаем пустой словарь в случае ошибки
            return {}

    def _prepare_transition_fields(self, issue_key, custom_fields=None, transition_type=None):
        """
        Prepare fields for transition with enhanced component mapping

        Args:
            issue_key (str): Jira issue key
            custom_fields (dict): Additional fields and values
            transition_type (str): Type of transition ('studying' or 'received')

        Returns:
            dict: Prepared fields for transition
        """
        try:
            # Initialize empty dictionary for fields
            result_fields = {}

            # If no custom fields provided, use empty dict
            custom_fields = custom_fields or {}

            logger.info(f"Preparing fields for transition type: {transition_type}")

            # Get field metadata if available
            field_meta = {}
            if hasattr(self.clm_creator, 'create_meta') and self.clm_creator.create_meta:
                if 'fields' in self.clm_creator.create_meta:
                    field_meta = self.clm_creator.create_meta['fields']

            # Default mapping for DIGITAL_BSS/NBSS_CORE
            product_group_id = '1011'  # Default for DIGITAL_BSS
            subsystem_id = '1011'  # Default for NBSS_CORE
            subsystem_version_id = '22550'  # Default version ID

            # Find information about related RMBSS ticket in creation_results.json
            source_issue_key = None
            try:
                # Check if issue_key is already an RMBSS ticket
                if issue_key.startswith('RMBSS-'):
                    source_issue_key = issue_key
                    logger.info(f"Issue {issue_key} is already a source issue (RMBSS)")
                else:
                    # Look for related RMBSS ticket in results_file
                    results_file = os.path.join('data', 'clm_results', 'creation_results.json')
                    if os.path.exists(results_file):
                        with open(results_file, 'r', encoding='utf-8') as f:
                            creation_results = json.load(f)
                            # Find entry where clm_error_key matches our issue_key
                            for result in creation_results:
                                if result.get('clm_error_key') == issue_key:
                                    source_issue_key = result.get('source_key')
                                    logger.info(f"Found source issue {source_issue_key} for CLM Error {issue_key}")
                                    break

                # If we found the source ticket, try to get its component
                if source_issue_key:
                    source_issue_details = self.clm_creator.get_issue_details(source_issue_key)
                    if source_issue_details:
                        # Extract component from source ticket
                        component = source_issue_details.get('component', '')
                        if component:
                            logger.info(f"Found component '{component}' in source issue {source_issue_key}")

                            # Use the enhanced mapping function
                            product_group_id, subsystem_id, _, subsystem_version_id = self._get_component_mapping_data(
                                component)

                            logger.info(
                                f"Mapped component '{component}' to Product Group ID '{product_group_id}' and Subsystem ID '{subsystem_id}'")
            except Exception as e:
                logger.error(f"Error finding source issue for {issue_key}: {e}", exc_info=True)

            # Get field options for the issue
            field_options = self._get_field_options_for_issue(issue_key)

            # Common fields for all transitions
            common_fields = [
                # Common fields using mapped values
                ('Product Group', product_group_id),
                ('Subsystem', subsystem_id),
                ('customfield_17813', '169086'),  # Investment - NBSS 2025
                ('customfield_17812', '170958'),  # Text field
            ]

            # Specific fields for transition to Studying
            studying_fields = [
                ('customfield_12405', {"value": "12010"}),
                ('customfield_17816', {"id": "25405"}),  # Current Sprint
            ]

            # Specific fields for transition to Received
            received_fields = [
                ('customfield_12409', '35200'),  # Subtype
                ('customfield_12415', '12030'),  # Workaround
                ('customfield_12408', subsystem_version_id),  # Subsystem version with proper mapping
            ]

            # Form final list of fields based on transition type
            fields_to_set = []
            fields_to_set.extend(common_fields)

            if transition_type == 'studying':
                fields_to_set.extend(studying_fields)
            elif transition_type == 'received':
                fields_to_set.extend(received_fields)

            # Add custom fields that might be passed from outside
            for k, v in custom_fields.items():
                # Check if field is already in the list
                if not any(field_name == k for field_name, _ in fields_to_set):
                    fields_to_set.append((k, v))

            # Set fields with proper format based on field type
            successful_fields = 0
            required_fields = len(fields_to_set)

            # Process all fields with field_ids lookup or special handling
            for field_name, value in fields_to_set:
                try:
                    # Special handling for custom field IDs passed directly
                    if field_name.startswith('customfield_'):
                        field_id = field_name
                        logger.info(f"Using direct field ID: {field_id}")
                    else:
                        field_id = self.field_ids.get(field_name)
                        if not field_id:
                            logger.warning(f"Could not find field ID for '{field_name}', skipping")
                            continue

                    # Get field info from create metadata
                    field_info = {}
                    if self.create_meta and 'fields' in self.create_meta:
                        field_info = self.create_meta['fields'].get(field_id, {})

                    schema = field_info.get('schema', {})
                    field_type = schema.get('type', '')
                    custom_type = schema.get('custom', '')

                    # Check if field is a select list
                    is_select = (
                            field_info.get('allowedValues') is not None or
                            custom_type == 'com.atlassian.jira.plugin.system.customfieldtypes:select' or
                            custom_type == 'com.atlassian.jira.plugin.system.customfieldtypes:multiselect'
                    )

                    # Check if field is an array
                    is_array = field_type == 'array' or custom_type == 'com.atlassian.jira.plugin.system.customfieldtypes:multiselect'

                    logger.info(
                        f"Setting field '{field_name}' (id: {field_id}, type: {field_type}, custom: {custom_type}, is_select: {is_select}, is_array: {is_array})")

                    # Special handling for specific field formats
                    if field_id in ['customfield_12311', 'customfield_12312']:
                        # These fields use a different structure for SQLFeed plugin
                        result_fields[field_id] = [value]  # Using array format
                        logger.info(f"Set SQLFeed field '{field_id}' as array: [{value}]")
                        successful_fields += 1
                    elif field_name in ['customfield_17813', 'customfield_17812']:
                        # These fields expect array of strings
                        result_fields[field_id] = [value]
                        logger.info(f"Set field '{field_id}' as array of strings: [{value}]")
                        successful_fields += 1
                    elif field_id == 'customfield_12408':  # Subsystem version
                        # This field is passed as array of strings
                        result_fields[field_id] = [value]
                        logger.info(f"Set field '{field_id}' as array of strings: [{value}]")
                        successful_fields += 1
                    elif field_id == 'customfield_12405':  # Error Type
                        # String value for this field
                        result_fields[field_id] = [value]
                        logger.info(f"Set field '{field_id}' as array (default): [{value}]")
                        successful_fields += 1
                    elif field_name in ['Product Group', 'Subsystem']:
                        # For these fields use ID directly
                        result_fields[field_id] = {'id': value}
                        logger.info(f"Set field '{field_name}' with direct ID '{value}'")
                        successful_fields += 1
                    elif is_select:
                        # For select fields like Product Group and Subsystem, use ID directly
                        result_fields[field_id] = {'id': value}
                        logger.info(f"Set field '{field_id}' as object with id: {{id: {value}}}")
                        successful_fields += 1
                    elif is_array:
                        # For arrays without additional info use array of strings
                        result_fields[field_id] = [value]
                        logger.info(f"Set field '{field_id}' as array (default): [{value}]")
                        successful_fields += 1
                    else:
                        # For other fields use string directly
                        result_fields[field_id] = value
                        logger.info(f"Set field '{field_id}' as string: {value}")
                        successful_fields += 1
                except Exception as e:
                    logger.error(f"Error setting field '{field_id}': {e}")
                    # Continue with other fields even if one fails

            # Check if all required fields were successfully set
            if successful_fields < required_fields:
                logger.error(f"Not all required fields were set successfully: {successful_fields}/{required_fields}")
                logger.warning(f"Continuing with partial field set for {issue_key}")

            return result_fields
        except Exception as e:
            logger.error(f"Error preparing transition fields: {e}", exc_info=True)
            return {}

    def _match_component_to_subsystem(self, component):
        """
        Match component to subsystem based on enhanced mapping logic.
        Uses the new _get_component_mapping_data method for consistent mapping.

        Args:
            component (str): Component name

        Returns:
            str: Matched subsystem name or default value
        """
        if not component:
            logger.warning(f"No component provided. Using default 'NBSS_CORE'")
            return "NBSS_CORE"  # Default subsystem

        # Use the enhanced mapping function to get mapping data
        _, _, subsystem_name, _ = self._get_component_mapping_data(component)

        # Return just the subsystem name for backward compatibility
        logger.info(f"Matched component '{component}' to subsystem '{subsystem_name}'")
        return subsystem_name

    def _load_subsystem_mapping(self):
        """
        Load subsystem mapping from Excel file

        Returns:
            dict: Mapping from component to subsystem
        """
        try:
            # Path to the Excel file
            excel_file = os.path.join('data', 'subsystem_mapping.xlsx')

            if not os.path.exists(excel_file):
                logger.warning(f"Subsystem mapping file not found: {excel_file}")
                return {}

            # Read Excel file
            df = pd.read_excel(excel_file)

            # Filter for DIGITAL_BSS product group
            df_filtered = df[df['ProdCode'] == 'DIGITAL_BSS']

            # Get all subsystems (SubCode values) for DIGITAL_BSS
            subsystems = df_filtered['SubCode'].unique().tolist()

            logger.info(f"Loaded {len(subsystems)} subsystems for DIGITAL_BSS: {subsystems}")

            return subsystems
        except Exception as e:
            logger.error(f"Error loading subsystem mapping: {e}", exc_info=True)
            return []

    def get_create_meta(self):
        """
        Get create metadata for CLM/Error to identify required fields and field types

        Returns:
            dict: Create metadata or None if error
        """
        if not self.api_token:
            logger.error("API token not available, cannot fetch create metadata")
            return None

        try:
            url = f"{self.jira_url}/rest/api/2/issue/createmeta?projectKeys=CLM&issuetypeNames=Error&expand=projects.issuetypes.fields"
            logger.info(f"Fetching create metadata from {url}")

            response = requests.get(
                url,
                headers=self.headers,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Error getting create metadata: {response.status_code}")
                return None

            meta_data = response.json()

            # Extract field information
            try:
                projects = meta_data.get('projects', [])
                if not projects:
                    logger.error("No projects found in metadata")
                    return None

                issue_types = projects[0].get('issuetypes', [])
                if not issue_types:
                    logger.error("No issue types found in metadata")
                    return None

                fields = issue_types[0].get('fields', {})

                # Log all available fields and their properties
                logger.info(f"Found {len(fields)} fields in create metadata")
                required_fields = {}

                for field_id, field_info in fields.items():
                    is_required = field_info.get('required', False)
                    field_name = field_info.get('name', '')
                    schema = field_info.get('schema', {})
                    field_type = schema.get('type', '')
                    custom_type = schema.get('custom', '')

                    # Check if field has allowed values
                    has_options = field_info.get('allowedValues') is not None

                    logger.info(
                        f"Field: {field_name} (id: {field_id}, type: {field_type}, custom: {custom_type}, has_options: {has_options}, required: {is_required})")

                    if is_required:
                        required_fields[field_id] = field_name

                logger.info(f"Found {len(required_fields)} required fields: {required_fields}")

                meta = {
                    'fields': fields
                }

                return meta
            except Exception as e:
                logger.error(f"Error parsing metadata: {e}")
                return None

        except Exception as e:
            logger.error(f"Error getting create metadata: {e}", exc_info=True)
            return None

    def _get_field_ids(self):
        """
        Get field IDs for CLM project from the create metadata

        Returns:
            dict: Mapping of field names to field IDs
        """
        try:
            logger.info("Extracting field IDs from create metadata")
            field_mappings = {
                'Product Group': None,
                'Subsystem': None,
                'Urgency': None,
                'Company': None,
                'Production/Test': None
            }

            # If we have metadata, extract field IDs
            if self.create_meta:
                fields = self.create_meta.get('fields', {})

                # Map field names to IDs
                for field_id, field_info in fields.items():
                    name = field_info.get('name', '')
                    if name in field_mappings:
                        field_mappings[name] = field_id
                        logger.info(f"Mapped field '{name}' to ID '{field_id}'")

                        # Check if this is a multi-select field
                        schema = field_info.get('schema', {})
                        field_type = schema.get('type', '')
                        is_array = schema.get('custom',
                                              '') == 'com.atlassian.jira.plugin.system.customfieldtypes:multiselect'

                        if is_array or field_type == 'array':
                            logger.info(f"Field '{name}' is a multi-select field")

                        # Check for allowedValues
                        allowed_values = field_info.get('allowedValues', [])
                        if allowed_values:
                            self.field_options_cache[field_id] = allowed_values
                            logger.info(f"Cached {len(allowed_values)} options for field '{name}'")

            # Fallback to API call if needed
            if not all(field_mappings.values()):
                logger.info("Some field IDs not found in metadata, fetching from API")

                if not self.api_token:
                    logger.error("Cannot fetch field metadata: API token not available")
                    return field_mappings

                url = f"{self.jira_url}/rest/api/2/field"
                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=30
                )

                if response.status_code != 200:
                    logger.error(f"Error fetching field metadata: {response.status_code}")
                    return field_mappings

                api_fields = response.json()
                logger.info(f"Successfully fetched {len(api_fields)} fields from Jira API")

                # Map field names to IDs
                for field in api_fields:
                    name = field.get('name', '')
                    id = field.get('id', '')
                    if name in field_mappings and field_mappings[name] is None:
                        field_mappings[name] = id
                        logger.info(f"Mapped field '{name}' to ID '{id}' from API")

            # Fallback to hardcoded values if not found
            if not field_mappings['Product Group']:
                field_mappings['Product Group'] = 'customfield_10509'
            if not field_mappings['Subsystem']:
                field_mappings['Subsystem'] = 'customfield_14900'
            if not field_mappings['Urgency']:
                field_mappings['Urgency'] = 'customfield_13004'
            if not field_mappings['Company']:
                field_mappings['Company'] = 'customfield_16300'
            if not field_mappings['Production/Test']:
                field_mappings['Production/Test'] = 'customfield_17200'

            return field_mappings
        except Exception as e:
            logger.error(f"Error getting field IDs: {e}", exc_info=True)
            # Return default mappings
            return {
                'Product Group': 'customfield_10509',
                'Subsystem': 'customfield_14900',
                'Urgency': 'customfield_13004',
                'Company': 'customfield_16300',
                'Production/Test': 'customfield_17200'
            }

    def _transition_to_studying(self, issue_key):
        """
        Transition a CLM Error issue to Studying status using enhanced component mapping.

        Args:
            issue_key (str): CLM Error issue key

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.api_token:
            logger.error(f"API token not available, cannot transition CLM Error {issue_key}")
            return False

        try:
            logger.info(f"Starting transition of CLM Error {issue_key} to Studying status")

            # Get transition ID
            transition_id = self._get_transition_id(issue_key, 'Studying')

            if not transition_id:
                logger.error(f"Could not find transition ID for 'Studying' for issue {issue_key}")
                return False

            # Use enhanced _prepare_transition_fields method for field preparation
            # This will automatically use component mapping logic
            transition_fields = self._prepare_transition_fields(
                issue_key,
                {
                    'customfield_12405': '12010',  # Error Type
                    'customfield_17813': '169086',  # Investment - NBSS 2025
                    'customfield_17812': '170958'  # Text field
                },
                transition_type='studying'
            )

            # Explicitly set customfield_12405 as JSON object with ID
            if 'customfield_12405' in transition_fields:
                transition_fields['customfield_12405'] = {"id": "12010"}

            if 'customfield_17816' in transition_fields:
                transition_fields['customfield_17816'] = {"id": "25405"}  # Current Sprint

            logger.info(f"Prepared fields for transition to Studying: {json.dumps(transition_fields)}")

            # Make transition request
            url = f"{self.clm_creator.jira_url}/rest/api/2/issue/{issue_key}/transitions"

            payload = {
                "transition": {"id": transition_id}
            }

            # Add prepared fields if available
            if transition_fields:
                payload["fields"] = transition_fields

            result = self._make_api_request('POST', url, payload)

            if result is not None:
                logger.info(f"Successfully transitioned {issue_key} to Studying")
                return True

            # If first attempt failed, try alternative approaches

            # Try with minimal fields
            logger.info(f"First attempt failed, trying alternative approach for {issue_key}")

            minimal_fields = {
                "customfield_12405": {"value": "31-Insignificant,caused by reasons beyond control of Nexign"},
                "customfield_17813": ["169086"],  # Investment
                "customfield_17812": ["170958"],  # Text field
            }

            # Get component info from related source issue
            source_issue_key = None
            try:
                # Find source issue for this CLM issue
                if issue_key.startswith('RMBSS-'):
                    source_issue_key = issue_key
                else:
                    results_file = os.path.join('data', 'clm_results', 'creation_results.json')
                    if os.path.exists(results_file):
                        with open(results_file, 'r', encoding='utf-8') as f:
                            creation_results = json.load(f)
                            for result in creation_results:
                                if result.get('clm_error_key') == issue_key:
                                    source_issue_key = result.get('source_key')
                                    break

                if source_issue_key:
                    # Get component from source issue
                    source_issue_details = self.clm_creator.get_issue_details(source_issue_key)
                    if source_issue_details:
                        component = source_issue_details.get('component', '')
                        if component:
                            # Get mapped Product Group and Subsystem
                            product_group_id, subsystem_id, _, _ = self._get_component_mapping_data(component)

                            # Add Product Group and Subsystem fields
                            minimal_fields["customfield_12311"] = [product_group_id]  # Product Group
                            minimal_fields["customfield_12312"] = [subsystem_id]  # Subsystem

                            logger.info(
                                f"Added Product Group ID {product_group_id} and Subsystem ID {subsystem_id} from component '{component}'")
            except Exception as e:
                logger.error(f"Error getting component mapping data: {e}", exc_info=True)

            # If we didn't get mapping from component, use default values
            if "customfield_12311" not in minimal_fields:
                minimal_fields["customfield_12311"] = ["1011"]  # Default DIGITAL_BSS
                minimal_fields["customfield_12312"] = ["1011"]  # Default NBSS_CORE

            payload["fields"] = minimal_fields

            result = self._make_api_request('POST', url, payload)

            if result is not None:
                logger.info(f"Successfully transitioned {issue_key} to Studying with minimal fields")
                return True

            # Try without customfield_12405 (Error Type)
            logger.info(f"Trying without customfield_12405 for {issue_key}")

            fields_no_12405 = {k: v for k, v in minimal_fields.items() if k != 'customfield_12405'}
            payload["fields"] = fields_no_12405

            result = self._make_api_request('POST', url, payload)

            if result is not None:
                logger.info(f"Successfully transitioned {issue_key} to Studying without customfield_12405")
                return True

            # Last attempt - try without any fields
            logger.info(f"Trying transition without fields")

            minimal_payload = {
                "transition": {"id": transition_id}
            }

            minimal_result = self._make_api_request('POST', url, minimal_payload)

            if minimal_result is not None:
                logger.info(f"Successfully transitioned {issue_key} to Studying without any fields")
                return True

            logger.error(f"Failed to transition {issue_key} to Studying after multiple attempts")
            return False

        except Exception as e:
            logger.error(f"Error transitioning {issue_key} to Studying: {e}", exc_info=True)
            return False

    def _transition_to_received(self, issue_key):
        """
        Transition a CLM Error issue to Received status using enhanced component mapping.

        Args:
            issue_key (str): CLM Error issue key

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get transition ID
            transition_id = self._get_transition_id(issue_key, 'Received')

            if not transition_id:
                return False

            # Get issue details
            issue_details = self._get_issue_details(issue_key)
            if not issue_details:
                logger.error(f"Could not get issue details for {issue_key}")
                return False

            # Get summary from issue details
            summary = issue_details.get('summary', 'No summary provided')

            # Find source issue for component mapping
            source_issue_key = None
            component = None
            subsystem_version_id = "22550"  # Default version ID

            try:
                # Find source issue for this CLM issue
                if issue_key.startswith('RMBSS-'):
                    source_issue_key = issue_key
                else:
                    results_file = os.path.join('data', 'clm_results', 'creation_results.json')
                    if os.path.exists(results_file):
                        with open(results_file, 'r', encoding='utf-8') as f:
                            creation_results = json.load(f)
                            for result in creation_results:
                                if result.get('clm_error_key') == issue_key:
                                    source_issue_key = result.get('source_key')
                                    break

                if source_issue_key:
                    # Get component from source issue
                    source_issue_details = self.clm_creator.get_issue_details(source_issue_key)
                    if source_issue_details:
                        component = source_issue_details.get('component', '')
            except Exception as e:
                logger.error(f"Error finding source issue: {e}", exc_info=True)

            # If we found a component, get component mapping
            if component:
                # Get mapped Product Group, Subsystem, and Version
                product_group_id, subsystem_id, _, subsystem_version_id = self._get_component_mapping_data(component)
                logger.info(f"Using Subsystem version ID {subsystem_version_id} for component '{component}'")
            else:
                # Get latest version as fallback
                subsystem_version_id = self._get_latest_version()
                logger.info(f"Using latest version ID {subsystem_version_id} (fallback)")

            # Prepare fields for transition using enhanced method
            fields = self._prepare_transition_fields(issue_key, {
                'customfield_12409': '35200',  # Subtype
                'customfield_12397': summary,  # Summary
                'customfield_12408': subsystem_version_id,  # Subsystem version
                'customfield_12415': '12030',  # Workaround
                'customfield_17813': '169086',  # Investment
                'customfield_17812': '170958'  # Text field
            }, transition_type='received')

            logger.info(f"Attempting transition to Received with fields: {fields}")

            if self._try_transition(issue_key, transition_id, fields):
                return True

            # If not successful, try alternative field formats

            # Variant 2: Simpler field format
            simple_fields = {
                "customfield_12409": {"id": "35200"},
                "customfield_12397": summary,
                "customfield_12408": [subsystem_version_id],
                "customfield_12415": {"id": "12030"}
            }

            # Add Product Group and Subsystem if we have component information
            if component:
                product_group_id, subsystem_id, _, _ = self._get_component_mapping_data(component)
                simple_fields["customfield_12311"] = [product_group_id]  # Product Group
                simple_fields["customfield_12312"] = [subsystem_id]  # Subsystem

            if self._try_transition(issue_key, transition_id, simple_fields):
                return True

            # Variant 3: All fields as arrays
            array_fields = {
                "customfield_12409": {"id": "35200"},
                "customfield_12397": summary,
                "customfield_12408": [subsystem_version_id],
                "customfield_12415": {"id": "12030"},
                "customfield_17813": ["169086"],
                "customfield_17812": ["170958"]
            }

            # Add Product Group and Subsystem if we have component information
            if component:
                product_group_id, subsystem_id, _, _ = self._get_component_mapping_data(component)
                array_fields["customfield_12311"] = [product_group_id]  # Product Group
                array_fields["customfield_12312"] = [subsystem_id]  # Subsystem

            if self._try_transition(issue_key, transition_id, array_fields):
                return True

            # Variant 4: Minimal fields
            minimal_fields = {
                "customfield_12409": {"id": "35200"},
                "customfield_12408": [subsystem_version_id],
                "customfield_12415": {"id": "12030"},
                "customfield_12397": summary
            }

            if self._try_transition(issue_key, transition_id, minimal_fields):
                return True

            logger.error(f"All attempts to transition {issue_key} to Received failed")
            return False

        except Exception as e:
            logger.error(f"Error transitioning {issue_key} to Received: {e}", exc_info=True)
            return False

    def _try_transition(self, issue_key, transition_id, fields):
        """
        Вспомогательный метод для попытки перехода с заданными полями

        Args:
            issue_key (str): Ключ задачи
            transition_id (str): ID перехода
            fields (dict): Поля для перехода

        Returns:
            bool: True если успешно, False если ошибка
        """
        try:
            # Execute transition
            url = f"{self.clm_creator.jira_url}/rest/api/2/issue/{issue_key}/transitions"

            payload = {
                "transition": {"id": transition_id}
            }

            # Добавляем поля только если они есть
            if fields:
                payload["fields"] = fields

            # Логируем JSON для отладки
            import json
            logger.info(f"Trying transition payload: {json.dumps(payload)}")

            result = self._make_api_request('POST', url, payload)

            if result is not None:
                logger.info(f"Successfully transitioned {issue_key} to Received")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Error in transition attempt: {e}", exc_info=True)
            return False