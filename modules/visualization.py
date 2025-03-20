# Установка бэкенда, который не использует GUI
import matplotlib
matplotlib.use('Agg')  # Важно установить до любых других импортов matplotlib

import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from modules.data_processor import get_improved_open_statuses, get_status_categories, logger


def create_visualizations(df, output_dir='jira_charts', logger=None):
    """
    Create visualizations from processed data.
    Removed charts "Original estimate by project" and "Time spent by project".
    Added chart for issues without transitions (which are likely still in OPEN status).

    Args:
        df (pandas.DataFrame): Processed data
        output_dir (str): Directory for saving visualizations
        logger: Logger instance

    Returns:
        dict: Paths to generated charts
    """
    # Set default logger if none provided
    if logger is None:
        import logging
        logger = logging.getLogger(__name__)

    if df.empty:
        logger.warning("No data for visualization.")
        return {}

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chart_paths = {}

    # Set consistent style
    sns.set(style="whitegrid")
    plt.rcParams.update({'font.size': 10})

    # Create all visualizations
    chart_paths.update(create_project_distribution_chart(df, output_dir))
    chart_paths.update(create_comparison_chart(df, output_dir))
    chart_paths.update(create_pie_chart(df, output_dir))
    chart_paths.update(create_efficiency_chart(df, output_dir))
    chart_paths.update(create_no_transitions_chart(df, output_dir, logger))
    chart_paths.update(create_open_tasks_chart(df, output_dir, logger))
    chart_paths.update(create_closed_tasks_chart(df, output_dir, logger))

    # Generate summary statistics
    summary = {
        'total_issues': len(df),
        'total_original_estimate_hours': df['original_estimate_hours'].sum(),
        'total_time_spent_hours': df['time_spent_hours'].sum(),
        'projects_count': len(df['project'].unique()),
        'projects': df['project'].unique().tolist(),
        'avg_estimate_per_issue': df['original_estimate_hours'].mean() if len(df) > 0 else 0,
        'avg_time_spent_per_issue': df['time_spent_hours'].mean() if len(df) > 0 else 0,
        'overall_efficiency': (df['time_spent_hours'].sum() / df['original_estimate_hours'].sum())
        if df['original_estimate_hours'].sum() > 0 else 0
    }

    # Add info about issues without transitions
    no_transitions_count = df['no_transitions'].sum()
    if no_transitions_count > 0:
        summary['no_transitions_tasks_count'] = int(no_transitions_count)

    # Add open tasks data
    open_statuses = get_improved_open_statuses(df)
    open_tasks = df[df['status'].isin(open_statuses) & (df['time_spent_hours'] > 0)]
    if not open_tasks.empty:
        summary['open_tasks_count'] = len(open_tasks)
        summary['open_tasks_time_spent_hours'] = open_tasks['time_spent_hours'].sum()

    # Add closed tasks data
    status_categories = get_status_categories(df)
    closed_statuses = status_categories['closed_statuses']
    closed_tasks = df[df['status'].isin(closed_statuses) & (~df['has_comments']) & (~df['has_attachments'])]
    if not closed_tasks.empty:
        summary['completed_tasks_no_comments_count'] = len(closed_tasks)

    # Save summary as JSON
    summary_path = f"{output_dir}/summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=4, ensure_ascii=False)

    chart_paths['summary'] = summary_path

    logger.info(f"Created {len(chart_paths)} visualizations in {output_dir}")
    return chart_paths


def configure_axis(ax, rotation=45):
    """Configure axis for better readability"""
    # Get current axis labels
    labels = ax.get_xticklabels()
    # Set rotation and alignment
    ax.set_xticklabels(labels, rotation=rotation, ha='right')
    # Improve chart layout
    plt.tight_layout()


def create_project_distribution_chart(df, output_dir):
    """Create project distribution chart"""
    plt.figure(figsize=(10, 6))
    project_counts = df['project'].value_counts()
    ax = sns.barplot(x=project_counts.index, y=project_counts.values)
    configure_axis(ax)
    plt.title('Распределение задач по проектам')
    plt.xlabel('Проект')
    plt.ylabel('Количество задач')

    project_chart_path = f"{output_dir}/project_distribution.png"
    plt.savefig(project_chart_path)
    plt.close()
    return {'project_distribution': project_chart_path}


