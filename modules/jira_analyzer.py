import requests
import pandas as pd
import json
import logging
import sys

# Try to import the config with API token
try:
    import config

    if not hasattr(config, 'api_token') or not config.api_token:
        logging.error("API token not found in config file")
        sys.exit(1)
except ImportError:
    logging.error("config.py file not found. Create a config.py file with an api_token variable")
    logging.error("Example: api_token = 'your_token_here'")
    sys.exit(1)

# Import visualization and data processing
from modules.data_processor import process_issues_data, get_status_categories
from modules.visualization import create_visualizations


class JiraAnalyzer:
    def __init__(self, jira_url=None, status_mapping=None):
        """
        Initialize Jira analyzer with token from config.py

        Args:
            jira_url (str): Base URL for your Jira instance
            status_mapping (dict): Optional mapping of statuses to categories ('open' or 'closed')
                                  Example: {'Custom Status': 'open', 'Another Status': 'closed'}
        """
        self.jira_url = jira_url or 'https://jira.nexign.com'
        self.logger = logging.getLogger(__name__)
        self.status_mapping = status_mapping or {}

        # Use token from config
        self.headers = {
            "Authorization": f"Bearer {config.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Check connection but continue even if it fails
        if not self._check_connection():
            self.logger.warning("Connection check failed, but will try to continue.")

    def _check_connection(self):
        """
        Check connection to Jira.
        Returns True if successful, False otherwise.
        """
        try:
            # First check server availability
            self.logger.info("Checking Jira server availability...")

            try:
                session = requests.Session()
                resp = session.get(self.jira_url, timeout=10, allow_redirects=False)
                if resp.status_code >= 300 and resp.status_code < 400:
                    self.logger.error(f"Server redirecting to: {resp.headers.get('Location', 'unknown')}")
                    self.logger.error("VPN connection or NetScaler authentication may be required")
                    return False
            except requests.RequestException as e:
                self.logger.error(f"Failed to connect to server: {e}")
                return False

            self.logger.info("Server available, checking token authentication...")

            # Now check authentication using API v2
            response = requests.get(
                f"{self.jira_url}/rest/api/2/myself",
                headers=self.headers,
                timeout=10
            )

            self.logger.info(f"Response code: {response.status_code}")

            if response.status_code == 200:
                try:
                    user_data = response.json()
                    self.logger.info(f"Authentication successful! User: {user_data.get('displayName', 'unknown')}")
                    return True
                except json.JSONDecodeError as e:
                    self.logger.error(f"Error parsing JSON: {e}")
                    self.logger.error(f"Response content: {response.text[:200]}...")
                    return False
            else:
                self.logger.error(f"Authentication error. Code: {response.status_code}")
                self.logger.error(f"Server response: {response.text[:200]}...")
                return False
        except Exception as e:
            self.logger.error(f"Error checking connection: {e}")
            return False

    def get_issues_by_filter(self, jql_query=None, filter_id=None, max_results=10000):
        """
        Get issues from Jira using a JQL query or filter ID.
        No limit on the number of issues (default 10000 should be sufficient).
        Includes changelog request for transitions analysis.

        Args:
            jql_query (str): JQL query string
            filter_id (str/int): Jira filter ID to use instead of JQL
            max_results (int): Maximum number of results to return

        Returns:
            list: List of issue dictionaries
        """
        # Use API v2
        search_url = f"{self.jira_url}/rest/api/2/search"

        # Use either jql_query or filter_id
        if filter_id and not jql_query:
            query_string = f'filter={filter_id}'
        else:
            query_string = jql_query

        self.logger.info(f"Using query: {query_string}")

        start_at = 0
        all_issues = []

        while True:
            query = {
                'jql': query_string,
                'maxResults': 100,  # Get 100 issues per request (API limit)
                'startAt': start_at,
                'fields': [
                    'project',
                    'summary',
                    'issuetype',
                    'timeoriginalestimate',
                    'timespent',
                    'status',
                    'worklog',
                    'comment',
                    'attachment',
                    'created',  # Request creation date
                    'components'  # Request components for CLM/EST analysis
                ],
                'expand': ['changelog']  # Request changelog for transitions analysis
            }

            try:
                response = requests.post(
                    search_url,
                    headers=self.headers,
                    data=json.dumps(query),
                    timeout=30
                )

                # Print request info for debugging
                self.logger.info(f"Request to {search_url}, response code: {response.status_code}")

                # Check for errors
                if response.status_code != 200:
                    self.logger.error(f"Error getting data: {response.status_code}")
                    self.logger.error(f"Server response: {response.text[:200]}...")
                    break

                # Check for valid JSON
                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    self.logger.error(f"Error parsing JSON: {e}")
                    self.logger.error(f"Response content: {response.text[:200]}...")
                    break

                issues = data.get('issues', [])

                if not issues:
                    self.logger.info("No more issues found.")
                    break

                all_issues.extend(issues)
                start_at += len(issues)

                # Progress indicator
                self.logger.info(f"Retrieved {len(all_issues)}/{data.get('total', 0)} issues...")

                # Exit if all issues received or max_results reached
                if start_at >= data.get('total', 0):
                    self.logger.info("Retrieved all issues matching the query.")
                    break

            except Exception as e:
                self.logger.error(f"Exception occurred: {str(e)}")
                self.logger.error("Traceback:", exc_info=True)
                break

        return all_issues

    def get_linked_issues(self, issues, link_type=None, max_depth=1):
        """
        Get issues linked to the provided issues.

        Args:
            issues (list): List of issue dictionaries or issue keys
            link_type (str): Optional link type to filter by (e.g., "relates to")
            max_depth (int): Maximum depth of link traversal

        Returns:
            list: List of linked issue dictionaries
        """
        if not issues:
            return []

        # Extract issue keys if issues are dictionaries
        issue_keys = []
        for issue in issues:
            if isinstance(issue, dict):
                key = issue.get('key')
                if key:
                    issue_keys.append(key)
            elif isinstance(issue, str):
                issue_keys.append(issue)

        if not issue_keys:
            return []

        # Split issue keys into much smaller chunks to avoid query length limitations
        # Jira has a smaller limit than expected, use 10 keys per chunk
        chunk_size = 10
        all_linked_issues = []

        for i in range(0, len(issue_keys), chunk_size):
            chunk = issue_keys[i:i + chunk_size]

            # Create the JQL query with proper syntax - important to use OR for multiple issues
            if link_type:
                jql_parts = []
                for key in chunk:
                    jql_parts.append(f'issue in linkedIssues("{key}", "{link_type}")')

                jql = " OR ".join(jql_parts)
            else:
                jql_parts = []
                for key in chunk:
                    jql_parts.append(f'issue in linkedIssues("{key}")')

                jql = " OR ".join(jql_parts)

            # Get the linked issues
            self.logger.info(f"Fetching linked issues with query: {jql}")
            linked_issues = self.get_issues_by_filter(jql_query=jql)
            all_linked_issues.extend(linked_issues)

            self.logger.info(
                f"Retrieved {len(linked_issues)} linked issues for chunk {i // chunk_size + 1}/{(len(issue_keys) + chunk_size - 1) // chunk_size}")

        return all_linked_issues

    def get_clm_related_issues(self, clm_issues):
        """
        Get all issues related to CLM issues following the specific logic.

        Args:
            clm_issues (list): List of CLM issue dictionaries

        Returns:
            tuple: (est_issues, improvement_issues, implementation_issues)
        """
        if not clm_issues:
            return [], [], []

        # Extract CLM issue keys
        clm_keys = [issue.get('key') for issue in clm_issues if issue.get('key')]

        # Get EST issues related to CLM with "relates to" link
        self.logger.info(f"Fetching EST issues related to {len(clm_keys)} CLM issues...")
        est_issues = self.get_linked_issues(clm_keys, link_type="relates to")

        # Filter to include only EST project issues
        est_issues = [issue for issue in est_issues if
                      issue.get('fields', {}).get('project', {}).get('key') == 'EST']

        # Get Improvement issues linked to CLM with "links CLM to" link
        self.logger.info(f"Fetching Improvement issues linked to CLM...")
        improvement_issues = self.get_linked_issues(clm_keys, link_type="links CLM to")

        # Filter for type "Improvement from CLM"
        improvement_issues = [issue for issue in improvement_issues if
                              issue.get('fields', {}).get('issuetype', {}).get('name') == 'Improvement from CLM']

        # Get implementation issues linked to Improvements with "is realized in" link
        implementation_keys = []
        implementation_issues = []

        improvement_keys = [issue.get('key') for issue in improvement_issues if issue.get('key')]
        if improvement_keys:
            self.logger.info(f"Fetching implementation issues linked to {len(improvement_keys)} Improvement issues...")
            implementation_issues = self.get_linked_issues(improvement_keys, link_type="is realized in")
            implementation_keys = [issue.get('key') for issue in implementation_issues if issue.get('key')]

        # Get subtasks using direct parent query instead of subtasksOf
        subtasks = []
        if implementation_keys:
            for i in range(0, len(implementation_keys), 10):
                chunk = implementation_keys[i:i + 10]
                parents_clause = " OR ".join([f'parent = "{key}"' for key in chunk])
                subtasks_query = parents_clause

                self.logger.info(f"Fetching subtasks with query: {subtasks_query}")
                try:
                    chunk_subtasks = self.get_issues_by_filter(jql_query=subtasks_query)
                    subtasks.extend(chunk_subtasks)
                except Exception as e:
                    self.logger.error(f"Error fetching subtasks: {e}")

        # Get epic issues using Epic Link field instead of issuesInEpics
        epic_issues = []
        if implementation_keys:
            for i in range(0, len(implementation_keys), 10):
                chunk = implementation_keys[i:i + 10]
                epics_clause = " OR ".join([f'"Epic Link" = "{key}"' for key in chunk])
                epics_query = epics_clause

                self.logger.info(f"Fetching epic issues with query: {epics_query}")
                try:
                    chunk_epics = self.get_issues_by_filter(jql_query=epics_query)
                    epic_issues.extend(chunk_epics)
                except Exception as e:
                    self.logger.error(f"Error fetching epic issues: {e}")

        # Combine all implementation-related issues
        implementation_issues.extend(subtasks)
        implementation_issues.extend(epic_issues)

        self.logger.info(
            f"Found {len(est_issues)} EST issues, {len(improvement_issues)} Improvement issues, and {len(implementation_issues)} implementation issues")
        return est_issues, improvement_issues, implementation_issues

    def get_subtasks_by_rest_api(self, issue_keys):
        """
        Get subtasks for issues using direct REST API calls instead of JQL

        Args:
            issue_keys (list): List of parent issue keys

        Returns:
            list: List of subtask issue dictionaries
        """
        all_subtasks = []

        for key in issue_keys:
            try:
                # Make a direct API call to get the issue with subtasks expanded
                issue_url = f"{self.jira_url}/rest/api/2/issue/{key}?expand=subtasks"

                response = requests.get(
                    issue_url,
                    headers=self.headers,
                    timeout=30
                )

                if response.status_code == 200:
                    issue_data = response.json()
                    # Extract subtask keys
                    subtask_keys = [subtask.get('key') for subtask in issue_data.get('subtasks', [])]

                    if subtask_keys:
                        self.logger.info(f"Found {len(subtask_keys)} subtasks for issue {key}")

                        # Get full details for each subtask
                        for i in range(0, len(subtask_keys), 10):
                            subtask_chunk = subtask_keys[i:i + 10]
                            subtask_jql = f"key in ({','.join(subtask_chunk)})"
                            chunk_subtasks = self.get_issues_by_filter(jql_query=subtask_jql)
                            all_subtasks.extend(chunk_subtasks)
                else:
                    self.logger.error(f"Error getting subtasks for issue {key}: {response.status_code}")
                    self.logger.error(f"Response: {response.text[:200]}...")

            except Exception as e:
                self.logger.error(f"Exception getting subtasks for issue {key}: {e}")

        return all_subtasks

    # Delegate these methods to the imported modules to maintain backward compatibility
    def process_issues_data(self, issues):
        """Process issues data into a structured DataFrame"""
        return process_issues_data(issues)

    def get_status_categories(self, df):
        """Get status categories from the DataFrame"""
        return get_status_categories(df)

    def create_visualizations(self, df, output_dir='jira_charts'):
        """Create visualizations based on processed data"""
        return create_visualizations(df, output_dir, self.logger)