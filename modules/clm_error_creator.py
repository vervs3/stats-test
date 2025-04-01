import os
import json
import logging
import pandas as pd
import requests
from io import BytesIO

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

        # Use token from config
        try:
            import config
            if hasattr(config, 'api_token') and config.api_token:
                self.headers = {
                    "Authorization": f"Bearer {config.api_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
                self.api_token = config.api_token
                logger.info("API token loaded from config")
            else:
                logger.error("API token not found in config file")
                self.api_token = None
                self.headers = {}
        except ImportError:
            logger.error("config.py file not found. Create a config.py file with an api_token variable")
            self.api_token = None
            self.headers = {}

        # Load subsystem mapping from Excel file
        self.subsystem_mapping = self._load_subsystem_mapping()

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

            # Create mapping from component to subsystem
            # We'll match based on the first 3 characters
            mapping = {}

            logger.info(f"Found {len(subsystems)} subsystems for DIGITAL_BSS")

            return subsystems
        except Exception as e:
            logger.error(f"Error loading subsystem mapping: {e}", exc_info=True)
            return []

    def _match_component_to_subsystem(self, component):
        """
        Match component to subsystem based on first 3 characters

        Args:
            component (str): Component name

        Returns:
            str: Matched subsystem or default value
        """
        if not component or not self.subsystem_mapping:
            return "NBSS_CORE"  # Default subsystem

        # Convert component to lowercase for case-insensitive matching
        component_lower = component.lower()

        # Try to find a match based on first 3 characters
        for subsystem in self.subsystem_mapping:
            if subsystem and len(subsystem) >= 3 and len(component) >= 3:
                if subsystem[:3].lower() in component_lower or component_lower[:3] in subsystem.lower():
                    logger.info(f"Matched component '{component}' to subsystem '{subsystem}'")
                    return subsystem

        # If no match found, log and return default
        logger.warning(f"No subsystem match found for component '{component}', using default")
        return "NBSS_CORE"  # Default subsystem

    def get_issue_details(self, issue_key):
        """
        Get details of a Jira issue

        Args:
            issue_key (str): Jira issue key

        Returns:
            dict: Issue details or None if error
        """
        if not self.api_token:
            logger.error("API token not available")
            return None

        try:
            # Make API request to get issue details
            url = f"{self.jira_url}/rest/api/2/issue/{issue_key}"
            response = requests.get(
                url,
                headers=self.headers,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Error getting issue details: {response.status_code}")
                logger.error(f"Response: {response.text[:200]}...")
                return None

            # Parse the response
            issue_data = response.json()

            # Extract relevant fields
            summary = issue_data.get('fields', {}).get('summary', '')
            description = issue_data.get('fields', {}).get('description', '')
            components = issue_data.get('fields', {}).get('components', [])

            # Get the first component name or empty string if none
            component = components[0].get('name', '') if components else ''

            return {
                'summary': summary,
                'description': description,
                'component': component
            }
        except Exception as e:
            logger.error(f"Error getting issue details: {e}", exc_info=True)
            return None

    def create_clm_error(self, issue_key):
        """
        Create a CLM Error issue for the given Jira issue key

        Args:
            issue_key (str): Jira issue key

        Returns:
            str: CLM Error issue key or None if error
        """
        if not self.api_token:
            logger.error("API token not available")
            return None

        try:
            # Get issue details
            issue_details = self.get_issue_details(issue_key)
            if not issue_details:
                logger.error(f"Could not get details for issue {issue_key}")
                return None

            # Match component to subsystem
            subsystem = self._match_component_to_subsystem(issue_details.get('component', ''))

            # Create CLM Error issue
            url = f"{self.jira_url}/rest/api/2/issue/"

            # Prepare issue data
            issue_data = {
                "fields": {
                    "project": {
                        "key": "CLM"
                    },
                    "issuetype": {
                        "name": "Error"
                    },
                    "summary": issue_details.get('summary', ''),
                    "description": issue_details.get('description', ''),
                    "customfield_10509": {  # Product Group
                        "value": "DIGITAL_BSS"
                    },
                    "customfield_14900": {  # Subsystem
                        "value": subsystem
                    },
                    "customfield_13004": {  # Urgency
                        "value": "B - High"
                    },
                    "customfield_16300": {  # Company
                        "value": "investment"
                    },
                    "customfield_17200": {  # Production/Test
                        "value": "DEVELOPMENT"
                    }
                }
            }

            # Make the API request to create the issue
            response = requests.post(
                url,
                headers=self.headers,
                data=json.dumps(issue_data),
                timeout=30
            )

            if response.status_code not in [200, 201]:
                logger.error(f"Error creating CLM Error: {response.status_code}")
                logger.error(f"Response: {response.text[:200]}...")
                return None

            # Get the created issue key
            created_issue = response.json()
            clm_error_key = created_issue.get('key', '')

            logger.info(f"Created CLM Error {clm_error_key} for issue {issue_key}")

            return clm_error_key
        except Exception as e:
            logger.error(f"Error creating CLM Error: {e}", exc_info=True)
            return None

    def create_clm_errors(self, issue_keys_str):
        """
        Create CLM Error issues for the given comma-separated Jira issue keys

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
            clm_error_key = self.create_clm_error(issue_key)
            results[issue_key] = clm_error_key

        return results