def create_comparison_chart(df, output_dir):
    """Create comparison chart between estimate and time spent"""
    # Get data for projects
    project_estimates = df.groupby('project')['original_estimate_hours'].sum().sort_values(ascending=False)
    project_time_spent = df.groupby('project')['time_spent_hours'].sum().sort_values(ascending=False)

    plt.figure(figsize=(14, 8))

    # Include only projects with either estimate or time spent
    all_projects = list(set(project_estimates.index) | set(project_time_spent.index))

    comparison_df = pd.DataFrame(index=all_projects, columns=['Исходная оценка', 'Затраченное время'])

    for project in all_projects:
        comparison_df.loc[project, 'Исходная оценка'] = project_estimates.get(project, 0)
        comparison_df.loc[project, 'Затраченное время'] = project_time_spent.get(project, 0)

    # Sort by total value (estimate + time spent)
    comparison_df['Всего'] = comparison_df['Исходная оценка'] + comparison_df['Затраченное время']
    comparison_df = comparison_df.sort_values('Всего', ascending=False).drop('Всего', axis=1)

    comparison_df_melted = pd.melt(
        comparison_df.reset_index(),
        id_vars=['index'],
        value_vars=['Исходная оценка', 'Затраченное время'],
        var_name='Метрика',
        value_name='Часы'
    )

    ax = sns.barplot(x='index', y='Часы', hue='Метрика', data=comparison_df_melted)
    configure_axis(ax)
    plt.title('Исходная оценка vs. Затраченное время по проектам (часы)')
    plt.xlabel('Проект')
    plt.ylabel('Часы')

    comparison_chart_path = f"{output_dir}/estimate_vs_spent_by_project.png"
    plt.savefig(comparison_chart_path)
    plt.close()
    return {'comparison': comparison_chart_path}


def create_pie_chart(df, output_dir):
    """Create pie chart of project distribution"""
    project_counts = df['project'].value_counts()

    if len(project_counts) > 0:
        plt.figure(figsize=(10, 10))

        # Limit number of slices for readability
        MAX_SLICES = 10
        if len(project_counts) > MAX_SLICES:
            # If more than MAX_SLICES projects, keep MAX_SLICES-1 largest and group others
            top_projects = project_counts.nlargest(MAX_SLICES - 1)
            other_count = project_counts.sum() - top_projects.sum()

            # Create new series with added "Other" category
            pie_data = pd.Series({**top_projects.to_dict(), "Другие": other_count})
        else:
            pie_data = project_counts

        plt.pie(pie_data.values, labels=pie_data.index, autopct='%1.1f%%', startangle=90)
        plt.axis('equal')
        plt.title('Распределение задач по проектам')

        pie_chart_path = f"{output_dir}/project_distribution_pie.png"
        plt.savefig(pie_chart_path)
        plt.close()
        return {'project_pie': pie_chart_path}
    return {}


def create_efficiency_chart(df, output_dir):
    """Create efficiency ratio chart"""
    # Get data for projects
    project_estimates = df.groupby('project')['original_estimate_hours'].sum()
    project_time_spent = df.groupby('project')['time_spent_hours'].sum()

    plt.figure(figsize=(12, 7))
    efficiency_df = pd.DataFrame({
        'Исходная оценка': project_estimates,
        'Затраченное время': project_time_spent
    }).fillna(0)

    # Calculate efficiency ratio (avoid division by zero)
    efficiency_df['Коэффициент эффективности'] = efficiency_df.apply(
        lambda row: row['Затраченное время'] / row['Исходная оценка'] if row['Исходная оценка'] > 0 else 0,
        axis=1
    )

    # Sort and filter projects without original estimate
    efficiency_df = efficiency_df[efficiency_df['Исходная оценка'] > 0].sort_values('Коэффициент эффективности')

    if not efficiency_df.empty:
        ax = sns.barplot(x=efficiency_df.index, y=efficiency_df['Коэффициент эффективности'])
        configure_axis(ax)

        # Add horizontal line at y=1 (where time spent equals original estimate)
        plt.axhline(y=1, color='r', linestyle='--')

        plt.title('Коэффициент эффективности по проектам (Затраченное время / Исходная оценка)')
        plt.xlabel('Проект')
        plt.ylabel('Коэффициент')

        efficiency_chart_path = f"{output_dir}/efficiency_ratio_by_project.png"
        plt.savefig(efficiency_chart_path, bbox_inches='tight')
        plt.close()
        return {'efficiency': efficiency_chart_path}
    return {}


