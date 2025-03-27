/**
 * Summary Statistics Updater Module - Updates summary stats when switching data modes
 * With fixed hour to day conversion (8 hours = 1 day)
 */

// Update summary statistics with new data
export function updateSummaryStatistics(data) {
    console.log("Updating summary statistics with new data");

    // Hours to days conversion factor
    const HOURS_PER_DAY = 8;

    // Find summary rows by their field labels
    const summaryRows = document.querySelectorAll('.card-body table tbody tr');
    if (!summaryRows || summaryRows.length === 0) {
        console.warn("Summary statistics table not found");
        return;
    }

    // Helper function to find a row by the text in its th element
    function findRowByLabel(label) {
        for (const row of summaryRows) {
            const thElement = row.querySelector('th');
            if (thElement && thElement.textContent.includes(label)) {
                return row;
            }
        }
        return null;
    }

    // Update total issues count
    const totalIssuesRow = findRowByLabel('Всего задач');
    if (totalIssuesRow) {
        const tdElement = totalIssuesRow.querySelector('td');
        if (tdElement) {
            const newCount = data.implementation_count || data.filtered_count || 0;
            tdElement.textContent = newCount;
            console.log(`Updated total issues count to ${newCount}`);
        }
    }

    // Update project count
    const projectsCountRow = findRowByLabel('Количество проектов');
    if (projectsCountRow) {
        const tdElement = projectsCountRow.querySelector('td');
        if (tdElement) {
            const projectCount = Object.keys(data.project_estimates || {}).length;
            tdElement.textContent = projectCount;
            console.log(`Updated project count to ${projectCount}`);
        }
    }

    // Update total estimate hours (CONVERTED TO DAYS)
    const totalEstimateRow = findRowByLabel('Общая исходная оценка');
    if (totalEstimateRow) {
        const tdElement = totalEstimateRow.querySelector('td');
        if (tdElement) {
            const totalEstimateHours = Object.values(data.project_estimates || {}).reduce((sum, val) => sum + val, 0);
            const totalEstimateDays = totalEstimateHours / HOURS_PER_DAY;
            tdElement.textContent = totalEstimateDays.toFixed(2);
            console.log(`Updated total estimate to ${totalEstimateDays.toFixed(2)} days (${totalEstimateHours.toFixed(2)} hours)`);
        }
    }

    // Update total time spent hours (CONVERTED TO DAYS)
    const totalTimeSpentRow = findRowByLabel('Общее затраченное время');
    if (totalTimeSpentRow) {
        const tdElement = totalTimeSpentRow.querySelector('td');
        if (tdElement) {
            const totalTimeSpentHours = Object.values(data.project_time_spent || {}).reduce((sum, val) => sum + val, 0);
            const totalTimeSpentDays = totalTimeSpentHours / HOURS_PER_DAY;
            tdElement.textContent = totalTimeSpentDays.toFixed(2);
            console.log(`Updated total time spent to ${totalTimeSpentDays.toFixed(2)} days (${totalTimeSpentHours.toFixed(2)} hours)`);
        }
    }

    // Update average estimate per issue (CONVERTED TO DAYS)
    const avgEstimateRow = findRowByLabel('Средняя оценка на задачу');
    if (avgEstimateRow) {
        const tdElement = avgEstimateRow.querySelector('td');
        if (tdElement) {
            const totalEstimateHours = Object.values(data.project_estimates || {}).reduce((sum, val) => sum + val, 0);
            const issueCount = data.implementation_count || data.filtered_count || 0;
            const avgEstimateHours = issueCount > 0 ? totalEstimateHours / issueCount : 0;
            const avgEstimateDays = avgEstimateHours / HOURS_PER_DAY;
            tdElement.textContent = avgEstimateDays.toFixed(2);
            console.log(`Updated average estimate to ${avgEstimateDays.toFixed(2)} days (${avgEstimateHours.toFixed(2)} hours)`);
        }
    }

    // Update average time spent per issue (CONVERTED TO DAYS)
    const avgTimeSpentRow = findRowByLabel('Среднее затраченное время на задачу');
    if (avgTimeSpentRow) {
        const tdElement = avgTimeSpentRow.querySelector('td');
        if (tdElement) {
            const totalTimeSpentHours = Object.values(data.project_time_spent || {}).reduce((sum, val) => sum + val, 0);
            const issueCount = data.implementation_count || data.filtered_count || 0;
            const avgTimeSpentHours = issueCount > 0 ? totalTimeSpentHours / issueCount : 0;
            const avgTimeSpentDays = avgTimeSpentHours / HOURS_PER_DAY;
            tdElement.textContent = avgTimeSpentDays.toFixed(2);
            console.log(`Updated average time spent to ${avgTimeSpentDays.toFixed(2)} days (${avgTimeSpentHours.toFixed(2)} hours)`);
        }
    }

    // Update overall efficiency (ratio stays the same)
    const efficiencyRow = findRowByLabel('Общий коэффициент эффективности');
    if (efficiencyRow) {
        const tdElement = efficiencyRow.querySelector('td');
        if (tdElement) {
            const totalEstimateHours = Object.values(data.project_estimates || {}).reduce((sum, val) => sum + val, 0);
            const totalTimeSpentHours = Object.values(data.project_time_spent || {}).reduce((sum, val) => sum + val, 0);
            const efficiency = totalEstimateHours > 0 ? totalTimeSpentHours / totalEstimateHours : 0;
            tdElement.textContent = efficiency.toFixed(2);
            console.log(`Updated efficiency to ${efficiency.toFixed(2)}`);
        }
    }

    // Update CLM-specific metrics if they exist
    if (data.clm_issues_count !== undefined) {
        // CLM Issues count
        const clmIssuesRow = findRowByLabel('Количество тикетов CLM');
        if (clmIssuesRow) {
            const tdElement = clmIssuesRow.querySelector('td');
            if (tdElement) {
                tdElement.textContent = data.clm_issues_count;
                console.log(`Updated CLM issues count to ${data.clm_issues_count}`);
            }
        }

        // EST Issues count
        const estIssuesRow = findRowByLabel('Количество тикетов EST');
        if (estIssuesRow) {
            const tdElement = estIssuesRow.querySelector('td');
            if (tdElement) {
                tdElement.textContent = data.est_issues_count;
                console.log(`Updated EST issues count to ${data.est_issues_count}`);
            }
        }

        // Improvement Issues count
        const improvementIssuesRow = findRowByLabel('Количество Improvement');
        if (improvementIssuesRow) {
            const tdElement = improvementIssuesRow.querySelector('td');
            if (tdElement) {
                tdElement.textContent = data.improvement_issues_count;
                console.log(`Updated Improvement issues count to ${data.improvement_issues_count}`);
            }
        }

        // Linked Issues count
        const linkedIssuesRow = findRowByLabel('Всего связанных задач');
        if (linkedIssuesRow) {
            const tdElement = linkedIssuesRow.querySelector('td');
            if (tdElement) {
                tdElement.textContent = data.linked_issues_count || data.implementation_count;
                console.log(`Updated linked issues count to ${data.linked_issues_count || data.implementation_count}`);
            }
        }
    }

    // Update CLM estimate total in the dynamically populated field (CONVERTED TO DAYS)
    const totalClmEstElement = document.getElementById('total-clm-est');
    if (totalClmEstElement && data.project_clm_estimates) {
        const totalClmEstHours = Object.values(data.project_clm_estimates).reduce((sum, val) => sum + val, 0);
        const totalClmEstDays = totalClmEstHours / HOURS_PER_DAY;
        totalClmEstElement.textContent = totalClmEstDays.toFixed(2);
        console.log(`Updated total CLM estimate to ${totalClmEstDays.toFixed(2)} days (${totalClmEstHours.toFixed(2)} hours)`);
    }

    console.log("Summary statistics update complete");
}