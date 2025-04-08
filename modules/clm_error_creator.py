import os
import json
import logging
from datetime import datetime

import pandas as pd
import requests
from io import BytesIO
from .status_transitioner import ClmStatusTransitioner


# Get logger
logger = logging.getLogger(__name__)


class ClmErrorCreator:
    def __init__(self, jira_url=None):
        """
        Initialize CLM Error creator

        Args:
            jira_url (str): Base URL for your Jira instance
        """
        self.jira_url = jira_url or 'https://jira.nexign.com'
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

        # Initialize the status transitioner
        self.status_transitioner = ClmStatusTransitioner(self)

        # Start the transition monitor if API token is available
        if self.api_token:
            self.status_transitioner.start_transition_monitor()
            logger.info("Started CLM Error status transition monitor")

        # Initialize cache for field options to avoid repeated API calls
        self.field_options_cache = {}

        # Cache for link types
        self.link_types = []
        self.default_link_type = "Relates"  # Default link type if none specified

        # Fetch and cache available link types
        if self.api_token:
            self.link_types = self.get_available_link_types()

            # Find the best link type to use as default
            # Поместили "Requirements" в начало списка предпочтительных типов связи
            preferred_link_types = ["Requirements", "Relates", "relates to", "relates", "Related", "Relationship",
                                    "CLM Link", "links CLM to", "Relates to"]

            for preferred in preferred_link_types:
                if any(lt.get('name') == preferred for lt in self.link_types):
                    self.default_link_type = preferred
                    logger.info(f"Using '{preferred}' as the default link type")
                    break

        # Load subsystem mapping from Excel file
        self.subsystem_mapping = self._load_subsystem_mapping()

        # Get metadata for CLM project to identify fields and options
        self.create_meta = self.get_create_meta()
        self.field_ids = self._get_field_ids()

        # Path for storing creation results
        self.results_dir = os.path.join('data', 'clm_results')
        self.results_file = os.path.join(self.results_dir, 'creation_results.json')

        # Ensure the results directory exists
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)

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

    def get_issue_details(self, issue_key):
        """
        Get details of a Jira issue

        Args:
            issue_key (str): Jira issue key

        Returns:
            dict: Issue details or None if error
        """
        if not self.api_token:
            logger.error(f"API token not available for issue {issue_key}")
            return None

        try:
            # Make API request to get issue details
            url = f"{self.jira_url}/rest/api/2/issue/{issue_key}"
            logger.info(f"Fetching issue details for {issue_key} from {url}")

            response = requests.get(
                url,
                headers=self.headers,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Error getting issue details for {issue_key}: Status code {response.status_code}")
                logger.error(f"Response: {response.text[:500]}...")
                return None

            # Parse the response
            issue_data = response.json()
            logger.info(f"Successfully retrieved issue data for {issue_key}")

            # Extract relevant fields
            summary = issue_data.get('fields', {}).get('summary', '')
            description = issue_data.get('fields', {}).get('description', '')
            components = issue_data.get('fields', {}).get('components', [])

            # Get the first component name or empty string if none
            component = components[0].get('name', '') if components else ''
            logger.info(f"Extracted fields from {issue_key}: summary='{summary[:30]}...', component='{component}'")

            return {
                'summary': summary,
                'description': description,
                'component': component
            }
        except Exception as e:
            logger.error(f"Error getting issue details for {issue_key}: {e}", exc_info=True)
            return None

    def get_available_link_types(self):
        """
        Get all available issue link types from Jira

        Returns:
            list: List of link type dictionaries with inward, outward, and name properties
        """
        if not self.api_token:
            logger.error("API token not available, cannot fetch link types")
            return []

        try:
            # Call Jira API to get link types
            url = f"{self.jira_url}/rest/api/2/issueLinkType"
            logger.info(f"Fetching available link types from {url}")

            response = requests.get(
                url,
                headers=self.headers,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Error fetching link types: Status code {response.status_code}")
                logger.error(f"Response: {response.text[:200]}...")
                return []

            # Parse response
            link_types_data = response.json()
            link_types = link_types_data.get('issueLinkTypes', [])

            # Log available link types
            logger.info(f"Found {len(link_types)} available link types:")
            for lt in link_types:
                logger.info(f"Link type: {lt.get('name')} (Inward: {lt.get('inward')}, Outward: {lt.get('outward')})")

            return link_types
        except Exception as e:
            logger.error(f"Error getting link types: {e}", exc_info=True)
            return []

    def create_link(self, source_issue_key, target_issue_key, link_type=None):
        """
        Create a link between two issues

        Args:
            source_issue_key (str): Source issue key
            target_issue_key (str): Target issue key
            link_type (str, optional): Link type name. If None, the default link type will be used.

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.api_token:
            logger.error(
                f"API token not available, cannot create link between {source_issue_key} and {target_issue_key}")
            return False

        try:
            # Use the provided link type or the default
            link_type = link_type or self.default_link_type
            logger.info(f"Attempting to create link with type '{link_type}'")

            # Check if the link type exists in our cached link types
            if self.link_types:
                link_type_exists = any(lt.get('name') == link_type for lt in self.link_types)

                if not link_type_exists:
                    # If requested link type doesn't exist, use default link type
                    logger.warning(
                        f"Link type '{link_type}' not found in available types, using '{self.default_link_type}' instead")
                    link_type = self.default_link_type

            # Create link via API
            url = f"{self.jira_url}/rest/api/2/issueLink"
            logger.info(f"Creating link from {source_issue_key} to {target_issue_key} with type '{link_type}'")

            # Prepare link data
            link_data = {
                "type": {
                    "name": link_type
                },
                "inwardIssue": {
                    "key": target_issue_key
                },
                "outwardIssue": {
                    "key": source_issue_key
                }
            }

            # Make the API request
            response = requests.post(
                url,
                headers=self.headers,
                data=json.dumps(link_data),
                timeout=30
            )

            if response.status_code in [200, 201, 204]:
                logger.info(f"Successfully created link from {source_issue_key} to {target_issue_key}")
                return True
            else:
                logger.error(f"Error creating link: Status code {response.status_code}")
                logger.error(f"Response: {response.text[:500]}...")

                # If the first attempt failed and we used a custom link type, try with the default link type
                if link_type != self.default_link_type:
                    logger.info(f"Trying again with default link type '{self.default_link_type}'")
                    link_data["type"]["name"] = self.default_link_type

                    retry_response = requests.post(
                        url,
                        headers=self.headers,
                        data=json.dumps(link_data),
                        timeout=30
                    )

                    if retry_response.status_code in [200, 201, 204]:
                        logger.info(f"Successfully created link on second attempt")
                        return True
                    else:
                        logger.error(f"Second attempt also failed: Status code {retry_response.status_code}")
                        logger.error(f"Response: {retry_response.text[:500]}...")

                # If there are no cached link types or both attempts failed, try to get the link types again
                if not self.link_types:
                    logger.info("No cached link types available, fetching them now")
                    self.link_types = self.get_available_link_types()

                    if self.link_types:
                        # Try one more time with the first available link type
                        first_link_type = self.link_types[0].get('name')
                        logger.info(f"Trying third attempt with first available link type: '{first_link_type}'")

                        link_data["type"]["name"] = first_link_type
                        third_response = requests.post(
                            url,
                            headers=self.headers,
                            data=json.dumps(link_data),
                            timeout=30
                        )

                        if third_response.status_code in [200, 201, 204]:
                            logger.info(f"Successfully created link on third attempt with '{first_link_type}'")
                            # Update default link type for future usage
                            self.default_link_type = first_link_type
                            return True
                        else:
                            logger.error(f"Third attempt also failed: Status code {third_response.status_code}")

                return False

        except Exception as e:
            logger.error(f"Error creating link: {e}", exc_info=True)
            return False

    def create_clm_error(self, issue_key):
        """
        Create a CLM Error issue for the given Jira issue key

        Args:
            issue_key (str): Jira issue key

        Returns:
            str: CLM Error issue key or None if error
        """
        if not self.api_token:
            logger.error(f"API token not available, cannot create CLM Error for {issue_key}")
            return None

        try:
            logger.info(f"Starting creation of CLM Error for issue {issue_key}")

            # Get issue details
            issue_details = self.get_issue_details(issue_key)
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
                ('Urgency', 'B - High'),  # Keep as is if ID not known
                ('Company', '825'),  # Keep as is
                ('Production/Test', 'DEVELOPMENT'),  # Keep as is if ID not known

                # PM Fields using same approach as Company
                ('customfield_17813', '169086'),  # Investment - NBSS 2025
                ('customfield_17812', '170958'),  # Text field

                # Additional fields from other tabs
                ('customfield_17814', ''),  # Milestone (can be left empty)
                ('customfield_17819', '')  # Requirement/Backlog (can be left empty)
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
                    if field_name == 'Company':
                        # The field expects an array of strings
                        issue_data['fields'][field_id] = ["825"]  # e.g., ["investment"]
                        logger.info(f"Set field '{field_name}' as array with value '['825']'")
                        successful_fields += 1
                    elif field_name == 'customfield_17813':
                        # Investment field - set as an array like Company
                        issue_data['fields'][field_id] = [value]
                        logger.info(f"Set field '{field_name}' as array with value '[{value}]'")
                        successful_fields += 1
                    elif field_name == 'customfield_17812':
                        # Text field - set as an array like Company
                        issue_data['fields'][field_id] = [value]
                        logger.info(f"Set field '{field_name}' as array with value '[{value}]'")
                        successful_fields += 1
                    elif field_name in ['customfield_17814', 'customfield_17819']:
                        # Skip empty dropdown fields - don't set them at all if value is empty
                        if value:
                            issue_data['fields'][field_id] = [value]  # Use array format like Company
                            logger.info(f"Set field '{field_name}' as array with value '[{value}]'")
                            successful_fields += 1
                        else:
                            logger.info(f"Skipping empty field '{field_name}'")
                            # Don't count optional empty fields against successful_fields count
                            required_fields -= 1
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

            # Log the request payload (without sensitive data)
            try:
                logger.info(
                    f"Request payload for CLM Error creation: {json.dumps(issue_data, indent=2, ensure_ascii=False)}")
            except Exception as e:
                logger.warning(f"Could not log request payload: {e}")

            # Make the API request to create the issue
            response = requests.post(
                url,
                headers=self.headers,
                data=json.dumps(issue_data),
                timeout=30
            )

            # Log detailed response information
            logger.info(f"CLM Error creation response status code: {response.status_code}")

            if response.status_code not in [200, 201]:
                logger.error(f"Error creating CLM Error for {issue_key}: Status code {response.status_code}")
                logger.error(f"Response headers: {response.headers}")
                logger.error(f"Response content: {response.text[:500]}...")
                return None

            # Get the created issue key
            try:
                created_issue = response.json()
                clm_error_key = created_issue.get('key', '')
                logger.info(f"Successfully created CLM Error {clm_error_key} for issue {issue_key}")
                # Create a link between the original issue and the CLM Error
                link_success = self.create_link(issue_key, clm_error_key, "links CLM to")
                if link_success:
                    logger.info(
                        f"Successfully linked {issue_key} to {clm_error_key} with 'links CLM to' link type")
                else:
                    logger.warning(f"Failed to create link between {issue_key} and {clm_error_key}")
                return clm_error_key
            except json.JSONDecodeError:
                logger.error(f"Could not parse JSON response: {response.text[:500]}...")
                return None

        except Exception as e:
            logger.error(f"Error creating CLM Error for {issue_key}: {e}", exc_info=True)
            return None

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

    def get_creation_results(self):
        """
        Get all CLM Error creation results from the results file

        Returns:
            list: List of creation result dictionaries
        """
        try:
            # Check if results file exists
            if not os.path.exists(self.results_file):
                logger.info(f"Results file not found: {self.results_file}")
                return []

            # Read results from file
            with open(self.results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)

            logger.info(f"Retrieved {len(results)} creation results from file")
            return results
        except Exception as e:
            logger.error(f"Error getting creation results: {e}", exc_info=True)
            return []

    def save_creation_result(self, source_key, clm_error_key):
        """
        Save a CLM Error creation result to the results file

        Args:
            source_key (str): Source issue key
            clm_error_key (str): CLM Error issue key or None if failed

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create a result object
            result = {
                'source_key': source_key,
                'clm_error_key': clm_error_key,
                'status': 'success' if clm_error_key else 'failed',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # Get existing results
            results = self.get_creation_results()

            # Add new result
            results.append(result)

            # Save results to file
            with open(self.results_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved creation result for {source_key} -> {clm_error_key}")
            return True
        except Exception as e:
            logger.error(f"Error saving creation result: {e}", exc_info=True)
            return False

    def create_clm_errors(self, issue_keys_str):
        """
        Create CLM Error issues for the given comma-separated Jira issue keys
        and save the results to a file for persistence

        Args:
            issue_keys_str (str): Comma-separated Jira issue keys

        Returns:
            dict: Mapping from original issue key to CLM Error issue key
        """
        # Split the input string and remove whitespace
        issue_keys = [key.strip() for key in issue_keys_str.split(',') if key.strip()]

        if not issue_keys:
            logger.warning("No valid issue keys provided")
            return {}

        logger.info(f"Creating CLM Errors for {len(issue_keys)} issues: {issue_keys}")

        # Process each issue key
        results = {}
        for issue_key in issue_keys:
            logger.info(f"Processing issue key: {issue_key}")
            clm_error_key = self.create_clm_error(issue_key)
            results[issue_key] = clm_error_key
            logger.info(f"Result for {issue_key}: {'Success' if clm_error_key else 'Failed'}")

            # Save result to file
            self.save_creation_result(issue_key, clm_error_key)

        logger.info(f"Completed CLM Errors creation. Results: {results}")
        return results

    # Add a new method to the ClmErrorCreator class
    def stop_status_monitor(self):
        """Stop the status transition monitor"""
        if hasattr(self, 'status_transitioner'):
            self.status_transitioner.stop_transition_monitor()
            logger.info("Stopped CLM Error status transition monitor")

    # Add a new method to manually trigger transitions for testing
    def trigger_transitions(self, clm_key):
        """
        Manually trigger status transitions for a CLM Error

        Args:
            clm_key (str): CLM Error issue key

        Returns:
            tuple: (studying_result, received_result) - both booleans
        """
        if not hasattr(self, 'status_transitioner'):
            logger.error("Status transitioner not initialized")
            return False, False

        studying_result = self.status_transitioner._transition_to_studying(clm_key)
        received_result = self.status_transitioner._transition_to_received(clm_key)

        return studying_result, received_result