def create_no_transitions_chart(df, output_dir, logger):
    """Create chart for issues without transitions (likely still in OPEN status)"""
    logger.info("GENERATING NO TRANSITIONS TASKS CHART")
    chart_paths = {}

    try:
        # Filter issues without transitions
        no_transitions_tasks = df[df['no_transitions'] == True]
        logger.info(f"FOUND {len(no_transitions_tasks)} TASKS WITH NO TRANSITIONS (PROBABLY NEW)")

        plt.figure(figsize=(12, 7))

        if not no_transitions_tasks.empty:
            # Group by project
            no_transitions_by_project = no_transitions_tasks.groupby('project').size().sort_values(ascending=False)
            logger.info(f"NO TRANSITIONS TASKS BY PROJECT: {no_transitions_by_project.to_dict()}")

            if not no_transitions_by_project.empty:
                ax = sns.barplot(x=no_transitions_by_project.index, y=no_transitions_by_project.values)
                ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
                plt.tight_layout()
                plt.title('Задачи без transitions по проектам (вероятно новые)')
                plt.xlabel('Проект')
                plt.ylabel('Количество задач')
            else:
                # Empty chart
                plt.text(0.5, 0.5, "Нет задач без transitions",
                         horizontalalignment='center', verticalalignment='center',
                         transform=plt.gca().transAxes, fontsize=14)
                plt.xticks([])
                plt.yticks([])
                plt.title('Задачи без transitions (вероятно новые)')
        else:
            # Empty chart
            plt.text(0.5, 0.5, "Нет задач без transitions",
                     horizontalalignment='center', verticalalignment='center',
                     transform=plt.gca().transAxes, fontsize=14)
            plt.xticks([])
            plt.yticks([])
            plt.title('Задачи без transitions (вероятно новые)')

        # Save chart
        no_transitions_chart_path = f"{output_dir}/no_transitions_tasks.png"
        plt.savefig(no_transitions_chart_path)
        plt.close()
        chart_paths['no_transitions_tasks'] = no_transitions_chart_path
        logger.info(f"NO TRANSITIONS TASKS CHART SAVED TO: {no_transitions_chart_path}")

        # Save metrics
        metrics_dir = os.path.join(output_dir, 'metrics')
        if not os.path.exists(metrics_dir):
            os.makedirs(metrics_dir)

        no_transitions_data = {
            'count': len(no_transitions_tasks),
            'by_project': no_transitions_tasks.groupby(
                'project').size().to_dict() if not no_transitions_tasks.empty else {}
        }

        no_transitions_metrics_path = os.path.join(metrics_dir, 'no_transitions_tasks.json')
        with open(no_transitions_metrics_path, 'w', encoding='utf-8') as f:
            json.dump(no_transitions_data, f, indent=2, ensure_ascii=False)
        logger.info(f"NO TRANSITIONS TASKS METRICS SAVED TO: {no_transitions_metrics_path}")

    except Exception as e:
        logger.error(f"ERROR GENERATING NO TRANSITIONS TASKS CHART: {str(e)}", exc_info=True)
        # Save issue count even if chart creation fails
        if 'no_transitions_tasks' in locals() and not no_transitions_tasks.empty:
            chart_paths['no_transitions_tasks_count'] = len(no_transitions_tasks)

    return chart_paths


