<<<<<<< HEAD
ECHO is on.
=======
# Jira Analytics Dashboard

Интерактивное веб-приложение для анализа задач в Jira. Позволяет визуализировать и анализировать данные по задачам, оценкам времени и эффективности работы команды.

## Возможности

- **Извлечение данных из Jira** с использованием API
- **Интерактивные графики** для анализа:
  - Открытые задачи со списаниями времени
  - Распределение задач по проектам
  - Сравнение оценки и затраченного времени
- **Расширенный анализ метрик**:
  - Общий коэффициент эффективности
  - Средняя оценка на задачу
  - Всего затраченное время
- **Прямые переходы в Jira** по проектам и задачам

## Требования

- Python 3.8+
- Flask 2.0+
- Matplotlib 3.4+
- Pandas 1.3+
- Requests 2.26+
- Bootstrap 5 (включено в проект)
- Chart.js (включено в проект)

## Установка и запуск

### Установка на сервере с Ubuntu

1. **Клонирование репозитория**
```bash
git clone https://github.com/your-username/jira-analytics-dashboard.git
cd jira-analytics-dashboard
```

2. **Настройка виртуального окружения**
```bash
sudo apt update && sudo apt install python3 python3-venv python3-pip -y
python3 -m venv venv
source venv/bin/activate
```

3. **Установка зависимостей для работы с графикой**
```bash
sudo apt install python3-dev libpq-dev build-essential libssl-dev libffi-dev libxml2-dev libxslt1-dev zlib1g-dev -y
sudo apt install libfreetype6-dev libpng-dev -y
```

4. **Установка Python зависимостей**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

5. **Настройка конфигурации**
```bash
cp config.example.py config.py
# Отредактируйте config.py с вашими настройками Jira
```

6. **Запуск приложения**
```bash
python app.py
```

Приложение будет доступно по адресу `http://localhost:5000`.

## Настройка для автоматического запуска

### Используя systemd

1. Создайте файл службы:
```bash
sudo nano /etc/systemd/system/jira-analyzer.service
```

2. Добавьте следующее содержимое:
```
[Unit]
Description=Jira Analytics Dashboard
After=network.target

[Service]
User=<your-username>
Group=<your-group>
WorkingDirectory=/path/to/jira-analytics-dashboard
Environment="PATH=/path/to/jira-analytics-dashboard/venv/bin"
ExecStart=/path/to/jira-analytics-dashboard/venv/bin/python app.py

[Install]
WantedBy=multi-user.target
```

3. Включите и запустите службу:
```bash
sudo systemctl enable jira-analyzer.service
sudo systemctl start jira-analyzer.service
```

### Используя screen

```bash
sudo apt install screen -y
screen -S jira-analytics
source venv/bin/activate
python app.py
```

Чтобы отсоединиться: `Ctrl+A` затем `D`.
Чтобы присоединиться: `screen -r jira-analytics`

## Использование

1. **Анализ на основе фильтра**:
   - Введите ID фильтра Jira
   - Укажите даты периода анализа
   - Нажмите "Начать анализ"

2. **Анализ на основе JQL запроса**:
   - Выберите "JQL запрос"
   - Введите JQL запрос
   - Укажите даты периода анализа
   - Нажмите "Начать анализ"

3. **Просмотр результатов**:
   - Изучите сводную информацию и графики
   - Нажмите на сегменты графиков для просмотра соответствующих задач в Jira

## Структура проекта

```
jira-analytics-dashboard/
├── app.py                # Основной файл приложения
├── config.py             # Настройки подключения к Jira
├── modules/              # Модули приложения
│   ├── analysis.py       # Анализ данных
│   ├── jira_analyzer.py  # Работа с Jira API
│   ├── data_processor.py # Обработка данных
│   ├── visualization.py  # Создание графиков
│   └── log_buffer.py     # Управление логами
├── routes/               # Маршруты Flask
│   ├── main_routes.py    # Основные маршруты
│   └── api_routes.py     # API маршруты
├── static/               # Статические файлы
│   ├── css/              # Стили CSS
│   ├── js/               # JavaScript файлы
│   │   ├── charts.js     # Генерация интерактивных графиков
│   │   └── main.js       # Основные JS функции
│   └── img/              # Изображения
├── templates/            # Шаблоны Flask
│   ├── base.html         # Базовый шаблон
│   ├── index.html        # Главная страница
│   └── view.html         # Страница просмотра анализа
└── jira_charts/          # Сохраненные графики и данные
```

## Разработка и модификация

### Добавление новых графиков

1. Создайте новую функцию анализа в `modules/analysis.py`
2. Добавьте визуализацию в `modules/visualization.py`
3. Обновите шаблон в `templates/view.html`
4. Добавьте JavaScript для интерактивности в `static/js/charts.js`

### Модификация JQL запросов

Для изменения специализированных JQL запросов при клике на графики, отредактируйте функцию `special_jql` в файле `routes/api_routes.py`.

## Лицензия

Этот проект распространяется под лицензией MIT.
>>>>>>> 85ba7029bb230a83c67dcfac4a9e14ca7866eb44
