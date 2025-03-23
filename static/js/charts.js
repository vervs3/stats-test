// Chart functionality for interactive charts
document.addEventListener('DOMContentLoaded', function() {
    // Initialize charts if chart data exists
    const chartDataElement = document.getElementById('chart-data');
    if (!chartDataElement) {
        console.log("No chart data element found");
        return;
    }

    try {
        const chartData = JSON.parse(chartDataElement.textContent);
        if (!chartData) {
            console.log("Chart data element exists but no data found");
            return;
        }

        console.log("Chart data loaded successfully");

        // Флаг для отслеживания, используем ли мы исходные данные
        let isInitialData = true;

        // Initialize CLM summary chart if this is a CLM analysis
        initClmSummaryChart();

        // Функция для принудительного обновления pie chart
        function forcePieChartUpdate(chartData, pieChartInstance, ctxElement) {
            console.log("Starting force update of pie chart");

            // Проверяем, что у нас есть данные для обновления
            if (!chartData || !chartData.project_counts || Object.keys(chartData.project_counts).length === 0) {
                console.warn("No project_counts data available for pie chart update");
                return null;
            }

            // Сортируем проекты по количеству задач (от большего к меньшему)
            const sortedProjects = Object.entries(chartData.project_counts)
                .sort((a, b) => b[1] - a[1]);

            console.log("Sorted projects data for pie chart:",
                sortedProjects.length,
                "projects, first 3:",
                sortedProjects.slice(0, 3));

            // Возьмем топ-20 проектов
            const TOP_PROJECTS = 20;
            const topProjects = sortedProjects.slice(0, TOP_PROJECTS);
            const otherProjects = sortedProjects.slice(TOP_PROJECTS);

            // Создаем массивы для меток и значений
            let labels = topProjects.map(item => item[0]);
            let values = topProjects.map(item => item[1]);

            // Если есть другие проекты, добавляем их как одну категорию
            if (otherProjects.length > 0) {
                const otherValue = otherProjects.reduce((sum, item) => sum + item[1], 0);
                labels.push('Другие');
                values.push(otherValue);
            }

            // Проверяем созданные данные
            console.log("New pie chart data:", {
                labels: labels,
                values: values,
                sum: values.reduce((acc, val) => acc + val, 0)
            });

            // Если существует chart объект, обновляем его данные
            if (pieChartInstance) {
                // Удаляем существующий график
                pieChartInstance.destroy();
            }

            // Создаем цвета для графика
            const pieColors = getChartColors(labels.length);

            // Очищаем canvas
            if (ctxElement) {
                const ctx = ctxElement.getContext('2d');
                ctx.clearRect(0, 0, ctxElement.width, ctxElement.height);

                // Создаем новый график
                const newPieChart = new Chart(ctx, {
                    type: 'pie',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: values,
                            backgroundColor: pieColors,
                            borderColor: pieColors.map(color => color.replace('0.7', '1')),
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'right',
                                labels: {
                                    boxWidth: 15,
                                    padding: 10
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const label = context.label || '';
                                        const value = context.parsed || 0;
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
                                        return `${label}: ${value} задач (${percentage}%)`;
                                    }
                                }
                            }
                        },
                        onClick: (event, activeElements) => {
                            if (activeElements.length > 0) {
                                const index = activeElements[0].index;
                                const project = labels[index];

                                // Не открываем Jira для категории "Другие"
                                if (project !== 'Другие') {
                                    // Use the same special JQL for CLM mode
                                    const isClmAnalysis = !!document.querySelector('[data-source="clm"]');
                                    if (isClmAnalysis) {
                                        // For pie chart, respect the current period toggle if it exists
                                        const withoutPeriod = document.getElementById('withoutPeriod')?.checked || false;
                                        createSpecialJQL(project, 'project_issues', withoutPeriod);
                                    } else {
                                        // Для стандартных графиков используем обычную ссылку
                                        if (typeof createJiraLink === 'function') {
                                            createJiraLink(project);
                                        }
                                    }
                                } else {
                                    console.log("Clicked on 'Others' category - no action");
                                }
                            }
                        }
                    }
                });

                console.log("Created new pie chart with updated data");
                return newPieChart;
            }

            return null;
        }

        // Function to get colors for charts
        function getChartColors(count) {
            const colors = [];
            for (let i = 0; i < count; i++) {
                // Cycle through colors using golden angle for even distribution
                const hue = (i * 137) % 360;
                colors.push(`hsla(${hue}, 70%, 60%, 0.7)`);
            }
            return colors;
        }

        // Handler for chart clicks based on chart type
        function handleChartClick(event, chartType, activeElements, chart) {
            if (activeElements.length === 0) return;

            const index = activeElements[0].index;
            const project = chart.data.labels[index];
            console.log(`Chart click: ${chartType}, Project: ${project}`);

            // Формирование специфичного JQL запроса в зависимости от типа графика
            if (chartType === 'no_transitions') {
                // Check selected period mode for CLM mode
                const isClmAnalysis = !!document.querySelector('[data-source="clm"]');
                const withoutPeriod = isClmAnalysis ? document.getElementById('withoutPeriod')?.checked || false : false;

                // Для графика "Открытые задачи со списаниями"
                createSpecialJQL(project, 'open_tasks', withoutPeriod);
            } else {
                // Для стандартных графиков используем обычную ссылку
                if (typeof createJiraLink === 'function') {
                    // Ensure the project is properly encoded
                    createJiraLink(project);
                } else {
                    console.error("createJiraLink function not found");
                }
            }
        }

        // Функция для создания специального JQL запроса
        function createSpecialJQL(project, chartType, withoutPeriod = false) {
            // Базовые параметры
            const params = new URLSearchParams();
            const dateFrom = !withoutPeriod ? document.querySelector('[data-date-from]')?.getAttribute('data-date-from') : null;
            const dateTo = !withoutPeriod ? document.querySelector('[data-date-to]')?.getAttribute('data-date-to') : null;
            const baseJql = document.querySelector('[data-base-jql]')?.getAttribute('data-base-jql');
            const isClm = document.querySelector('[data-source="clm"]') ? 'true' : 'false';

            // Добавляем timestamp анализа для доступа к сохраненным данным
            const timestamp = document.querySelector('[data-timestamp]')?.getAttribute('data-timestamp') ||
                            window.location.pathname.split('/').pop();

            // Ensure project is properly encoded
            params.append('project', encodeURIComponent(project));
            params.append('chart_type', chartType);
            params.append('is_clm', isClm);
            if (dateFrom) params.append('date_from', dateFrom);
            if (dateTo) params.append('date_to', dateTo);
            if (baseJql) params.append('base_jql', baseJql);
            if (timestamp) params.append('timestamp', timestamp);
            params.append('ignore_period', withoutPeriod ? 'true' : 'false');

            console.log(`Creating special JQL for project: ${project}, chart type: ${chartType}, timestamp: ${timestamp}, ignore_period: ${withoutPeriod}`);

            // Запрос на сервер для формирования специального JQL
            fetch(`/jql/special?${params.toString()}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log("Received JQL:", data.jql);

                    // Заполняем модальное окно
                    document.getElementById('jqlQuery').value = data.jql;
                    document.getElementById('openJiraBtn').href = data.url;

                    // Показываем модальное окно
                    const bsJqlModal = new bootstrap.Modal(document.getElementById('jqlModal'));
                    bsJqlModal.show();
                })
                .catch(error => {
                    console.error('Error generating special JQL:', error);
                    alert('Ошибка при формировании JQL запроса: ' + error.message);

                    // Если произошла ошибка, используем обычную ссылку
                    if (typeof createJiraLink === 'function') {
                        createJiraLink(project);
                    }
                });
        }

        // Common chart options
        const commonOptions = {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                },
                x: {
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            },
            layout: {
                padding: {
                    left: 10,
                    right: 10,
                    top: 0,
                    bottom: 20
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        boxWidth: 15,
                        padding: 10
                    }
                }
            }
        };

        // Comparison chart (estimate vs. time spent) с возможностью фильтрации
        const ctxComparison = document.getElementById('comparisonChart');
        if (ctxComparison && chartData.project_estimates && chartData.project_time_spent) {
            console.log("Initializing comparison chart with filtering");

            // Collect all unique projects
            const allProjects = [...new Set([
                ...Object.keys(chartData.project_estimates),
                ...Object.keys(chartData.project_time_spent),
                ...(chartData.project_clm_estimates ? Object.keys(chartData.project_clm_estimates) : [])
            ])];

            if (allProjects.length > 0) {
                // Sort projects by sum of all three metrics (descending)
                allProjects.sort((a, b) => {
                    const aTotal = (chartData.project_clm_estimates?.[a] || 0) +
                                   (chartData.project_estimates[a] || 0) +
                                   (chartData.project_time_spent[a] || 0);
                    const bTotal = (chartData.project_clm_estimates?.[b] || 0) +
                                   (chartData.project_estimates[b] || 0) +
                                   (chartData.project_time_spent[b] || 0);
                    return bTotal - aTotal;
                });

                // Сохраняем полный список проектов для использования при фильтрации
                const fullProjectsList = [...allProjects];

                // Сохраним исходные данные при первой загрузке графика
                const originalChartData = {
                    project_estimates: {},
                    project_time_spent: {},
                    project_clm_estimates: {},
                    project_counts: {},
                    filtered_project_estimates: {},
                    filtered_project_time_spent: {},
                    projects: []
                };

                // Глубокое копирование данных
                if (chartData.data_source === 'clm') {
                    originalChartData.project_estimates = JSON.parse(JSON.stringify(chartData.project_estimates));
                    originalChartData.project_time_spent = JSON.parse(JSON.stringify(chartData.project_time_spent));
                    originalChartData.project_counts = JSON.parse(JSON.stringify(chartData.project_counts));

                    if (chartData.project_clm_estimates) {
                        originalChartData.project_clm_estimates = JSON.parse(JSON.stringify(chartData.project_clm_estimates));
                    }

                    // Сохраняем исходный список проектов
                    originalChartData.projects = [...allProjects];

                    console.log("Original data saved:",
                        Object.keys(originalChartData.project_estimates).length,
                        "projects in estimates,",
                        Object.keys(originalChartData.project_time_spent).length,
                        "projects in time spent");
                }

                // Инициализация состояния исключенных проектов
                let excludedProjects = new Set();

                // Создаем контейнер для элементов фильтрации над графиком
                const chartContainer = ctxComparison.closest('.chart-container');
                const filterContainer = document.createElement('div');
                filterContainer.className = 'mb-3 chart-filter-container';
                filterContainer.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <button class="btn btn-sm btn-outline-primary toggle-filter-btn">Показать/скрыть фильтр</button>
                        <div class="filter-actions" style="display: none;">
                            <button class="btn btn-sm btn-outline-success select-all-btn">Выбрать все</button>
                            <button class="btn btn-sm btn-outline-danger deselect-all-btn">Снять все</button>
                            <button class="btn btn-sm btn-outline-warning reset-filter-btn">Сбросить</button>
                        </div>
                    </div>
                    <div class="project-filter-options" style="display: none; max-height: 200px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; border-radius: 4px;">
                    </div>
                `;

                if (chartContainer && chartContainer.parentNode) {
                    chartContainer.parentNode.insertBefore(filterContainer, chartContainer);
                } else {
                    ctxComparison.parentNode.insertBefore(filterContainer, ctxComparison);
                }

                // Добавим переключатель периода для режима CLM
                if (chartData.data_source === 'clm') {
                    const periodToggleDiv = document.createElement('div');
                    periodToggleDiv.className = 'period-toggle-container mb-3';
                    periodToggleDiv.innerHTML = `
                        <div class="alert alert-info py-2">
                            <small>Режим отображения данных:</small>
                            <div class="mt-1">
                                <div class="form-check form-check-inline">
                                    <input class="form-check-input" type="radio" name="periodMode" id="withPeriod" value="withPeriod" checked>
                                    <label class="form-check-label" for="withPeriod">
                                        Данные за выбранный период
                                    </label>
                                </div>
                                <div class="form-check form-check-inline">
                                    <input class="form-check-input" type="radio" name="periodMode" id="withoutPeriod" value="withoutPeriod">
                                    <label class="form-check-label" for="withoutPeriod">
                                        Все данные CLM
                                    </label>
                                </div>
                            </div>
                            <div id="period-loading" class="mt-2" style="display: none;">
                                <div class="spinner-border spinner-border-sm text-primary" role="status">
                                    <span class="visually-hidden">Загрузка...</span>
                                </div>
                                <span class="ms-2">Загрузка данных...</span>
                            </div>
                        </div>
                    `;
                    if (filterContainer) {
                        filterContainer.appendChild(periodToggleDiv);
                    }

                    // Добавим обработчик изменения режима периода
                    const periodRadios = periodToggleDiv.querySelectorAll('input[name="periodMode"]');
                    periodRadios.forEach(radio => {
                        radio.addEventListener('change', function() {
                            const withoutPeriod = this.value === 'withoutPeriod';
                            console.log("Period mode changed to: " + (withoutPeriod ? 'without period' : 'with period'));

                            // Показываем индикатор загрузки
                            const loadingIndicator = document.getElementById('period-loading');
                            if (loadingIndicator) {
                                loadingIndicator.style.display = 'block';
                            }

                            // Update the data mode indicator
                            const dataModeIndicator = document.getElementById('data-mode-indicator');
                            if (dataModeIndicator) {
                                dataModeIndicator.textContent = withoutPeriod ? 'Все данные CLM' : 'Данные за период';
                            }

                            if (withoutPeriod && isInitialData) {
                                // Получаем полные данные только если сейчас у нас исходные данные
                                const timestamp = document.querySelector('[data-timestamp]')?.getAttribute('data-timestamp') ||
                                                window.location.pathname.split('/').pop();

                                fetch(`/api/clm-chart-data/${timestamp}`)
                                    .then(response => {
                                        if (!response.ok) {
                                            throw new Error(`Server returned ${response.status}: ${response.statusText}`);
                                        }
                                        return response.json();
                                    })
                                    .then(fullData => {
                                        if (!fullData.success) {
                                            throw new Error(fullData.error || 'Failed to get full data');
                                        }

                                        // Переключаем флаг - теперь у нас не исходные данные
                                        isInitialData = false;

                                        // ENHANCED: Store filtered data for later use
                                        originalChartData.project_estimates = JSON.parse(JSON.stringify(chartData.project_estimates));
                                        originalChartData.project_time_spent = JSON.parse(JSON.stringify(chartData.project_time_spent));
                                        originalChartData.project_counts = JSON.parse(JSON.stringify(chartData.project_counts));

                                        // Save filtered data explicitly
                                        originalChartData.filtered_project_estimates = fullData.filtered_project_estimates || {};
                                        originalChartData.filtered_project_time_spent = fullData.filtered_project_time_spent || {};

                                        // Save original project list to maintain order
                                        originalChartData.projectOrder = [...fullProjectsList];

                                        // Use full implementation issues data instead of filtered data
                                        console.log(`Switching to full implementation data:
                                            ${Object.keys(fullData.project_estimates).length} projects in estimates (${fullData.implementation_count} issues),
                                            ${Object.keys(fullData.filtered_project_estimates).length} projects in filtered estimates (${fullData.filtered_count} issues)`);

                                        // To debug data differences, log some examples:
                                        // Take first 5 common projects and show the difference
                                        const commonProjects = Object.keys(fullData.project_estimates)
                                            .filter(p => p in fullData.filtered_project_estimates)
                                            .slice(0, 5);

                                        console.log("Data comparison examples (first 5 common projects):");
                                        commonProjects.forEach(project => {
                                            const fullEst = fullData.project_estimates[project] || 0;
                                            const filteredEst = fullData.filtered_project_estimates[project] || 0;
                                            const fullSpent = fullData.project_time_spent[project] || 0;
                                            const filteredSpent = fullData.filtered_project_time_spent[project] || 0;

                                            console.log(`Project ${project}:
                                                Full data: Estimate=${fullEst}, Spent=${fullSpent}
                                                Filtered: Estimate=${filteredEst}, Spent=${filteredSpent}
                                                Differences: Estimate=${fullEst - filteredEst}, Spent=${fullSpent - filteredSpent}`);
                                        });

                                        // Обновляем данные графика с полными данными implementation issues
                                        chartData.project_estimates = fullData.project_estimates;
                                        chartData.project_time_spent = fullData.project_time_spent;

                                        if (fullData.project_clm_estimates) {
                                            chartData.project_clm_estimates = fullData.project_clm_estimates;
                                            originalChartData.project_clm_estimates = JSON.parse(JSON.stringify(fullData.project_clm_estimates));
                                        }

                                        // Также нужно создать новые данные для счетчиков проектов
                                        // на основе полного набора реализационных задач
                                        if (fullData.implementation_count > 0) {
                                            // Создаем новые счетчики на основе реализационных задач
                                            let newProjectCounts = {};

                                            // Используем project_issue_mapping из chartData, если есть
                                            if (chartData.project_issue_mapping) {
                                                // Создаем счетчик на основе mapping
                                                Object.keys(chartData.project_issue_mapping).forEach(project => {
                                                    const count = chartData.project_issue_mapping[project].length;
                                                    if (count > 0) {
                                                        newProjectCounts[project] = count;
                                                    }
                                                });
                                            } else {
                                                // Просто копируем все данные из filtered_project_estimates в качестве приближения
                                                newProjectCounts = Object.keys(fullData.project_estimates).reduce((acc, project) => {
                                                    // Используем оценки как приближение к количеству задач
                                                    if (fullData.project_estimates[project] > 0) {
                                                        acc[project] = Math.max(1, Math.round(fullData.project_estimates[project] / 8)); // примерное число задач
                                                    }
                                                    return acc;
                                                }, {});
                                            }

                                            // Сохраняем оригинальные счетчики для восстановления
                                            originalChartData.project_counts_filtered = JSON.parse(JSON.stringify(chartData.project_counts));

                                            // Обновляем счетчики
                                            chartData.project_counts = newProjectCounts;
                                            console.log("Updated project_counts for full data mode",
                                                        Object.keys(newProjectCounts).length, "projects",
                                                        "First 3 counts:", Object.entries(newProjectCounts).slice(0, 3));
                                        }

                                        // Maintain the original project order as much as possible
                                        // First, get all unique projects from both datasets
                                        const newUniqueProjects = [...new Set([
                                            ...Object.keys(fullData.project_estimates),
                                            ...Object.keys(fullData.project_time_spent),
                                            ...(fullData.project_clm_estimates ? Object.keys(fullData.project_clm_estimates) : [])
                                        ])];

                                        // Create a set for faster lookups
                                        const newProjectsSet = new Set(newUniqueProjects);

                                        // Start with existing projects that exist in the new data
                                        const orderedProjects = fullProjectsList.filter(p => newProjectsSet.has(p));

                                        // Add any new projects that weren't in the original list
                                        newUniqueProjects.forEach(p => {
                                            if (!orderedProjects.includes(p)) {
                                                orderedProjects.push(p);
                                            }
                                        });

                                        // Update the fullProjectsList with the ordered list
                                        fullProjectsList.length = 0;
                                        fullProjectsList.push(...orderedProjects);

                                        // Сбрасываем исключенные проекты
                                        excludedProjects.clear();

                                        // Обновляем опции фильтра
                                        populateFilterOptions();

                                        // Обновляем график
                                        updateChart();

                                        // Принудительно обновляем pie chart напрямую с новыми данными
                                        console.log("Directly updating pie chart after data change");
                                        if (typeof forcePieChartUpdate === 'function' && ctxProjectsPie) {
                                            pieChart = forcePieChartUpdate(chartData, pieChart, ctxProjectsPie);
                                        }

                                        console.log("Data updated to full implementation data:",
                                            Object.keys(chartData.project_estimates).length,
                                            "projects in estimates,",
                                            Object.keys(chartData.project_time_spent).length,
                                            "projects in time spent");

                                        // Скрываем индикатор загрузки
                                        if (loadingIndicator) {
                                            loadingIndicator.style.display = 'none';
                                        }
                                    })
                                    .catch(error => {
                                        console.error('Error loading full data:', error);
                                        alert('Ошибка при загрузке полных данных: ' + error.message);

                                        // При ошибке переключаем обратно на исходный режим
                                        document.getElementById('withPeriod').checked = true;
                                        if (dataModeIndicator) {
                                            dataModeIndicator.textContent = 'Данные за период';
                                        }

                                        // Скрываем индикатор загрузки
                                        if (loadingIndicator) {
                                            loadingIndicator.style.display = 'none';
                                        }
                                    });
                            } else if (!withoutPeriod && !isInitialData) {
                                // Возвращаем данные с фильтрацией по worklog
                                console.log("Switching back to filtered worklog data");

                                // Use saved filtered data from original chart data
                                if (originalChartData.filtered_project_estimates &&
                                    Object.keys(originalChartData.filtered_project_estimates).length > 0) {
                                    // If we have explicit filtered data saved, use it
                                    chartData.project_estimates = JSON.parse(JSON.stringify(originalChartData.filtered_project_estimates));
                                    chartData.project_time_spent = JSON.parse(JSON.stringify(originalChartData.filtered_project_time_spent));
                                    console.log("Using explicitly saved filtered data");

                                    // Log some data to confirm we're using different data
                                    const projectExample = Object.keys(chartData.project_estimates)[0];
                                    if (projectExample) {
                                        console.log(`Example project ${projectExample}:
                                            Current estimate: ${chartData.project_estimates[projectExample]},
                                            Original full estimate: ${originalChartData.project_estimates[projectExample]}`);
                                    }
                                } else {
                                    // Otherwise fallback to original data
                                    chartData.project_estimates = JSON.parse(JSON.stringify(originalChartData.project_estimates));
                                    chartData.project_time_spent = JSON.parse(JSON.stringify(originalChartData.project_time_spent));
                                    console.log("Using fallback original data");
                                }

                                if (originalChartData.project_clm_estimates) {
                                    chartData.project_clm_estimates = JSON.parse(JSON.stringify(originalChartData.project_clm_estimates));
                                }

                                // Также восстанавливаем оригинальные счетчики проектов
                                if (originalChartData.project_counts_filtered) {
                                    chartData.project_counts = JSON.parse(JSON.stringify(originalChartData.project_counts_filtered));
                                    console.log("Restored original project counts for",
                                                Object.keys(chartData.project_counts).length, "projects");
                                } else if (originalChartData.project_counts) {
                                    chartData.project_counts = JSON.parse(JSON.stringify(originalChartData.project_counts));
                                    console.log("Restored fallback project counts");
                                }

                                // Restore the original project order if available
                                if (originalChartData.projectOrder && originalChartData.projectOrder.length > 0) {
                                    console.log("Restoring original project order");
                                    fullProjectsList.length = 0;
                                    fullProjectsList.push(...originalChartData.projectOrder);
                                }

                                // Переключаем флаг - теперь у нас исходные данные
                                isInitialData = true;

                                // Сбрасываем исключенные проекты
                                excludedProjects.clear();

                                // Обновляем опции фильтра
                                populateFilterOptions();

                                // Обновляем график
                                updateChart();

                                // Принудительно обновляем pie chart напрямую с восстановленными данными
                                console.log("Directly updating pie chart after restoring data");
                                if (typeof forcePieChartUpdate === 'function' && ctxProjectsPie) {
                                    pieChart = forcePieChartUpdate(chartData, pieChart, ctxProjectsPie);
                                }

                                console.log("Data restored to filtered worklog data:",
                                    Object.keys(chartData.project_estimates).length,
                                    "projects in estimates,",
                                    Object.keys(chartData.project_time_spent).length,
                                    "projects in time spent");

                                // Скрываем индикатор загрузки
                                if (loadingIndicator) {
                                    loadingIndicator.style.display = 'none';
                                }
                            } else {
                                // If we're trying to switch to a mode that's already active
                                console.log("No data change needed, already in the right mode.");

                                // Скрываем индикатор загрузки
                                if (loadingIndicator) {
                                    loadingIndicator.style.display = 'none';
                                }
                            }
                        });
                    });
                }

                // Добавляем чекбоксы для проектов
                const filterOptions = filterContainer.querySelector('.project-filter-options');

                function populateFilterOptions() {
                    filterOptions.innerHTML = ''; // Очищаем содержимое

                    // Создаем чекбоксы для проектов - выводим ВСЕ проекты, включая малозначимые
                    fullProjectsList.forEach((project, index) => {
                        const isExcluded = excludedProjects.has(project);
                        const rowDiv = document.createElement('div');
                        rowDiv.className = 'form-check';
                        rowDiv.innerHTML = `
                            <input class="form-check-input project-checkbox" type="checkbox" value="${project}" id="project-${index}" ${isExcluded ? '' : 'checked'}>
                            <label class="form-check-label" for="project-${index}">${project}</label>
                        `;
                        filterOptions.appendChild(rowDiv);
                    });

                    // Добавляем обработчики событий для чекбоксов
                    const checkboxes = filterOptions.querySelectorAll('.project-checkbox');
                    checkboxes.forEach(checkbox => {
                        checkbox.addEventListener('change', function() {
                            const project = this.value;
                            if (this.checked) {
                                excludedProjects.delete(project);
                            } else {
                                excludedProjects.add(project);
                            }
                            updateChart();
                        });
                    });
                }

                // Заполняем опции фильтра
                populateFilterOptions();

                // Обработчики для кнопок фильтра
                const toggleFilterBtn = filterContainer.querySelector('.toggle-filter-btn');
                const filterActions = filterContainer.querySelector('.filter-actions');
                const selectAllBtn = filterContainer.querySelector('.select-all-btn');
                const deselectAllBtn = filterContainer.querySelector('.deselect-all-btn');
                const resetFilterBtn = filterContainer.querySelector('.reset-filter-btn');

                toggleFilterBtn.addEventListener('click', function() {
                    const filterOptions = filterContainer.querySelector('.project-filter-options');
                    const isVisible = filterOptions.style.display !== 'none';
                    filterOptions.style.display = isVisible ? 'none' : 'block';
                    filterActions.style.display = isVisible ? 'none' : 'flex';
                });

                selectAllBtn.addEventListener('click', function() {
                    const checkboxes = filterOptions.querySelectorAll('.project-checkbox');
                    checkboxes.forEach(checkbox => {
                        checkbox.checked = true;
                    });
                    excludedProjects.clear();
                    updateChart();
                });

                deselectAllBtn.addEventListener('click', function() {
                    const checkboxes = filterOptions.querySelectorAll('.project-checkbox');
                    checkboxes.forEach(checkbox => {
                        checkbox.checked = false;
                    });
                    excludedProjects = new Set(fullProjectsList);
                    updateChart();
                });

                resetFilterBtn.addEventListener('click', function() {
                    excludedProjects.clear();
                    populateFilterOptions();
                    updateChart();
                });

                // Создаем пустой график, который будет обновляться
                let comparisonChart = null;

                // Функция для обновления данных графика на основе выбранных проектов
                function updateChart() {
    // Фильтруем проекты, исключая те, что отмечены для исключения
    const filteredProjects = fullProjectsList.filter(project => !excludedProjects.has(project));

    // Проверяем, что у нас есть данные и проекты для отображения
    if (filteredProjects.length === 0) {
        console.warn("No projects to display after filtering");
        // Instead of leaving chart empty, show a message
        if (comparisonChart) {
            comparisonChart.destroy();
            comparisonChart = null;

            const ctx = ctxComparison.getContext('2d');
            ctx.clearRect(0, 0, ctxComparison.width, ctxComparison.height);
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.font = '16px Arial';
            ctx.fillStyle = '#666';
            ctx.fillText('Нет данных для отображения', ctxComparison.width / 2, ctxComparison.height / 2);
        }
        return;
    }

    // Ограничиваем количество проектов для читаемости (можно увеличить)
    const displayProjects = filteredProjects.slice(0, 30);

    // Verify every project in displayProjects has a corresponding entry in chart data
    displayProjects.forEach(project => {
        if (!(project in chartData.project_estimates) && !(project in chartData.project_time_spent)) {
            console.warn(`Project ${project} missing from both estimates and time spent data`);
        }
    });

    // Log some debug info about the data we're using
    if (displayProjects.length > 0) {
        const firstProject = displayProjects[0];
        console.log(`First project ${firstProject} data:
            Estimate: ${chartData.project_estimates[firstProject] || 0},
            Time spent: ${chartData.project_time_spent[firstProject] || 0}`);
    }

    // Make sure we have valid data arrays
    const estimateData = displayProjects.map(project => chartData.project_estimates[project] || 0);
    const timeSpentData = displayProjects.map(project => chartData.project_time_spent[project] || 0);

    // Verify data has meaningful values and isn't all zeros
    const estimateSum = estimateData.reduce((sum, val) => sum + val, 0);
    const timeSpentSum = timeSpentData.reduce((sum, val) => sum + val, 0);
    console.log(`Chart data totals - Estimate: ${estimateSum.toFixed(2)}, Time spent: ${timeSpentSum.toFixed(2)}`);

    // Check if data sums are effectively zero
    if (estimateSum < 0.01 && timeSpentSum < 0.01) {
        console.warn("Chart data totals are effectively zero, chart may appear empty");
    }

    let needNewChart = !comparisonChart;

    // Если график уже существует, обновляем его данные
    if (comparisonChart) {
        comparisonChart.data.labels = displayProjects;

        // Обновляем данные каждого набора данных
        let datasetIndex = 0;

        // Если есть CLM оценки, обновляем их данные
        if (chartData.project_clm_estimates &&
            Object.values(chartData.project_clm_estimates).some(val => val > 0)) {

            if (datasetIndex >= comparisonChart.data.datasets.length) {
                // Dataset missing, recreate chart
                comparisonChart.destroy();
                comparisonChart = null;
                needNewChart = true;
            } else {
                comparisonChart.data.datasets[datasetIndex].data =
                    displayProjects.map(project => chartData.project_clm_estimates[project] || 0);
                datasetIndex++;
            }
        }

        // Check if we have enough datasets
        if (!needNewChart && datasetIndex + 1 >= comparisonChart.data.datasets.length) {
            console.warn("Not enough datasets in chart, recreating");
            comparisonChart.destroy();
            comparisonChart = null;
            needNewChart = true;
        }

        if (!needNewChart) {
            // Обновляем исходные оценки
            comparisonChart.data.datasets[datasetIndex].data = estimateData;
            datasetIndex++;

            // Обновляем затраченное время
            comparisonChart.data.datasets[datasetIndex].data = timeSpentData;

            // Force a full redraw
            comparisonChart.update('none');
        }
    }

    // Create new chart if needed
    if (needNewChart) {
        // Получаем данные CLM оценок, если они доступны
        const clmEstimateData = chartData.project_clm_estimates
            ? displayProjects.map(project => chartData.project_clm_estimates[project] || 0)
            : null;

        // Создаем массив набора данных, который будет использоваться для графика
        const datasets = [];

        // Добавляем CLM оценку только если данные доступны
        if (clmEstimateData && clmEstimateData.some(val => val > 0)) {
            datasets.push({
                label: 'CLM оценка (часы)',
                data: clmEstimateData,
                backgroundColor: 'rgba(75, 192, 192, 0.7)',  // Зеленоватый цвет
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1
            });
        }

        // Добавляем исходную оценку и затраченное время всегда
        datasets.push({
            label: 'Исходная оценка (часы)',
            data: estimateData,
            backgroundColor: 'rgba(54, 162, 235, 0.7)',  // Синий
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 1
        });

        datasets.push({
            label: 'Затраченное время (часы)',
            data: timeSpentData,
            backgroundColor: 'rgba(255, 99, 132, 0.7)',  // Красный
            borderColor: 'rgba(255, 99, 132, 1)',
            borderWidth: 1
        });

        // Clear canvas before creating new chart
        if (ctxComparison.chart) {
            ctxComparison.chart.destroy();
        }

        // Force a clear
        const ctx = ctxComparison.getContext('2d');
        ctx.clearRect(0, 0, ctxComparison.width, ctxComparison.height);

        // Создаем новый график
        comparisonChart = new Chart(ctxComparison.getContext('2d'), {
            type: 'bar',
            data: {
                labels: displayProjects,
                datasets: datasets
            },
            options: {
                ...commonOptions,
                onClick: (event, activeElements) => {
                    if (activeElements.length === 0) return;

                    const index = activeElements[0].index;
                    const project = displayProjects[index];

                    // Add more detailed logging
                    console.log(`Comparison chart click - Index: ${index}, Project: ${project}`);

                    // Use the same special JQL for CLM mode
                    const isClmAnalysis = !!document.querySelector('[data-source="clm"]');
                    if (isClmAnalysis) {
                        // Check selected period mode
                        const withoutPeriod = document.getElementById('withoutPeriod')?.checked || false;
                        createSpecialJQL(project, 'project_issues', withoutPeriod);
                    } else if (typeof createJiraLink === 'function') {
                        // Ensure we're passing the correct project
                        createJiraLink(project);
                    } else {
                        console.error("createJiraLink function not found");
                    }
                }
            }
        });
    }
}

                // Инициализируем график с полным набором данных
                updateChart();
            } else {
                console.log("No projects with estimates or time spent");
            }
        } else {
            console.log("Comparison chart not initialized - missing element or data");
        }

        // No transitions tasks chart (переименованные в "Открытые задачи со списаниями")
        const ctxNoTrans = document.getElementById('noTransitionsChart');
        if (ctxNoTrans && chartData.special_charts && chartData.special_charts.no_transitions) {
            console.log("Initializing No Transitions Chart (renamed to Open Tasks with Worklogs)");

            const noTransData = chartData.special_charts.no_transitions;
            const noTransLabels = Object.keys(noTransData.by_project || {});

            // Only create the chart if we have data
            if (noTransLabels.length > 0) {
                const noTransValues = noTransLabels.map(project => noTransData.by_project[project] || 0);
                const noTransColors = getChartColors(noTransLabels.length);

                try {
                    const noTransChart = new Chart(ctxNoTrans.getContext('2d'), {
                        type: 'bar',
                        data: {
                            labels: noTransLabels,
                            datasets: [{
                                label: 'Количество задач',
                                data: noTransValues,
                                backgroundColor: noTransColors,
                                borderColor: noTransColors.map(color => color.replace('0.7', '1')),
                                borderWidth: 1
                            }]
                        },
                        options: {
                            ...commonOptions,
                            onClick: (event, activeElements) => {
                                handleChartClick(event, 'no_transitions', activeElements, noTransChart);
                            }
                        }
                    });
                } catch (err) {
                    console.error("Error creating no transitions chart:", err);
                }
            } else {
                console.log("No transitions chart has no data");
            }
        } else {
            console.log("No transitions chart not initialized - missing element or data");
        }

        // Projects Pie Chart (переименованный в "Распределение задач по проектам")
        const ctxProjectsPie = document.getElementById('projectsPieChart');
        let pieChart = null;

        if (ctxProjectsPie && chartData.project_counts && Object.keys(chartData.project_counts).length > 0) {
            console.log("Initializing projects pie chart");

            // Function to update the pie chart based on current data
            function updatePieChart() {
                console.log("Updating pie chart with current data", {
                    'project_counts_keys': Object.keys(chartData.project_counts).length,
                    'sample_counts': Object.entries(chartData.project_counts).slice(0, 3)
                });

                // Add period toggle for the pie chart if in CLM mode (independent of the comparison chart)
                if (chartData.data_source === 'clm' && !document.querySelector('.pie-period-toggle-container')) {
                    const chartContainer = ctxProjectsPie.closest('.chart-container');
                    if (chartContainer) {
                        const periodToggleDiv = document.createElement('div');
                        periodToggleDiv.className = 'period-toggle-container pie-period-toggle-container mb-3';
                        periodToggleDiv.innerHTML = `
                            <div class="alert alert-info py-2">
                                <small>Режим отображения данных:</small>
                                <div class="mt-1">
                                    <div class="form-check form-check-inline">
                                        <input class="form-check-input" type="radio" name="piePeriodMode" id="pieWithPeriod" value="withPeriod" checked>
                                        <label class="form-check-label" for="pieWithPeriod">
                                            Данные за выбранный период
                                        </label>
                                    </div>
                                    <div class="form-check form-check-inline">
                                        <input class="form-check-input" type="radio" name="piePeriodMode" id="pieWithoutPeriod" value="withoutPeriod">
                                        <label class="form-check-label" for="pieWithoutPeriod">
                                            Все данные CLM
                                        </label>
                                    </div>
                                </div>
                                <div id="pie-period-loading" class="mt-2" style="display: none;">
                                    <div class="spinner-border spinner-border-sm text-primary" role="status">
                                        <span class="visually-hidden">Загрузка...</span>
                                    </div>
                                    <span class="ms-2">Загрузка данных...</span>
                                </div>
                            </div>
                        `;

                        // Insert the toggle before the chart
                        chartContainer.parentNode.insertBefore(periodToggleDiv, chartContainer);

                        // Add event listeners for the new toggle
                        const piePeriodRadios = periodToggleDiv.querySelectorAll('input[name="piePeriodMode"]');
                        piePeriodRadios.forEach(radio => {
                            radio.addEventListener('change', function() {
                                const withoutPeriod = this.value === 'withoutPeriod';

                                // Update the pie indicator text
                                const pieIndicator = document.getElementById('pie-data-mode-indicator');
                                if (pieIndicator) {
                                    pieIndicator.textContent = withoutPeriod ? 'Все данные CLM' : 'Данные за период';
                                }

                                // Show loading indicator
                                const loadingIndicator = document.getElementById('pie-period-loading');
                                if (loadingIndicator) {
                                    loadingIndicator.style.display = 'block';
                                }

                                // Сохраняем ссылку на индикатор загрузки для использования позже
                                window.piePeriodLoadingIndicator = loadingIndicator;

                                // Synchronize with the main toggle to keep data consistent
                                const mainPeriodToggle = document.getElementById(withoutPeriod ? 'withoutPeriod' : 'withPeriod');
                                if (mainPeriodToggle && !mainPeriodToggle.checked) {
                                    // Программно меняем главный переключатель
                                    mainPeriodToggle.checked = true;

                                    // Вызываем событие change вручную для главного переключателя
                                    const event = new Event('change');
                                    mainPeriodToggle.dispatchEvent(event);
                                } else {
                                    // Если переключатели уже синхронизированы, обновим диаграмму сами
                                    // и скроем индикатор загрузки после небольшой задержки
                                    setTimeout(() => {
                                        updatePieChart();
                                        if (loadingIndicator) {
                                            loadingIndicator.style.display = 'none';
                                        }
                                    }, 300);
                                }
                            });
                        });

                        // Listen to changes on the main toggle to keep our toggle in sync
                        const mainPeriodRadios = document.querySelectorAll('input[name="periodMode"]');
                        mainPeriodRadios.forEach(radio => {
                            radio.addEventListener('change', function() {
                                const withoutPeriod = this.value === 'withoutPeriod';

                                // Синхронизируем переключатель pie chart
                                const piePeriodToggle = document.getElementById(withoutPeriod ? 'pieWithoutPeriod' : 'pieWithPeriod');
                                if (piePeriodToggle && !piePeriodToggle.checked) {
                                    piePeriodToggle.checked = true;
                                }

                                // Скрываем спиннер pie chart после небольшой задержки
                                setTimeout(() => {
                                    // Проверяем сохраненный индикатор
                                    if (window.piePeriodLoadingIndicator) {
                                        window.piePeriodLoadingIndicator.style.display = 'none';
                                    }

                                    // А также ищем его по ID (для надежности)
                                    const pieLoadingIndicator = document.getElementById('pie-period-loading');
                                    if (pieLoadingIndicator) {
                                        pieLoadingIndicator.style.display = 'none';
                                    }
                                }, 500); // Увеличенная задержка для уверенности
                            });
                        });
                    }
                }

                // Вызываем forcePieChartUpdate для создания или обновления диаграммы
                console.log("Calling forcePieChartUpdate from updatePieChart");
                pieChart = forcePieChartUpdate(chartData, pieChart, ctxProjectsPie);
            }

            // Initial chart creation
            updatePieChart();

            // Add period toggle indicator to the chart header if in CLM mode
            if (chartData.data_source === 'clm') {
                const chartCard = ctxProjectsPie.closest('.card');
                if (chartCard) {
                    const cardHeader = chartCard.querySelector('.card-header');
                    if (cardHeader) {
                        // Check if an indicator already exists
                        if (!cardHeader.querySelector('#pie-data-mode-indicator')) {
                            const indicator = document.createElement('span');
                            indicator.id = 'pie-data-mode-indicator';
                            indicator.className = 'badge bg-info';
                            indicator.textContent = 'Данные за период';

                            // Create a container for the header title and indicator
                            const headerContainer = document.createElement('div');
                            headerContainer.className = 'd-flex justify-content-between align-items-center w-100';

                            // Move existing content to the container
                            const existingContent = cardHeader.innerHTML;
                            headerContainer.innerHTML = `<h4>${existingContent}</h4>`;
                            headerContainer.appendChild(indicator);

                            // Clear card header and add the new container
                            cardHeader.innerHTML = '';
                            cardHeader.appendChild(headerContainer);
                        }
                    }
                }

                // Listen for changes on the period radio buttons (shared with comparison chart)
                const periodRadios = document.querySelectorAll('input[name="periodMode"]');
                periodRadios.forEach(radio => {
                    radio.addEventListener('change', function() {
                        // Update the pie chart indicator
                        const pieIndicator = document.getElementById('pie-data-mode-indicator');
                        if (pieIndicator) {
                            pieIndicator.textContent = this.value === 'withoutPeriod' ? 'Все данные CLM' : 'Данные за период';
                        }

                        // When data changes in updateChart() for comparison chart,
                        // we also need to update the pie chart with the new data
                        // This will happen automatically when the data is fetched
                        setTimeout(updatePieChart, 500);  // Small delay to ensure data is updated
                    });
                });
            }
        } else {
            console.log("Projects pie chart not initialized - missing element or data");
        }
    } catch (error) {
        console.error('Error initializing charts:', error);
    }

    // Function to initialize CLM summary chart
    function initClmSummaryChart() {
        const clmDataElement = document.getElementById('clm-data');
        const ctxClmSummary = document.getElementById('clmSummaryChart');

        if (!clmDataElement || !ctxClmSummary) {
            console.log("CLM summary chart not initialized - missing element or data");
            return;
        }

        try {
            const clmData = JSON.parse(clmDataElement.textContent);

            const clmColors = [
                'rgba(75, 192, 192, 0.7)',  // CLM Issues
                'rgba(54, 162, 235, 0.7)',  // EST Issues
                'rgba(153, 102, 255, 0.7)', // Improvement Issues
                'rgba(255, 159, 64, 0.7)',  // Linked Issues
                'rgba(255, 99, 132, 0.7)'   // Filtered Issues
            ];

            const clmChart = new Chart(ctxClmSummary.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: clmData.labels,
                    datasets: [{
                        label: 'Количество',
                        data: clmData.values,
                        backgroundColor: clmColors,
                        borderColor: clmColors.map(color => color.replace('0.7', '1')),
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `Количество: ${context.raw}`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        },
                        x: {
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45
                            }
                        }
                    },
                    // Добавляем обработчик клика на графике
                    onClick: (event, activeElements) => {
                        if (activeElements.length === 0) return;

                        const index = activeElements[0].index;
                        const label = clmData.labels[index];

                        // Создаем JQL в зависимости от того, на какой столбец нажали
                        let chartType = '';
                        if (label === 'CLM Issues') {
                            chartType = 'clm_issues';
                        } else if (label === 'EST Issues') {
                            chartType = 'est_issues';
                        } else if (label === 'Improvement Issues') {
                            chartType = 'improvement_issues';
                        } else if (label === 'Linked Issues') {
                            chartType = 'linked_issues';
                        } else if (label === 'Filtered Issues') {
                            chartType = 'filtered_issues';
                        }

                        if (chartType) {
                            // Respect the current period toggle if it exists
                            const withoutPeriod = document.getElementById('withoutPeriod')?.checked || false;
                            // Используем 'all' как параметр project чтобы получить все задачи данного типа
                            createSpecialJQL('all', chartType, withoutPeriod);
                        }
                    }
                }
            });

            console.log("CLM summary chart initialized successfully");
        } catch (error) {
            console.error('Error initializing CLM summary chart:', error);
        }
    }
});