def create_open_tasks_chart(df, output_dir, logger):
    """Create chart for open tasks with logged time"""
    logger.info("GENERATING OPEN TASKS WITH WORKLOGS CHART - IMPROVED")
    chart_paths = {}

    try:
        # Create metrics directory if it doesn't exist
        metrics_dir = os.path.join(output_dir, 'metrics')
        if not os.path.exists(metrics_dir):
            os.makedirs(metrics_dir)
            logger.info(f"Created metrics directory: {metrics_dir}")

        # Get improved open statuses detection
        improved_open_statuses = get_improved_open_statuses(df)
        logger.info(f"IMPROVED OPEN STATUSES: {improved_open_statuses}")

        # Filter open tasks with logged time
        open_tasks_improved = df[df['status'].isin(improved_open_statuses) & (df['time_spent_hours'] > 0)]
        logger.info(f"Found {len(open_tasks_improved)} open tasks using improved detection")

        # Always create a chart, even if empty
        plt.figure(figsize=(12, 7))

        if not open_tasks_improved.empty:
            open_tasks_by_project = open_tasks_improved.groupby('project')['time_spent_hours'].sum().sort_values(
                ascending=False)
            logger.info(f"OPEN TASKS BY PROJECT: {open_tasks_by_project.to_dict()}")

            if not open_tasks_by_project.empty:
                ax = sns.barplot(x=open_tasks_by_project.index, y=open_tasks_by_project.values)
                ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
                plt.tight_layout()
        else:
            # Create an empty chart with a message
            plt.text(0.5, 0.5, "Нет открытых задач с логированием времени",
                     horizontalalignment='center', verticalalignment='center',
                     transform=plt.gca().transAxes, fontsize=14)
            plt.xticks([])
            plt.yticks([])

        plt.title('Затраченное время на открытые задачи')
        plt.xlabel('Проект')
        plt.ylabel('Затраченное время (часы)')

        # Always save the chart
        open_tasks_chart_path = f"{output_dir}/open_tasks_time_spent.png"
        plt.savefig(open_tasks_chart_path)
        plt.close()
        chart_paths['open_tasks'] = open_tasks_chart_path
        logger.info(f"OPEN TASKS CHART SAVED TO: {open_tasks_chart_path}")

        # Always save metrics data, even if empty
        open_tasks_data = {
            'count': int(len(open_tasks_improved)),
            'total_time_spent': float(
                open_tasks_improved['time_spent_hours'].sum()) if not open_tasks_improved.empty else 0.0,
            'by_project': open_tasks_improved.groupby('project')[
                'time_spent_hours'].sum().to_dict() if not open_tasks_improved.empty else {},
            'task_statuses': open_tasks_improved[
                'status'].value_counts().to_dict() if not open_tasks_improved.empty else {},
            'sample_tasks': open_tasks_improved['issue_key'].head(
                10).tolist() if not open_tasks_improved.empty else []
        }

        # Save metrics file
        open_tasks_metrics_path = os.path.join(metrics_dir, 'open_tasks.json')
        with open(open_tasks_metrics_path, 'w', encoding='utf-8') as f:
            json.dump(open_tasks_data, f, indent=2, ensure_ascii=False)
        logger.info(f"OPEN TASKS METRICS SAVED TO: {open_tasks_metrics_path}")

    except Exception as e:
        logger.error(f"ERROR GENERATING OPEN TASKS CHART: {str(e)}", exc_info=True)
        # Still include count in summary data even if chart creation fails
        if 'open_tasks_improved' in locals() and not open_tasks_improved.empty:
            chart_paths['open_tasks_count'] = len(open_tasks_improved)

    return chart_paths


