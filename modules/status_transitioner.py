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


        # Load subsystem mapping from Excel file
        self.subsystem_mapping = self._load_subsystem_mapping()

        # Get metadata for CLM project to identify fields and options
        self.create_meta = self.get_create_meta()
        self.field_ids = self._get_field_ids()

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
        С поддержкой перехода из статуса Authorized"""
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
                    if current_status in ['Open',
                                          'Authorized'] and time_since_creation.total_seconds() >= self.time_delay:
                        logger.info(f"Time to transition {clm_key} to Studying from {current_status}")
                        self._transition_to_studying(clm_key)

                    # Always try to transition to Received if not already in a final status
                    if current_status in ['Open', 'Studying', 'Authorized']:
                        # If more than 10 minutes passed since creation, try to transition to Received
                        if time_since_creation.total_seconds() >= (self.time_delay * 2):
                            logger.info(f"Time to transition {clm_key} to Received from {current_status}")
                            self._transition_to_received(clm_key)

            except Exception as e:
                logger.error(f"Error in CLM transition monitor: {e}", exc_info=True)

            # Sleep for a while before checking again
            time.sleep(60)  # Check every minute

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

    def _find_latest_version_id(self, field_options, field_id):
        """
        Find the latest version ID from available versions

        Args:
            field_options (dict): Field options dictionary
            field_id (str): Field ID for versions

        Returns:
            str: Latest version ID or None if not found
        """
        if not field_options or field_id not in field_options:
            return None

        versions = []
        for option in field_options[field_id]:
            option_value = option.get('value', option.get('name', ''))
            option_id = option.get('id')
            # Extract version number using regex
            import re
            match = re.search(r'(\d+(\.\d+)*)', option_value)
            if match:
                version_str = match.group(1)
                try:
                    # Convert version to tuple of integers for comparison
                    version_parts = [int(part) for part in version_str.split('.')]
                    versions.append((version_parts, option_id, option_value))
                except ValueError:
                    # If conversion fails, still include the version
                    versions.append(([0], option_id, option_value))
            else:
                # Include non-versioned options with lowest priority
                versions.append(([0], option_id, option_value))

        # Sort versions by numeric value (descending)
        versions.sort(reverse=True)
        if versions:
            logger.info(f"Found latest version: {versions[0][2]} (ID: {versions[0][1]})")
            return versions[0][1]

        return None

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

    def _get_field_options(self, field_id):
        """Получить доступные опции для поля через API"""
        try:
            url = f"{self.clm_creator.jira_url}/rest/api/2/field/{field_id}/option"

            response = requests.get(
                url,
                headers=self.clm_creator.headers,
                timeout=30
            )

            if response.status_code != 200:
                logger.warning(f"Could not fetch options for {field_id}: {response.status_code}")

                # Попробуем альтернативный способ получения опций
                meta_url = f"{self.clm_creator.jira_url}/rest/api/2/issue/createmeta?projectKeys=CLM&issuetypeNames=Error&expand=projects.issuetypes.fields"
                meta_response = requests.get(
                    meta_url,
                    headers=self.clm_creator.headers,
                    timeout=30
                )

                if meta_response.status_code != 200:
                    logger.warning(f"Could not fetch metadata: {meta_response.status_code}")
                    return []

                meta = meta_response.json()

                try:
                    # Извлекаем опции из метаданных
                    fields = meta.get('projects', [])[0].get('issuetypes', [])[0].get('fields', {})
                    field_info = fields.get(field_id, {})
                    allowed_values = field_info.get('allowedValues', [])

                    logger.info(f"Found {len(allowed_values)} options for {field_id} in metadata")
                    return allowed_values
                except (IndexError, KeyError) as e:
                    logger.error(f"Error parsing metadata: {e}")
                    return []

            options_data = response.json()
            return options_data.get('values', [])
        except Exception as e:
            logger.error(f"Error getting field options: {e}", exc_info=True)
            return []

    def _prepare_transition_fields(self, issue_key, custom_fields=None):
        """
        Подготовка полей для перехода с использованием того же подхода, что и при создании тикета

        Args:
            issue_key (str): Ключ задачи Jira
            custom_fields (dict): Дополнительные поля и их значения

        Returns:
            dict: Подготовленные поля для перехода
        """
        try:
            # Инициализируем пустой словарь для полей
            result_fields = {}

            # Если не переданы пользовательские поля, используем пустой словарь
            custom_fields = custom_fields or {}

            # Получаем информацию о метаданных полей
            field_meta = {}
            if hasattr(self.clm_creator, 'create_meta') and self.clm_creator.create_meta:
                if 'fields' in self.clm_creator.create_meta:
                    field_meta = self.clm_creator.create_meta['fields']

            # Подготавливаем список полей для установки
            fields_to_set = [
                # Для перехода в Studying
                ('customfield_12405', '12010'),  # Current Sprint
                ('customfield_17813', '169086'),  # Investment - NBSS 2025
                ('customfield_17812', '170958'),  # Text field

                # Для перехода в Received
                ('customfield_12409', '35200'),  # Subtype
                ('customfield_12415', '12030'),  # Workaround

                # Специальные поля, которые могут быть переданы извне
                *[(k, v) for k, v in custom_fields.items()]
            ]

            # Устанавливаем поля с правильным форматом
            for field_id, value in fields_to_set:
                try:
                    # Получаем информацию о поле из метаданных
                    field_info = field_meta.get(field_id, {})
                    schema = field_info.get('schema', {})
                    field_type = schema.get('type', '')
                    custom_type = schema.get('custom', '')

                    # Проверяем, является ли поле списком с возможностью выбора
                    is_select = (
                            field_info.get('allowedValues') is not None or
                            custom_type == 'com.atlassian.jira.plugin.system.customfieldtypes:select' or
                            custom_type == 'com.atlassian.jira.plugin.system.customfieldtypes:multiselect'
                    )

                    # Проверяем, является ли поле массивом
                    is_array = field_type == 'array' or custom_type == 'com.atlassian.jira.plugin.system.customfieldtypes:multiselect'

                    logger.info(
                        f"Setting field '{field_id}' (type: {field_type}, custom: {custom_type}, is_select: {is_select}, is_array: {is_array})")

                    # Специальная обработка для конкретных полей
                    if field_id in ['customfield_17813', 'customfield_17812']:
                        # Эти поля ожидают массив строк
                        result_fields[field_id] = [value]
                        logger.info(f"Set field '{field_id}' as array of strings: [{value}]")
                    elif field_id == 'customfield_12408':  # Subsystem version
                        # Это поле передается как массив строк
                        result_fields[field_id] = [value]
                        logger.info(f"Set field '{field_id}' as array of strings: [{value}]")
                    elif field_id == 'customfield_12405':  # Current Sprint
                        # По аналогии с другими полями, передаем как массив строк
                        result_fields[field_id] = [value]
                        logger.info(f"Set field '{field_id}' as array of strings: [{value}]")
                    elif is_select:
                        # Для полей выбора используем объект с id
                        result_fields[field_id] = {'id': value}
                        logger.info(f"Set field '{field_id}' as object with id: {{id: {value}}}")
                    elif is_array:
                        # Для массивов без доп. информации используем массив строк
                        result_fields[field_id] = [value]
                        logger.info(f"Set field '{field_id}' as array (default): [{value}]")
                    else:
                        # Для остальных полей используем строку
                        result_fields[field_id] = value
                        logger.info(f"Set field '{field_id}' as string: {value}")

                except Exception as e:
                    logger.error(f"Error setting field '{field_id}': {e}", exc_info=True)
                    # Продолжаем с другими полями в случае ошибки

            return result_fields

        except Exception as e:
            logger.error(f"Error preparing transition fields: {e}", exc_info=True)
            return {}


    def _match_component_to_subsystem(self, component):
        """
        Match component to subsystem based on first 3 characters with improved matching

        Args:
            component (str): Component name

        Returns:
            str: Matched subsystem or default value
        """
        if not component or not self.subsystem_mapping:
            logger.warning(f"No component provided or subsystem mapping is empty. Using default 'NBSS_CORE'")
            return "NBSS_CORE"  # Default subsystem

        # Convert component to lowercase for case-insensitive matching
        component_lower = component.lower()
        logger.info(f"Matching component '{component}' to subsystem")

        # List of subsystems with corresponding patterns to check
        # Format: (subsystem, [list of patterns to check])
        subsystem_patterns = [
            ("UDB", ["udb", "user data"]),
            ("NUS", ["nus", "notification"]),
            ("NBSSPORTAL", ["portal", "nbssportal", "ui"]),
            ("CHM", ["chm", "catalog", "product"]),
            ("ATS", ["ats", "task", "automation"]),
            ("SSO", ["sso", "auth", "login"]),
            ("DMS", ["dms", "document"]),
            ("TUDS", ["tuds", "technical"]),
            ("LIS", ["lis", "license"]),
            ("APC", ["apc"]),
            ("CSM", ["csm"]),
            ("ECS", ["ecs"]),
            ("NPM_PORTAL", ["npm"]),
            ("NSG", ["nsg"]),
            ("PASS", ["pass"]),
            ("PAYMENT_MANAGEMENT", ["payment"]),
            ("VMS", ["vms"])
        ]

        # First try to find an exact match in the mapping
        if component in self.subsystem_mapping:
            logger.info(f"Found exact component match in mapping: '{component}'")
            return component

        # Then try to match the component using the patterns
        for subsystem, patterns in subsystem_patterns:
            for pattern in patterns:
                if pattern in component_lower:
                    if subsystem in self.subsystem_mapping:
                        logger.info(
                            f"Matched component '{component}' to subsystem '{subsystem}' using pattern '{pattern}'")
                        return subsystem

        # If no pattern match, try to find a match based on first 3 characters
        for subsystem in self.subsystem_mapping:
            if subsystem and len(subsystem) >= 3 and len(component) >= 3:
                if subsystem[:3].lower() in component_lower or component_lower[:3] in subsystem.lower():
                    logger.info(f"Matched component '{component}' to subsystem '{subsystem}' using first 3 characters")
                    return subsystem

        # If no match found, log and return default
        logger.warning(f"No subsystem match found for component '{component}', using default 'NBSS_CORE'")
        return "NBSS_CORE"  # Default subsystem


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


    def find_option_id(self, field_id, option_name):
        """
        Find the option ID for a given option name in a multi-select field

        Args:
            field_id (str): Field ID
            option_name (str): Option name to find

        Returns:
            str: Option ID or None if not found
        """
        options = self.get_field_options(field_id)

        if not options:
            logger.warning(f"No options found for field {field_id}")
            return None

        # Try to find the option by name (case insensitive)
        option_name_lower = option_name.lower()
        for option in options:
            # Options can have 'value' or 'name' depending on the field type
            option_value = option.get('value', option.get('name', ''))

            if option_value.lower() == option_name_lower:
                option_id = option.get('id')
                logger.info(f"Found option ID {option_id} for '{option_name}' in field {field_id}")
                return option_id

        logger.warning(f"Could not find option '{option_name}' in field {field_id}")

        # Log all available options for debugging
        option_values = [option.get('value', option.get('name', '')) for option in options]
        logger.info(f"Available options for field {field_id}: {option_values}")

        return None

    def _transition_to_studying(self, issue_key):
        """
        Transition a CLM Error issue to Studying status используя тот же формат полей,
        что и при создании тикета в clm_error_creator, с конкретным значением Severity
        """
        if not self.api_token:
            logger.error(f"API token not available, cannot create CLM Error for {issue_key}")
            return None

        try:
            logger.info(f"Starting transition of CLM Error {issue_key}")

            # Get issue details
            issue_details = self._get_issue_details(issue_key)
            if not issue_details:
                logger.error(f"Could not get details for issue {issue_key}, aborting CLM Error creation")
                return None

            # Define the subsystem IDs mapping first
            subsystem_ids = {
                "NBSS_CORE": "1011",  # Default if not matched to a specific ID
                "APC": "23923",
                "CSM": "23817",
                "ECS": "14187",
                "NBSSPORTAL": "27398",
                "NPM_PORTAL": "27400",
                "NSG": "27373",
                "NUS": "23932",
                "PASS": "23764",
                "PAYMENT_MANAGEMENT": "14274",
                "UDB": "23924",
                "VMS": "23767"
            }

            # Получаем ID перехода
            transition_id = self._get_transition_id(issue_key, 'Studying')

            if not transition_id:
                logger.error(f"Could not find transition ID for 'Studying' for issue {issue_key}")
                return False

            # Match component to subsystem
            component = issue_details.get('component', '')
            subsystem = self._match_component_to_subsystem(component)
            logger.info(f"Using subsystem '{subsystem}' for issue {issue_key} with component '{component}'")

            # Determine the subsystem ID based on the matched subsystem
            subsystem_id = None
            if subsystem:
                # First check for exact match
                if subsystem in subsystem_ids:
                    subsystem_id = subsystem_ids[subsystem]
                    logger.info(f"Found exact subsystem ID match: {subsystem_id} for {subsystem}")
                else:
                    # Try to match based on prefix
                    for sub_name, sub_id in subsystem_ids.items():
                        if subsystem.startswith(sub_name) or sub_name.startswith(subsystem):
                            subsystem_id = sub_id
                            logger.info(
                                f"Found partial subsystem ID match: {subsystem_id} for {subsystem} using {sub_name}")
                            break

            # Fallback to NBSS_CORE (default subsystem) if no match found
            if not subsystem_id:
                subsystem_id = subsystem_ids.get("NBSS_CORE", "1011")
                logger.info(f"No subsystem ID match found, using default: {subsystem_id}")

            # Create CLM Error issue
            url = f"{self.jira_url}/rest/api/2/issue/"
            logger.info(f"Creating CLM Error issue at {url}")

            # Prepare base issue data
            issue_data = {
                "fields": {
                    "project": {
                        "key": "CLM"
                    },
                    "issuetype": {
                        "name": "Error"
                    },
                    "summary": issue_details.get('summary', ''),
                    "description": issue_details.get('description', '')
                }
            }

            # Add custom fields with proper ID values
            fields_to_set = [
                # Basic fields
                ('Product Group', '1011'),  # ID for DIGITAL_BSS
                ('Subsystem', subsystem_id),  # Use the resolved subsystem ID
                ('Production/Test', 'DEVELOPMENT'),  # Keep as is if ID not known

                # PM Fields using same approach as Company
                ('customfield_17813', '169086'),  # Investment - NBSS 2025
                ('customfield_17812', '170958'),  # Text field

                # Additional fields from other tabs
                ('customfield_12405', '12010')  # Milestone (can be left empty)
            ]

            # Set each field with the correct format based on the field type
            successful_fields = 0
            required_fields = len(fields_to_set)

            # Process all fields with field_ids lookup or special handling
            for field_name, value in fields_to_set:
                try:
                    # Special handling for custom field IDs that are passed directly
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

                    # Check if this is a select list (options) field
                    is_select = (
                            field_info.get('allowedValues') is not None or
                            custom_type == 'com.atlassian.jira.plugin.system.customfieldtypes:select' or
                            custom_type == 'com.atlassian.jira.plugin.system.customfieldtypes:multiselect'
                    )

                    logger.info(
                        f"Setting field '{field_name}' (id: {field_id}, type: {field_type}, custom: {custom_type}, is_select: {is_select})")

                    # Special handling for specific field formats
                    if field_name == 'customfield_17813':
                        # Investment field - set as an array like Company
                        issue_data['fields'][field_id] = [value]
                        logger.info(f"Set field '{field_name}' as array with value '[{value}]'")
                        successful_fields += 1
                    elif field_name == 'customfield_17812':
                        # Text field - set as an array like Company
                        issue_data['fields'][field_id] = [value]
                        logger.info(f"Set field '{field_name}' as array with value '[{value}]'")
                        successful_fields += 1
                    elif is_select:
                        # For select fields like Product Group and Subsystem, use ID directly
                        if field_name in ['Product Group', 'Subsystem']:
                            # For these fields, we know we should use the ID directly
                            issue_data['fields'][field_id] = {'id': value}
                            logger.info(f"Set field '{field_name}' with direct ID '{value}'")
                            successful_fields += 1
                        else:
                            # For other select fields, try to find the option ID
                            option_id = self.find_option_id(field_id, value)

                            if option_id:
                                # For select fields, use {'id': 'option_id'}
                                issue_data['fields'][field_id] = {'id': option_id}
                                logger.info(f"Set field '{field_name}' to option ID '{option_id}'")
                                successful_fields += 1
                            else:
                                # If we couldn't find the option ID, try using {'value': 'value'}
                                issue_data['fields'][field_id] = {'value': value}
                                logger.info(f"Set field '{field_name}' to value '{value}' (fallback)")
                                successful_fields += 1
                    else:
                        # For non-select fields, use the value directly
                        issue_data['fields'][field_id] = value
                        logger.info(f"Set field '{field_name}' to direct value '{value}'")
                        successful_fields += 1
                except Exception as e:
                    logger.error(f"Error setting field '{field_name}': {e}")
                    # Continue with other fields even if one fails

            # Check if all required fields were successfully set
            if successful_fields < required_fields:
                logger.error(f"Not all required fields were set successfully: {successful_fields}/{required_fields}")
                logger.error(f"Aborting CLM Error creation for {issue_key}")
                return None

            

            logger.info(f"Attempting to transition {issue_key} to Studying with specific Severity value")

            # Выполняем запрос на переход
            url = f"{self.clm_creator.jira_url}/rest/api/2/issue/{issue_key}/transitions"

            payload = {
                "transition": {"id": transition_id},
                "fields": fields_to_set
            }

            result = self._make_api_request('POST', url, payload)

            if result is not None:
                logger.info(f"Successfully transitioned {issue_key} to Studying")
                return True

            # Проверяем, связана ли ошибка с договором заказчика
            error_data = self._get_last_error(issue_key)
            if error_data and 'errorMessages' in error_data:
                for msg in error_data['errorMessages']:
                    if 'Заказчика' in msg and 'договор' in msg:
                        logger.warning(f"Business rule preventing transition: Contract issue")
                        # Если проблема в контракте, вернем False чтобы помечать как ошибку
                        return False

            if result is not None:
                logger.info(f"Successfully transitioned {issue_key} to Studying with explicit Company field")
                return True

            logger.error(f"Failed to transition {issue_key} to Studying after multiple attempts")
            return False

        except Exception as e:
            logger.error(f"Error transitioning {issue_key} to Studying: {e}", exc_info=True)
            return False

    def _transition_to_received(self, issue_key):
        """
        Transition a CLM Error issue to Received status
        Использует улучшенный метод подготовки полей

        Args:
            issue_key (str): CLM Error issue key

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Получаем ID перехода
            transition_id = self._get_transition_id(issue_key, 'Received')

            if not transition_id:
                return False

            # Получаем информацию о тикете
            issue_details = self._get_issue_details(issue_key)
            if not issue_details:
                logger.error(f"Could not get issue details for {issue_key}")
                return False

            # Получаем summary из деталей тикета
            summary = issue_details.get('summary', 'No summary provided')

            # Получаем ID последней версии
            subsystem_version_id = self._find_latest_version_id(
                self._get_field_options_for_issue(issue_key),
                'customfield_12408'
            )

            # Если не удалось получить версию, используем последнюю из скриншота - 1.3.4
            if not subsystem_version_id or subsystem_version_id == "0":  # "0" - это "Please select"
                subsystem_version_id = "1.3.4"  # Последняя версия из скриншота
                logger.info(f"Using latest version from screenshot: {subsystem_version_id}")

            # Подготавливаем поля для перехода
            fields = self._prepare_transition_fields(issue_key, {
                # Обязательные поля для перехода в Received
                'customfield_12409': '35200',  # Subtype
                'customfield_12397': summary,  # Summary
                'customfield_12408': subsystem_version_id,  # Subsystem version
                'customfield_12415': '12030',  # Workaround
                'customfield_17813': '169086',  # Investment
                'customfield_17812': '170958'  # Text field
            })

            logger.info(f"Attempting transition to Received with fields: {fields}")

            if self._try_transition(issue_key, transition_id, fields):
                return True

            # Если не получилось, попробуем еще несколько вариантов форматов

            # Вариант 2: Более простые форматы полей
            simple_fields = {
                "customfield_12409": {"id": "35200"},
                "customfield_12397": summary,
                "customfield_12408": subsystem_version_id,  # Просто строка
                "customfield_12415": {"id": "12030"}
            }

            if self._try_transition(issue_key, transition_id, simple_fields):
                return True

            # Вариант 3: Все поля как массивы
            array_fields = {
                "customfield_12409": {"id": "35200"},
                "customfield_12397": summary,
                "customfield_12408": [subsystem_version_id],
                "customfield_12415": {"id": "12030"},
                "customfield_17813": ["169086"],
                "customfield_17812": ["170958"]
            }

            if self._try_transition(issue_key, transition_id, array_fields):
                return True

            # Вариант 4: Без дополнительных полей
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

    def _get_last_error(self, issue_key):
        """
        Получить последнюю ошибку из лога для данного тикета

        Args:
            issue_key (str): Ключ задачи

        Returns:
            dict: Словарь с ошибками или None
        """
        # Если у нас нет хранилища ошибок, создадим его
        if not hasattr(self, '_last_errors'):
            self._last_errors = {}

        # Возвращаем последнюю ошибку для тикета
        return self._last_errors.get(issue_key)

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

    def _get_subsystem_version_for_issue(self, issue_key):
        """
        Получить доступные версии Subsystem для конкретного тикета и выбрать последнюю

        Args:
            issue_key (str): Ключ задачи

        Returns:
            str: ID последней версии Subsystem или None
        """
        try:
            # В идеале здесь должен быть запрос к Jira API для получения доступных версий
            # для конкретного Subsystem этого тикета
            # Но в отсутствие прямого доступа к этой информации используем стандартный подход

            # Получаем информацию о тикете, включая поля Subsystem
            issue_details = self._get_issue_details(issue_key)
            if not issue_details:
                logger.error(f"Could not get issue details for {issue_key}")
                return "22550"  # Возвращаем значение по умолчанию

            # В идеальном случае мы бы извлекли значение Subsystem из тикета
            # и затем запросили доступные версии для этого Subsystem

            # Но пока используем жесткий список версий и выбираем последнюю
            versions = [
                {"id": "22400", "value": "NBSS 5.2.0"},
                {"id": "22450", "value": "NBSS 5.3.0"},
                {"id": "22500", "value": "NBSS 5.4.0"},
                {"id": "22550", "value": "NBSS 5.5.0"}
            ]

            # Находим версию с наибольшим номером
            latest_version = None
            latest_version_id = None

            for option in versions:
                version_name = option.get('value', '')
                version_id = option.get('id')

                # Извлечение номера версии с помощью regex
                match = re.search(r'(\d+\.\d+\.\d+)', version_name)
                if match:
                    version_str = match.group(1)
                    try:
                        components = [int(x) for x in version_str.split('.')]

                        if latest_version is None or components > latest_version:
                            latest_version = components
                            latest_version_id = version_id
                            logger.info(f"Found newer version: {version_name} (ID: {version_id})")
                    except ValueError:
                        continue

            if latest_version_id:
                logger.info(f"Latest version ID for {issue_key}: {latest_version_id}")
                return latest_version_id
            else:
                # Возвращаем ID последней версии из списка, если не удалось определить
                return "22550"

        except Exception as e:
            logger.error(f"Error getting subsystem version for {issue_key}: {e}", exc_info=True)
            return "22550"  # Возвращаем ID по умолчанию в случае ошибки