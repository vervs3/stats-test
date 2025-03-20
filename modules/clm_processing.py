import logging
import re

# Get logger
logger = logging.getLogger(__name__)


def process_clm_data(clm_issues, est_issues, implementation_issues):
    """
    Process CLM, EST and implementation issues to establish connections

    Args:
        clm_issues (list): List of CLM issue dictionaries
        est_issues (list): List of EST issue dictionaries
        implementation_issues (list): List of implementation issue dictionaries

    Returns:
        dict: Processing results and metrics
    """
    logger.info(
        f"Processing {len(clm_issues)} CLM issues, {len(est_issues)} EST issues, {len(implementation_issues)} implementation issues")

    # Extract component information from EST issues
    component_to_est = {}
    est_summary = {}
    for issue in est_issues:
        issue_key = issue.get('key', '')
        if not issue_key:
            continue

        components = issue.get('fields', {}).get('components', [])
        summary = issue.get('fields', {}).get('summary', '')
        est_summary[issue_key] = summary

        # Extract original estimate if available
        original_estimate = issue.get('fields', {}).get('timeoriginalestimate', 0)
        if original_estimate is None:
            original_estimate = 0

        estimate_hours = original_estimate / 3600 if original_estimate else 0

        # Store component information
        for component in components:
            comp_name = component.get('name', '')
            if comp_name:
                if comp_name not in component_to_est:
                    component_to_est[comp_name] = []
                component_to_est[comp_name].append({
                    'issue_key': issue_key,
                    'summary': summary,
                    'estimate_hours': estimate_hours
                })

    # Extract project information from implementation issues
    project_to_implementation = {}
    for issue in implementation_issues:
        issue_key = issue.get('key', '')
        if not issue_key:
            continue

        project = issue.get('fields', {}).get('project', {}).get('key', '')
        summary = issue.get('fields', {}).get('summary', '')

        if project:
            if project not in project_to_implementation:
                project_to_implementation[project] = []
            project_to_implementation[project].append({
                'issue_key': issue_key,
                'summary': summary
            })

    # Map components to projects
    component_to_project = map_components_to_projects(component_to_est.keys(), project_to_implementation.keys())

    # Create EST to project mapping
    est_to_project = {}
    for component, est_issues in component_to_est.items():
        projects = component_to_project.get(component, [])
        for est_issue in est_issues:
            est_key = est_issue['issue_key']
            if est_key not in est_to_project:
                est_to_project[est_key] = set()
            for project in projects:
                est_to_project[est_key].add(project)

    # Convert sets to lists for JSON serialization
    for est_key in est_to_project:
        est_to_project[est_key] = list(est_to_project[est_key])

    # Calculate metrics
    metrics = {
        'components_count': len(component_to_est),
        'projects_count': len(project_to_implementation),
        'mapped_components_count': sum(1 for comp in component_to_project if component_to_project[comp]),
        'unmapped_components_count': sum(
            1 for comp in component_to_est if comp not in component_to_project or not component_to_project[comp]),
        'mapped_est_count': sum(1 for est in est_to_project if est_to_project[est]),
        'unmapped_est_count': len(est_summary) - sum(1 for est in est_to_project if est_to_project[est])
    }

    # Prepare results
    results = {
        'component_to_project': component_to_project,
        'est_to_project': est_to_project,
        'est_summary': est_summary,
        'metrics': metrics
    }

    return results


def map_components_to_projects(components, projects):
    """
    Map EST components to implementation projects based on substring matching

    Args:
        components (iterable): Collection of component names
        projects (iterable): Collection of project keys

    Returns:
        dict: Mapping from component to list of related projects
    """
    mapping = {}

    # Normalize component names and project keys for better matching
    normalized_projects = {normalize_string(p): p for p in projects}

    for component in components:
        component_norm = normalize_string(component)
        matched_projects = []

        # Try direct substring matching
        for norm_proj, orig_proj in normalized_projects.items():
            # Check for at least 3 character overlap
            if (len(component_norm) >= 3 and len(norm_proj) >= 3 and
                    (component_norm[:3] in norm_proj or norm_proj[:3] in component_norm)):
                matched_projects.append(orig_proj)

        # Add additional matching strategies if needed
        # For now, we're just using the simple substring matching

        mapping[component] = matched_projects

    # Log matching statistics
    match_count = sum(1 for comp in mapping if mapping[comp])
    total_count = len(mapping)
    logger.info(f"Mapped {match_count} components to projects out of {total_count} total components")

    return mapping


def normalize_string(s):
    """
    Normalize string for better matching

    Args:
        s (str): String to normalize

    Returns:
        str: Normalized string
    """
    # Convert to lowercase
    s = s.lower()

    # Remove non-alphanumeric characters
    s = re.sub(r'[^a-z0-9]', '', s)

    return s


def generate_clm_summary_chart(clm_metrics, output_path):
    """
    Generate a summary chart for CLM analysis

    Args:
        clm_metrics (dict): CLM metrics
        output_path (str): Output file path

    Returns:
        str: Path to the generated chart
    """
    import matplotlib.pyplot as plt
    import seaborn as sns

    plt.figure(figsize=(12, 6))

    # Prepare data for chart
    metrics_to_display = [
        ('CLM Issues', clm_metrics.get('clm_issues_count', 0)),
        ('EST Issues', clm_metrics.get('est_issues_count', 0)),
        ('Improvement Issues', clm_metrics.get('improvement_issues_count', 0)),
        ('Linked Issues', clm_metrics.get('linked_issues_count', 0)),
        ('Issues with Time', clm_metrics.get('filtered_issues_count', 0))
    ]

    # Add mapping metrics if available
    if 'components_count' in clm_metrics:
        metrics_to_display.extend([
            ('Components', clm_metrics.get('components_count', 0)),
            ('Mapped Components', clm_metrics.get('mapped_components_count', 0))
        ])

    # Extract labels and values
    labels, values = zip(*metrics_to_display)

    # Create bar chart
    ax = sns.barplot(x=list(labels), y=list(values))

    # Add value labels on top of bars
    for i, v in enumerate(values):
        ax.text(i, v + 0.5, str(v), ha='center')

    plt.title('CLM Analysis Summary')
    plt.ylabel('Count')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Save chart
    plt.savefig(output_path)
    plt.close()

    return output_path