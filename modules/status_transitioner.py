"""
CLM Status Transition Module
Handles automatic transitions of CLM Error tickets through different statuses
Переиспользует логику ClmErrorCreator для работы с Jira API
"""

import time
import threading
import re
import logging
from datetime import datetime, timedelta

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
        Make an API request to Jira using the ClmErrorCreator's credentials
        С сохранением последней ошибки

        Args:
            method (str): HTTP method (GET, POST, etc.)
            url (str): API URL
            data (dict, optional): JSON data for POST requests

        Returns:
            dict: JSON response or None if error
        """
        try:
            import requests
            import json

            # Извлекаем ключ задачи из URL
            issue_key = None
            import re
            match = re.search(r'/issue/([A-Z]+-\d+)/', url)
            if match:
                issue_key = match.group(1)

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

            if response.status_code not in [200, 201, 204]:
                logger.error(f"Error making API request to {url}: {response.status_code}")
                logger.error(f"Response: {response.text[:500]}...")

                # Сохраняем ошибку, если это ошибка перехода
                if issue_key and '/transitions' in url:
                    try:
                        error_data = json.loads(response.text)
                        # Сохраняем ошибку в хранилище
                        if not hasattr(self, '_last_errors'):
                            self._last_errors = {}
                        self._last_errors[issue_key] = error_data
                    except:
                        pass

                return None

            if response.status_code == 204:  # No content
                return {}

            return response.json()

        except Exception as e:
            logger.error(f"Error making API request: {e}", exc_info=True)
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
        Get the latest version ID for customfield_12408
        Reuses ClmErrorCreator's field handling methods

        Returns:
            str: ID of the latest version or None if error
        """
        try:
            # Жестко закодированные версии для выбора последней
            # В реальной системе можно получить через API или другие методы
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
                    # Разбиваем на компоненты и преобразуем в числа
                    try:
                        components = [int(x) for x in version_str.split('.')]

                        # Сравниваем с текущей последней версией
                        if latest_version is None or components > latest_version:
                            latest_version = components
                            latest_version_id = version_id
                            logger.info(f"Found newer version: {version_name} (ID: {version_id})")
                    except ValueError:
                        continue

            if latest_version_id:
                logger.info(f"Latest version ID: {latest_version_id}")
                return latest_version_id
            else:
                # Возвращаем ID последней версии из списка, если не удалось определить
                return "22550"

        except Exception as e:
            logger.error(f"Error getting latest version: {e}", exc_info=True)
            return "22550"  # Возвращаем ID по умолчанию в случае ошибки

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

    def _transition_to_studying(self, issue_key):
        """
        Transition a CLM Error issue to Studying status
        Использует улучшенный метод подготовки полей

        Args:
            issue_key (str): CLM Error issue key

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Получаем ID перехода
            transition_id = self._get_transition_id(issue_key, 'Studying')

            if not transition_id:
                return False

            # Подготавливаем поля для перехода
            fields = self._prepare_transition_fields(issue_key, {
                # Только поля, необходимые для перехода в Studying
                'customfield_12405': '12010',  # Current Sprint
                'customfield_17813': '169086',  # Investment - NBSS 2025
                'customfield_17812': '170958'  # Text field
            })

            logger.info(f"Attempting transition to Studying with fields: {fields}")

            if self._try_transition(issue_key, transition_id, fields):
                return True

            # Если не получилось, попробуем еще несколько вариантов форматов

            # Вариант 2: Все поля как строки
            fields = {
                "customfield_12405": "12010",
                "customfield_17813": "169086",
                "customfield_17812": "170958"
            }

            if self._try_transition(issue_key, transition_id, fields):
                return True

            # Вариант 3: Все поля как объекты с id
            fields = {
                "customfield_12405": {"id": "12010"},
                "customfield_17813": {"id": "169086"},
                "customfield_17812": {"id": "170958"}
            }

            if self._try_transition(issue_key, transition_id, fields):
                return True

            # Вариант 4: Минимальный набор полей
            if self._try_transition(issue_key, transition_id, {"customfield_12405": ["12010"]}):
                return True

            # Вариант 5: Без полей
            if self._try_transition(issue_key, transition_id, {}):
                return True

            logger.error(f"All attempts to transition {issue_key} to Studying failed")
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