def create_closed_tasks_chart(df, output_dir, logger):
    """Create chart for closed tasks without comments or attachments"""
    logger.info("GENERATING CLOSED TASKS WITHOUT COMMENTS CHART")
    chart_paths = {}

    try:
        # Get status categories
        status_categories = get_status_categories(df)
        closed_statuses = status_categories['closed_statuses']

        # Filter tasks with these statuses, without comments and attachments
        closed_tasks = df[df['status'].isin(closed_statuses) & (~df['has_comments']) & (~df['has_attachments'])]
        logger.info(f"FOUND {len(closed_tasks)} CLOSED TASKS WITHOUT COMMENTS/ATTACHMENTS")

        if len(closed_tasks) > 0:
            logger.info(f"SAMPLE CLOSED TASKS: {closed_tasks['issue_key'].head(5).tolist()}")

        # Always create a chart, even if empty
        plt.figure(figsize=(12, 7))

        if not closed_tasks.empty:
            closed_tasks_by_project = closed_tasks.groupby('project').size().sort_values(ascending=False)
            logger.info(f"CLOSED TASKS BY PROJECT: {closed_tasks_by_project.to_dict()}")

            if not closed_tasks_by_project.empty:
                ax = sns.barplot(x=closed_tasks_by_project.index, y=closed_tasks_by_project.values)
                ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
                plt.tight_layout()
        else:
            # Create an empty chart with a message
            plt.text(0.5, 0.5, "Нет закрытых задач без комментариев и вложений",
                     horizontalalignment='center', verticalalignment='center',
                     transform=plt.gca().transAxes, fontsize=14)
            plt.xticks([])
            plt.yticks([])

        plt.title('Закрытые задачи без комментариев и вложений')
        plt.xlabel('Проект')
        plt.ylabel('Количество задач')

        # Always save the chart
        closed_tasks_chart_path = f"{output_dir}/completed_tasks_no_comments.png"
        plt.savefig(closed_tasks_chart_path)
        plt.close()
        chart_paths['completed_tasks_no_comments'] = closed_tasks_chart_path
        logger.info(f"CLOSED TASKS CHART SAVED TO: {closed_tasks_chart_path}")

        # Save metrics data
        metrics_dir = os.path.join(output_dir, 'metrics')
        if not os.path.exists(metrics_dir):
            os.makedirs(metrics_dir)

        closed_tasks_data = {
            'count': len(closed_tasks),
            'by_project': closed_tasks.groupby('project').size().to_dict() if not closed_tasks.empty else {}
        }

        closed_tasks_metrics_path = os.path.join(metrics_dir, 'closed_tasks.json')
        with open(closed_tasks_metrics_path, 'w', encoding='utf-8') as f:
            json.dump(closed_tasks_data, f, indent=2, ensure_ascii=False)
        logger.info(f"CLOSED TASKS METRICS SAVED TO: {closed_tasks_metrics_path}")

    except Exception as e:
        logger.error(f"ERROR GENERATING CLOSED TASKS CHART: {str(e)}", exc_info=True)
        # Still include count in summary data even if chart creation fails
        if 'closed_tasks' in locals() and not closed_tasks.empty:
            chart_paths['completed_tasks_no_comments_count'] = len(closed_tasks)

    return chart_paths


