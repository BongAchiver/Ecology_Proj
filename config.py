# Настройки Telegram-бота
TELEGRAM_TOKEN = '7672623941:AAFQbMi1NFhrP9XMFqkRkZygP7wRVFWs98Q'  # Токен бота
CHANNEL_ID = '@gos_parser'  # ID канала для отправки сообщений

# Настройки расписания
SEND_DAY_OF_WEEK = 4  # День недели для отправки (0 - понедельник, 1 - вторник, ..., 6 - воскресенье)
SEND_HOUR = 19  # Час отправки (24-часовой формат)
CHECK_INTERVAL_HOURS = 6  # Интервал проверки времени отправки (в часах)

# Настройки парсера
PAGES_TO_FETCH = 10  # Количество страниц для парсинга
PROJECTS_PER_PAGE = 20  # Количество проектов на странице
DAYS_TO_LOOK_BACK = 7  # Количество дней в прошлое для поиска проектов

# Настройки базы данных
DB_FILE = 'draft_laws.db'  # Имя файла базы данных

# Словарь для преобразования кода статуса в текст
STATUS_MAP = {
    "0": "Разработка",
    "10": "Подготовка к обсуждению",
    "20": "Идет обсуждение",
    "30": "Обсуждение завершено",
    "50": "Разработка завершена",
    "100": "Отказ от продолжения разработки"
}

# HTTP заголовки для запросов
HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json',
    'Origin': 'https://regulation.gov.ru',
    'Referer': 'https://regulation.gov.ru/projects/List/AdvancedSearch'
}

# URL для API
API_URL = "https://regulation.gov.ru/Npa/CollectionRead"

# Интервалы ожидания
SLEEP_BETWEEN_MESSAGES = 3  # Секунды ожидания между отправкой сообщений
SLEEP_AFTER_HEADER = 2  # Секунды ожидания после отправки заголовка
SLEEP_BETWEEN_API_REQUESTS = 1  # Секунды ожидания между запросами к API
ERROR_SLEEP_TIME = 60 * 60  # Секунды ожидания после ошибки в цикле отправки