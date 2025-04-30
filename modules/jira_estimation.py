import os
import logging
import pandas as pd
from datetime import datetime
import requests
import json
import re
from collections import defaultdict

# Get logger
logger = logging.getLogger(__name__)

# Constants
CUTOFF_DATE = "2025-01-10T00:00:00.000+0000"
FIELDS_TO_FETCH = "summary,issuetype,created,timeoriginalestimate,subtasks,sprint"
HISTORY_EXPAND = "changelog"
ISSUE_TYPE_NEW_FEATURE = "New Feature"
TARGET_SPRINT_IDS = [14638, 14639, 14640, 14641]  # NBSS 25Q1, 25Q2, 25Q3, 25Q4


class JiraEstimationAnalyzer:
    """
    Class to analyze Jira estimation data, comparing estimates from before Jan 10, 2025
    with current estimates.
    """

    def __init__(self, jira_url=None, api_token=None):
        """Initialize the analyzer with Jira URL and API token"""
        # Try to import config if token not provided
        if api_token is None:
            try:
                import config
                if hasattr(config, 'api_token'):
                    api_token = config.api_token
                    logger.info("Using API token from config.py")
            except ImportError:
                logger.error("No API token available and couldn't import from config.py")

        if jira_url is None:
            try:
                import config
                if hasattr(config, 'jira_url'):
                    jira_url = config.jira_url
                    logger.info(f"Using Jira URL from config.py: {jira_url}")
            except ImportError:
                logger.warning("Could not import config.py for Jira URL")

        # Default Jira URL if not provided
        if not jira_url:
            jira_url = "https://jira.nexign.com"
            logger.info(f"Using default Jira URL: {jira_url}")

        self.jira_url = jira_url
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def check_connection(self):
        """Check connection to Jira and API token validity"""
        try:
            logger.info("Checking Jira server availability...")
            try:
                session = requests.Session()
                resp = session.get(self.jira_url, timeout=10, allow_redirects=False)
                if resp.status_code >= 300 and resp.status_code < 400:
                    logger.error(f"Server redirecting to: {resp.headers.get('Location', 'unknown')}")
                    logger.error("VPN connection or NetScaler authentication may be required")
                    return False
            except requests.RequestException as e:
                logger.error(f"Failed to connect to server: {e}")
                return False

            logger.info("Server available, checking token authentication...")
            response = requests.get(
                f"{self.jira_url}/rest/api/2/myself",
                headers=self.headers,
                timeout=10
            )
            logger.info(f"Response code: {response.status_code}")

            if response.status_code == 200:
                try:
                    user_data = response.json()
                    logger.info(f"Authentication successful! User: {user_data.get('displayName', 'unknown')}")
                    return True
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON: {e}")
                    return False
            else:
                logger.error(f"Authentication error. Code: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error checking connection: {e}")
            return False

    def get_filter_jql(self, filter_id):
        """Get JQL query from a Jira filter ID"""
        filter_url = f"{self.jira_url}/rest/api/2/filter/{filter_id}"
        logger.info(f"Getting filter JQL from: {filter_url}")
        try:
            response = requests.get(filter_url, headers=self.headers)
            response.raise_for_status()
            jql = response.json().get('jql', '')
            logger.info(f"Retrieved JQL: {jql[:50]}...")
            return jql
        except Exception as e:
            logger.error(f"Error getting filter JQL: {e}")
            return None

    def search_issues(self, jql):
        """Search for issues using JQL query"""
        search_url = f"{self.jira_url}/rest/api/2/search"
        issues = []
        start_at = 0
        max_results = 50

        try:
            while True:
                params = {
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": max_results,
                    "fields": FIELDS_TO_FETCH,
                    "expand": HISTORY_EXPAND
                }

                logger.info(f"Searching issues: startAt={start_at}, maxResults={max_results}")
                response = requests.get(search_url, headers=self.headers, params=params)
                response.raise_for_status()

                data = response.json()
                issues.extend(data["issues"])
                logger.info(f"Retrieved {len(data['issues'])} issues, total: {len(issues)}/{data['total']}")

                if start_at + max_results >= data["total"]:
                    break

                start_at += max_results

            return issues
        except Exception as e:
            logger.error(f"Error searching issues: {e}")
            return []

    def get_subtasks(self, issue_key):
        """Get subtasks for a specific issue"""
        issue_url = f"{self.jira_url}/rest/api/2/issue/{issue_key}"
        params = {
            "fields": f"subtasks,{FIELDS_TO_FETCH}",
            "expand": HISTORY_EXPAND
        }

        try:
            logger.info(f"Getting subtasks for issue: {issue_key}")
            response = requests.get(issue_url, headers=self.headers, params=params)
            response.raise_for_status()

            data = response.json()
            subtask_ids = [subtask["id"] for subtask in data["fields"].get("subtasks", [])]
            logger.info(f"Found {len(subtask_ids)} subtasks for {issue_key}")

            subtasks = []
            if subtask_ids:
                for subtask_id in subtask_ids:
                    subtask_url = f"{self.jira_url}/rest/api/2/issue/{subtask_id}"
                    logger.debug(f"Fetching subtask data for ID: {subtask_id}")
                    subtask_response = requests.get(subtask_url, headers=self.headers,
                                                    params={"expand": HISTORY_EXPAND})
                    subtask_response.raise_for_status()
                    subtasks.append(subtask_response.json())

            return subtasks
        except Exception as e:
            logger.error(f"Error getting subtasks for {issue_key}: {e}")
            return []

    def convert_seconds_to_days(self, seconds):
        """Convert seconds to days (8 hours per day)"""
        if seconds is None:
            return 0
        hours_per_day = 8
        return round(seconds / 3600 / hours_per_day, 2)

    def get_original_estimate_at_date(self, issue, cutoff_date):
        """Get the original estimate of an issue at a specific date from history"""
        if not issue.get("changelog") or not issue["changelog"].get("histories"):
            created_date = issue["fields"]["created"]
            current_estimate = issue["fields"].get("timeoriginalestimate")

            if created_date <= cutoff_date:
                return current_estimate
            else:
                return 0

        if issue["fields"]["created"] > cutoff_date:
            return 0

        histories = sorted(issue["changelog"]["histories"], key=lambda x: x["created"])
        estimate = issue["fields"].get("timeoriginalestimate", 0)

        for history in reversed(histories):
            history_date = history["created"]

            if history_date <= cutoff_date:
                break

            for item in history["items"]:
                if item["field"] == "timeoriginalestimate":
                    from_value = item.get("from")
                    if from_value is not None and from_value != "":
                        try:
                            estimate = int(from_value)
                        except ValueError:
                            logger.warning(f"Invalid timeoriginalestimate value: {from_value}")

        return estimate

    def get_sprint_info_at_date(self, issue, cutoff_date):
        """Extract sprint information from an issue that was valid at a specific date"""
        sprint_data = []
        sprint_ids_found = set()

        # Mapping of sprint names to IDs
        sprint_name_to_id = {
            "NBSS 25Q1": 14638,
            "NBSS 25Q2": 14639,
            "NBSS 25Q3": 14640,
            "NBSS 25Q4": 14641
        }

        current_sprints = self.get_current_sprint_info(issue)

        if issue["fields"]["created"] > cutoff_date:
            logger.debug(f"Issue {issue['key']} was created after cutoff date, no sprints to consider")
            return []

        if not issue.get("changelog") or not issue["changelog"].get("histories"):
            logger.debug(f"Issue {issue['key']} has no changelog, using current sprints")
            return current_sprints

        histories = sorted(issue["changelog"]["histories"], key=lambda x: x["created"])
        histories_before_cutoff = [h for h in histories if h["created"] <= cutoff_date]

        if not histories_before_cutoff and issue["fields"]["created"] <= cutoff_date:
            logger.debug(f"Issue {issue['key']} has no changelog before cutoff but was created before")
            return current_sprints

        for history in histories_before_cutoff:
            for item in history.get("items", []):
                if item.get("field") == "Sprint":
                    sprint_str = item.get("toString", "")
                    logger.debug(f"Found sprint change in history: '{sprint_str}'")

                    if sprint_str:
                        sprint_data = []
                        sprint_ids_found = set()

                        # Find sprint IDs in format [ XXXX ]
                        sprint_ids = re.findall(r'\[\s*(\d+)\s*\]', sprint_str)

                        # Find sprint names in format "NBSS XXqX"
                        sprint_names = re.findall(r'(NBSS\s+\d+Q[1-4])', sprint_str)
                        if not sprint_names:
                            sprint_names = [name.strip() for name in re.split(r'[,\s]+', sprint_str) if name.strip()]

                        logger.debug(f"Extracted sprint IDs: {sprint_ids}, names: {sprint_names}")

                        # Process combined format "NAME [ ID ]"
                        sprint_blocks = re.findall(r'([^\[\]]+)\[\s*(\d+)\s*\]', sprint_str)

                        if sprint_blocks:
                            for name, sprint_id in sprint_blocks:
                                try:
                                    sprint_id_int = int(sprint_id)
                                    if sprint_id_int not in sprint_ids_found:
                                        sprint_ids_found.add(sprint_id_int)
                                        sprint_data.append({
                                            "id": sprint_id_int,
                                            "name": name.strip(),
                                            "state": "unknown"
                                        })
                                except ValueError:
                                    logger.warning(f"Error parsing sprint ID '{sprint_id}'")
                        elif sprint_ids:
                            for sprint_id in sprint_ids:
                                try:
                                    sprint_id_int = int(sprint_id)
                                    if sprint_id_int not in sprint_ids_found:
                                        sprint_ids_found.add(sprint_id_int)
                                        sprint_data.append({
                                            "id": sprint_id_int,
                                            "name": f"Sprint {sprint_id}",
                                            "state": "unknown"
                                        })
                                except ValueError:
                                    logger.warning(f"Error parsing sprint ID '{sprint_id}'")
                        elif sprint_names:
                            for name in sprint_names:
                                name_clean = name.strip()
                                if name_clean in sprint_name_to_id:
                                    sprint_id_int = sprint_name_to_id[name_clean]
                                    if sprint_id_int not in sprint_ids_found:
                                        sprint_ids_found.add(sprint_id_int)
                                        sprint_data.append({
                                            "id": sprint_id_int,
                                            "name": name_clean,
                                            "state": "unknown"
                                        })
                                else:
                                    quarter_match = re.search(r'NBSS\s+(\d+)Q([1-4])', name_clean)
                                    if quarter_match:
                                        year = quarter_match.group(1)
                                        quarter = quarter_match.group(2)

                                        if f"NBSS {year}Q{quarter}" in sprint_name_to_id:
                                            sprint_id_int = sprint_name_to_id[f"NBSS {year}Q{quarter}"]

                                            if sprint_id_int not in sprint_ids_found:
                                                sprint_ids_found.add(sprint_id_int)
                                                sprint_data.append({
                                                    "id": sprint_id_int,
                                                    "name": name_clean,
                                                    "state": "unknown"
                                                })

        if not sprint_data:
            logger.debug(f"No sprint changes found in history for {issue['key']}, using current sprints")
            sprint_data = current_sprints

        return sprint_data

    def get_current_sprint_info(self, issue):
        """Get current sprint information from an issue"""
        sprint_data = []
        sprint_ids_found = set()

        if "sprint" in issue["fields"]:
            sprints = issue["fields"]["sprint"]
            if sprints:
                if isinstance(sprints, list):
                    for sprint in sprints:
                        sprint_id = sprint.get("id")
                        if sprint_id and sprint_id not in sprint_ids_found:
                            sprint_ids_found.add(sprint_id)
                            sprint_data.append({
                                "id": sprint_id,
                                "name": sprint.get("name", f"Sprint {sprint_id}"),
                                "state": sprint.get("state", "unknown"),
                            })
                else:
                    sprint_id = sprints.get("id")
                    if sprint_id and sprint_id not in sprint_ids_found:
                        sprint_ids_found.add(sprint_id)
                        sprint_data.append({
                            "id": sprint_id,
                            "name": sprints.get("name", f"Sprint {sprint_id}"),
                            "state": sprints.get("state", "unknown"),
                        })

        for field_name, field_value in issue["fields"].items():
            if field_name.startswith("customfield_") and field_value is not None:
                if isinstance(field_value, list):
                    for item in field_value:
                        if isinstance(item, str) and "sprint" in item.lower():
                            try:
                                sprint_id_match = re.search(r'id=(\d+)', item)
                                if sprint_id_match:
                                    sprint_id = int(sprint_id_match.group(1))
                                    if sprint_id not in sprint_ids_found:
                                        sprint_ids_found.add(sprint_id)

                                        sprint_name_match = re.search(r'name=([^,]+)', item)
                                        sprint_state_match = re.search(r'state=([^,]+)', item)

                                        sprint_data.append({
                                            "id": sprint_id,
                                            "name": sprint_name_match.group(
                                                1) if sprint_name_match else f"Sprint {sprint_id}",
                                            "state": sprint_state_match.group(1) if sprint_state_match else "unknown",
                                        })
                            except Exception as e:
                                logger.warning(f"Error parsing sprint string '{item}': {e}")

        return sprint_data

    def process_issues(self, issues, cutoff_date, sprint_filter=True, all_tasks=True):
        """Process all issues and extract required data"""
        results = []
        total_processed = 0
        total_included = 0
        total_metrics = {
            "total_issues": 0,
            "total_historical": 0,
            "total_current": 0,
            "difference": 0
        }

        issue_type_metrics = defaultdict(lambda: {"count": 0, "historical": 0, "current": 0, "difference": 0})

        for issue in issues:
            issue_key = issue["key"]
            issue_type = issue["fields"]["issuetype"]["name"]
            total_processed += 1

            if not all_tasks and issue_type != ISSUE_TYPE_NEW_FEATURE:
                logger.info(f"Skipping {issue_key} as it is not a New Feature task")
                continue

            if sprint_filter:
                sprints = self.get_sprint_info_at_date(issue, cutoff_date)
                sprint_ids = [sprint.get("id") for sprint in sprints]

                logger.info(f"Found sprint IDs for {issue_key} at cutoff date: {sprint_ids}")

                if not any(sprint_id in TARGET_SPRINT_IDS for sprint_id in sprint_ids):
                    logger.info(f"Skipping {issue_key} as it does not belong to target sprints.")
                    continue
                else:
                    logger.info(f"Including {issue_key} as it belongs to target sprints: {sprint_ids}")
            else:
                sprints = self.get_current_sprint_info(issue)

            total_included += 1
            logger.info(f"Processing {issue_key}: {issue['fields']['summary']} (Type: {issue_type})")

            issue_current_estimate = issue["fields"].get("timeoriginalestimate", 0) or 0
            issue_historical_estimate = self.get_original_estimate_at_date(issue, cutoff_date) or 0

            subtasks = self.get_subtasks(issue_key)

            current_subtask_estimates = 0
            historical_subtask_estimates = 0
            subtask_data = []

            for subtask in subtasks:
                subtask_key = subtask["key"]
                subtask_created = subtask["fields"]["created"]
                subtask_current_estimate = subtask["fields"].get("timeoriginalestimate", 0) or 0

                subtask_historical_estimate = self.get_original_estimate_at_date(subtask, cutoff_date)
                if subtask_historical_estimate is None:
                    subtask_historical_estimate = 0

                if subtask_created <= cutoff_date:
                    historical_subtask_estimates += subtask_historical_estimate

                current_subtask_estimates += subtask_current_estimate

                if sprint_filter:
                    subtask_sprints = self.get_sprint_info_at_date(subtask, cutoff_date)
                else:
                    subtask_sprints = self.get_current_sprint_info(subtask)

                subtask_sprint_names = [sprint.get("name") for sprint in subtask_sprints]

                subtask_historical_estimate_days = self.convert_seconds_to_days(subtask_historical_estimate)
                subtask_current_estimate_days = self.convert_seconds_to_days(subtask_current_estimate)

                # Calculate difference and status
                subtask_difference = subtask_current_estimate_days - subtask_historical_estimate_days
                status = "unchanged"
                if subtask_difference > 0:
                    status = "increased"
                elif subtask_difference < 0:
                    status = "decreased"

                subtask_data.append({
                    "issue_key": subtask_key,
                    "summary": subtask["fields"]["summary"],
                    "issue_type": subtask["fields"]["issuetype"]["name"],
                    "created": subtask_created,
                    "historical_estimate_seconds": subtask_historical_estimate,
                    "historical_estimate_days": subtask_historical_estimate_days,
                    "current_estimate_seconds": subtask_current_estimate,
                    "current_estimate_days": subtask_current_estimate_days,
                    "parent_key": issue_key,
                    "level": 1,  # Subtasks are level 1, parents are level 0
                    "sprints": subtask_sprint_names,
                    "difference": subtask_difference,
                    "status": status
                })

            if issue_type == ISSUE_TYPE_NEW_FEATURE:
                final_current_estimate = current_subtask_estimates
                final_historical_estimate = historical_subtask_estimates
            else:
                final_current_estimate = issue_current_estimate
                final_historical_estimate = issue_historical_estimate

            issue_historical_estimate_days = self.convert_seconds_to_days(final_historical_estimate)
            issue_current_estimate_days = self.convert_seconds_to_days(final_current_estimate)

            # Calculate difference and status for the parent issue
            issue_difference = issue_current_estimate_days - issue_historical_estimate_days
            status = "unchanged"
            if issue_difference > 0:
                status = "increased"
            elif issue_difference < 0:
                status = "decreased"

            issue_sprint_names = [sprint.get("name") for sprint in sprints]

            results.append({
                "issue_key": issue_key,
                "summary": issue["fields"]["summary"],
                "issue_type": issue_type,
                "created": issue["fields"]["created"],
                "historical_estimate_seconds": final_historical_estimate,
                "historical_estimate_days": issue_historical_estimate_days,
                "current_estimate_seconds": final_current_estimate,
                "current_estimate_days": issue_current_estimate_days,
                "parent_key": None,
                "level": 0,  # Parent issues are level 0
                "sprints": issue_sprint_names,
                "difference": issue_difference,
                "status": status
            })

            # Update metrics
            issue_type_metrics[issue_type]["count"] += 1
            issue_type_metrics[issue_type]["historical"] += issue_historical_estimate_days
            issue_type_metrics[issue_type]["current"] += issue_current_estimate_days
            issue_type_metrics[issue_type]["difference"] += issue_difference

            total_metrics["total_issues"] += 1
            total_metrics["total_historical"] += issue_historical_estimate_days
            total_metrics["total_current"] += issue_current_estimate_days
            total_metrics["difference"] += issue_difference

            results.extend(subtask_data)

        logger.info(f"Processed {total_processed} issues, included {total_included} in results")

        return {
            "results": results,
            "total_metrics": total_metrics,
            "issue_type_metrics": dict(issue_type_metrics)
        }

    def run_analysis(self, filter_id, sprint_filter=False, all_tasks=False):
        """Run the full Jira estimation analysis"""
        if not self.check_connection():
            logger.error("Failed to connect to Jira")
            return None

        jql = self.get_filter_jql(filter_id)
        if not jql:
            logger.error(f"Failed to get JQL from filter ID {filter_id}")
            return None

        issues = self.search_issues(jql)
        if not issues:
            logger.error("No issues found")
            return None

        results = self.process_issues(issues, CUTOFF_DATE, sprint_filter=sprint_filter, all_tasks=all_tasks)
        return results