def run_analysis(use_filter=True, filter_id=114476, jql_query=None, date_from=None, date_to=None):
    """
    Run Jira data analysis in a separate thread

    Args:
        use_filter (bool): Whether to use filter ID or JQL query
        filter_id (str/int): ID of Jira filter to use
        jql_query (str): JQL query to use instead of filter ID
        date_from (str): Start date for worklog filtering (YYYY-MM-DD)
        date_to (str): End date for worklog filtering (YYYY-MM-DD)
    """
    global analysis_state

    try:
        # Import Jira analyzer
        from jira_analyzer import JiraAnalyzer

        analysis_state['is_running'] = True
        analysis_state['progress'] = 0
        analysis_state['status_message'] = 'Initialization...'

        # Create timestamp folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(CHARTS_DIR, timestamp)
        analysis_state['current_folder'] = timestamp

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Create directory for JSON data
        data_dir = os.path.join(output_dir, 'data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        # Create directory for metrics
        metrics_dir = os.path.join(output_dir, 'metrics')
        if not os.path.exists(metrics_dir):
            os.makedirs(metrics_dir)

        # Initialize Jira analyzer
        analyzer = JiraAnalyzer()

        # Create JQL query with time period
        final_jql = ""
        if use_filter:
            final_jql = f'filter={filter_id}'
        else:
            final_jql = jql_query or ""

        # Add date filtering if specified
        date_conditions = []
        if date_from:
            date_conditions.append(f'worklogDate >= "{date_from}"')
        if date_to:
            date_conditions.append(f'worklogDate <= "{date_to}"')

        if date_conditions:
            if final_jql:
                final_jql = f"({final_jql}) AND ({' AND '.join(date_conditions)})"
            else:
                final_jql = ' AND '.join(date_conditions)

        analysis_state['status_message'] = f'Using query: {final_jql}'
        analysis_state['progress'] = 10

        # Fetch issues
        analysis_state['status_message'] = 'Fetching issues from Jira...'
        issues = analyzer.get_issues_by_filter(jql_query=final_jql)

        analysis_state['total_issues'] = len(issues)
        analysis_state['status_message'] = f'Found {len(issues)} issues.'
        analysis_state['progress'] = 30

        if not issues:
            analysis_state['status_message'] = "No issues found. Check query or credentials."
            analysis_state['is_running'] = False
            return

        # Process data
        analysis_state['status_message'] = 'Processing issue data...'
        analysis_state['progress'] = 50
        df = analyzer.process_issues_data(issues)

        # Save raw data for interactive charts
        raw_data_path = os.path.join(data_dir, 'raw_data.json')
        df.to_json(raw_data_path, orient='records')

        # Create visualizations
        analysis_state['status_message'] = 'Creating visualizations...'
        analysis_state['progress'] = 70
        chart_paths = analyzer.create_visualizations(df, output_dir)

        # Generate data for interactive charts
        analysis_state['status_message'] = 'Creating interactive charts...'
        analysis_state['progress'] = 80

        # Project data
        project_counts = df['project'].value_counts().to_dict()
        project_estimates = df.groupby('project')['original_estimate_hours'].sum().to_dict()
        project_time_spent = df.groupby('project')['time_spent_hours'].sum().to_dict()

        # Special chart data

        # 1. No transitions tasks data
        no_transitions_tasks = df[df['no_transitions'] == True]
        no_transitions_by_project = no_transitions_tasks.groupby(
            'project').size().to_dict() if not no_transitions_tasks.empty else {}

        # 2. Open tasks data
        # Get improved open statuses detection
        improved_open_statuses = get_improved_open_statuses(df)
        open_tasks = df[df['status'].isin(improved_open_statuses) & (df['time_spent_hours'] > 0)]
        open_tasks_by_project = open_tasks.groupby('project')[
            'time_spent_hours'].sum().to_dict() if not open_tasks.empty else {}

        # 3. Closed tasks without comments data
        status_categories = get_status_categories(df)
        closed_statuses = status_categories['closed_statuses']
        closed_tasks = df[df['status'].isin(closed_statuses) & (~df['has_comments']) & (~df['has_attachments'])]
        closed_tasks_by_project = closed_tasks.groupby('project').size().to_dict() if not closed_tasks.empty else {}

        # Save data for interactive charts
        chart_data = {
            'project_counts': project_counts,
            'project_estimates': project_estimates,
            'project_time_spent': project_time_spent,
            'projects': list(
                set(list(project_counts.keys()) + list(project_estimates.keys()) + list(project_time_spent.keys()))),
            'filter_params': {
                'filter_id': filter_id if use_filter else None,
                'jql': jql_query if not use_filter else None,
                'date_from': date_from,
                'date_to': date_to
            },
            # Add special chart data
            'special_charts': {
                'no_transitions': {
                    'title': 'Задачи без transitions (вероятно новые)',
                    'by_project': no_transitions_by_project,
                    'total': len(no_transitions_tasks)
                },
                'open_tasks': {
                    'title': 'Затраченное время на открытые задачи',
                    'by_project': open_tasks_by_project,
                    'total': len(open_tasks),
                    'total_time': float(open_tasks['time_spent_hours'].sum()) if not open_tasks.empty else 0.0
                },
                'closed_no_comments': {
                    'title': 'Закрытые задачи без комментариев/вложений',
                    'by_project': closed_tasks_by_project,
                    'total': len(closed_tasks)
                }
            }
        }

        chart_data_path = os.path.join(data_dir, 'chart_data.json')
        with open(chart_data_path, 'w', encoding='utf-8') as f:
            json.dump(chart_data, f, indent=4, ensure_ascii=False)

        # Create index file with chart information
        index_data = {
            'timestamp': timestamp,
            'total_issues': len(issues),
            'charts': chart_paths,
            'summary': {},
            'date_from': date_from,
            'date_to': date_to,
            'filter_id': filter_id if use_filter else None,
            'jql_query': jql_query if not use_filter else None
        }

        # Load summary data if available
        summary_path = chart_paths.get('summary')
        if summary_path and os.path.exists(summary_path):
            try:
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary_data = json.load(f)
                    index_data['summary'] = summary_data
            except Exception as e:
                logger.error(f"Error reading summary: {e}")

        # Save index file
        index_path = os.path.join(output_dir, 'index.json')
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=4, ensure_ascii=False)

        analysis_state['status_message'] = f'Analysis complete. Charts saved to {output_dir}.'
        analysis_state['progress'] = 100
        analysis_state['last_run'] = timestamp

        # Save raw issues for diagnostics
        raw_issues_path = os.path.join(output_dir, 'raw_issues.json')
        with open(raw_issues_path, 'w', encoding='utf-8') as f:
            json.dump(issues, f, indent=2, ensure_ascii=False)
        logger.info(f"Raw issue data saved to {raw_issues_path}")

    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)
        analysis_state['status_message'] = f"An error occurred: {str(e)}"
    finally:
        analysis_state['is_running'] = False