def collect_estimation_data(filter_id="114924", sprint_filter=True, all_tasks=True):
    """
    Collect Jira estimation data and return the results

    Args:
        filter_id (str): Jira filter ID
        sprint_filter (bool): Filter New Feature tasks by target sprints
        all_tasks (bool): Process all tasks, not just New Feature tasks

    Returns:
        dict: Analysis results or None if error
    """
    try:
        logger.info(
            f"Starting Jira estimation data collection with filter_id={filter_id}, sprint_filter={sprint_filter}, all_tasks={all_tasks}")
        analyzer = JiraEstimationAnalyzer()
        results = analyzer.run_analysis(filter_id, sprint_filter=sprint_filter, all_tasks=all_tasks)

        if results:
            logger.info(f"Successfully collected estimation data: {len(results['results'])} issues processed")

            # Save results to a file for persistence - передаем параметры анализа
            save_estimation_results(results, sprint_filter=sprint_filter, all_tasks=all_tasks)

            return results
        else:
            logger.error("Failed to collect estimation data")
            return None
    except Exception as e:
        logger.error(f"Error collecting estimation data: {e}", exc_info=True)
        return None


def save_estimation_results(results, sprint_filter=False, all_tasks=False):
    """Save estimation results to a file"""
    try:
        # Create directory if it doesn't exist
        data_dir = os.path.join('jira_charts', 'estimation_data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        # Generate timestamp for the file
        timestamp = datetime.now().strftime("%Y%m%d")

        # Create a unique filename based on parameters
        filename_parts = ['estimation_results']
        if sprint_filter:
            filename_parts.append('sprint_filtered')
        if all_tasks:
            filename_parts.append('all_tasks')

        filename = f"{timestamp}_{'_'.join(filename_parts)}.json"
        file_path = os.path.join(data_dir, filename)

        # Convert results to serializable format
        serializable_results = {
            "timestamp": timestamp,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_metrics": results["total_metrics"],
            "issue_type_metrics": results["issue_type_metrics"],
            "results": results["results"],
            "parameters": {
                "sprint_filter": sprint_filter,
                "all_tasks": all_tasks
            }
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved estimation results to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving estimation results: {e}", exc_info=True)
        return False


def get_latest_estimation_results(sprint_filter=None, all_tasks=None):
    """
    Get the latest saved estimation results

    Args:
        sprint_filter (bool or None): If True, get only sprint filtered results.
                                    If False, get only non-filtered results.
                                    If None, get latest results regardless of filter.
        all_tasks (bool or None): Similar to sprint_filter, filter by all_tasks parameter.

    Returns:
        dict: Latest estimation results or None if not found
    """
    try:
        data_dir = os.path.join('jira_charts', 'estimation_data')
        if not os.path.exists(data_dir):
            logger.warning(f"Estimation data directory does not exist: {data_dir}")
            return None

        # Find all result files
        files = [f for f in os.listdir(data_dir) if f.startswith('20') and f.endswith('.json')]
        if not files:
            logger.warning("No estimation result files found")
            return None

        # Filter files based on parameters if specified
        filtered_files = []
        for file in files:
            # Check if file matches the requested filter parameters
            matches_sprint_filter = (sprint_filter is None or
                                     (sprint_filter and 'sprint_filtered' in file) or
                                     (not sprint_filter and 'sprint_filtered' not in file))

            matches_all_tasks = (all_tasks is None or
                                 (all_tasks and 'all_tasks' in file) or
                                 (not all_tasks and 'all_tasks' not in file))

            if matches_sprint_filter and matches_all_tasks:
                filtered_files.append(file)

        if not filtered_files:
            logger.warning(
                f"No matching estimation result files found for sprint_filter={sprint_filter}, all_tasks={all_tasks}")
            return None

        # Sort by filename (which includes timestamp)
        latest_file = sorted(filtered_files, reverse=True)[0]
        file_path = os.path.join(data_dir, latest_file)

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        logger.info(f"Loaded latest estimation results from {file_path}")
        return data
    except Exception as e:
        logger.error(f"Error getting latest estimation results: {e}", exc_info=True)
        return None