import sqlite3
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from datetime import datetime, timedelta
import pytz
import json
import asyncio
import logging
from aiogram.exceptions import TelegramRetryAfter

# Импорт настроек из конфигурационного файла
from config import *

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()


def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS draft_laws
                 (id TEXT PRIMARY KEY, title TEXT, status TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")


def insert_draft_law(id, title, status):
    """Добавление законопроекта в базу"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO draft_laws (id, title, status, timestamp) VALUES (?, ?, ?, ?)",
                  (id, title, status, datetime.now().isoformat()))
        conn.commit()
        logger.info(f"✅ Добавлен новый законопроект: ID={id}")
    except sqlite3.IntegrityError:
        logger.info(f"⚠️ Законопроект с ID={id} уже существует в базе")
    conn.close()


def get_all_draft_laws():
    """Получение всех законопроектов из базы"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM draft_laws")
    rows = c.fetchall()
    conn.close()
    return rows


def clear_db():
    """Очистка базы данных"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM draft_laws")
    count = c.fetchone()[0]
    c.execute("DELETE FROM draft_laws")
    conn.commit()
    conn.close()
    if count > 0:
        logger.info(f"🗑️ База данных очищена. Удалено {count} записей")


async def parse_website():
    """Парсинг законопроектов относящихся к категории ОКВЭД 'Экология'"""

    logger.info("🔄 Начинаю парсинг законопроектов по ОКВЭД 'Экология'...")

    all_projects = []

    # Определяем дату для фильтрации проектов
    lookback_date = datetime.now() - timedelta(days=DAYS_TO_LOOK_BACK)

    logger.info(f"📅 Ищу проекты опубликованные после {lookback_date.strftime('%d.%m.%Y')}")

    try:
        for page in range(1, PAGES_TO_FETCH + 1):
            logger.info(f"📃 Обработка страницы {page}/{PAGES_TO_FETCH}")

            search_params = {
                "mnemonic": "Npa_AreaRegulation_Grid",
                "sort": "Date-desc",
                "page": page,
                "pageSize": PROJECTS_PER_PAGE,
                "filter": {
                    "searchString": "",
                    "statusId": None,
                    "typeId": None,
                    "kindId": None,
                    "departmentId": None,
                    "npaAreaRegulation": True,
                    "excludeProjectsArchive": True,
                    "excludeProjectsDevArchive": True
                }
            }

            response = requests.post(API_URL, headers=HTTP_HEADERS, json=search_params)
            logger.info(f"📡 Статус ответа сервера для страницы {page}: {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    projects = data.get("Data", [])
                    logger.info(f"📊 Получено проектов на странице {page}: {len(projects)}")

                    # Проверяем дату публикации проектов
                    has_recent_projects = False
                    for project in projects:
                        pub_date_str = project.get("PublishDate")
                        if pub_date_str:
                            pub_date = datetime.strptime(pub_date_str, "%d.%m.%Y %H:%M:%S")
                            if pub_date >= lookback_date:
                                all_projects.append(project)
                                has_recent_projects = True
                            else:
                                # Логируем, что нашли старый проект
                                logger.info(f"📅 Пропускаю устаревший проект от {pub_date_str}")

                    # Если на этой странице не было недавних проектов, прекращаем парсинг
                    if not has_recent_projects:
                        logger.info(f"📅 Не найдено проектов за последние {DAYS_TO_LOOK_BACK} дней, прекращаю парсинг")
                        break

                    # Делаем паузу между запросами
                    await asyncio.sleep(SLEEP_BETWEEN_API_REQUESTS)

                except json.JSONDecodeError as e:
                    logger.error(f"❌ Ошибка декодирования JSON на странице {page}: {str(e)}")
                    continue
            else:
                logger.error(f"❌ Ошибка: сервер вернул код {response.status_code} для страницы {page}")
                continue

        # После получения всех проектов обрабатываем их
        logger.info(f"📊 Всего получено проектов за последние {DAYS_TO_LOOK_BACK} дней: {len(all_projects)}")

        # Очищаем базу перед добавлением новых проектов
        clear_db()
        logger.info("🗑️ База данных очищена перед добавлением новых проектов")

        eco_projects_count = 0

        for project in all_projects:
            # Проверяем наличие ОКВЭД с Экологией
            is_eco = False
            project_id = str(project.get("ID", ""))

            # Смотрим только в поле Okveds и ищем Title со словом "Экология"
            okveds = project.get('Okveds', [])
            for okved in okveds:
                okved_title = okved.get('Title', '')
                if "эколог" in okved_title.lower():
                    is_eco = True
                    logger.info(f"✅ Проект {project_id}: Найден по ОКВЭД 'Экология': {okved_title}")
                    break

            # Если проект относится к экологии, сохраняем его
            if is_eco:
                eco_projects_count += 1
                title = project.get("Title", "")
                status_code = str(project.get("Status", "0"))

                # Получаем текстовое описание статуса
                status_text = STATUS_MAP.get(status_code, "Неизвестный статус")

                pub_date = project.get("PublishDate", "")
                creator = project.get('CreatorDepartmentReal', {}).get('Title', '')

                logger.info(f"   ID: {project_id}")
                logger.info(f"   Название: {title}")
                logger.info(f"   Статус: {status_text} (код {status_code})")
                logger.info(f"   Разработчик: {creator}")
                logger.info(f"   Дата публикации: {pub_date}")

                # Сохраняем в базу с текстовым описанием статуса
                insert_draft_law(project_id, title, status_text)

        logger.info(f"📊 Всего найдено экологических проектов: {eco_projects_count}")

        if eco_projects_count > 0:
            logger.info(f"📥 Добавлено {eco_projects_count} экологических законопроектов")
        else:
            logger.info("📥 Экологических законопроектов не обнаружено")

    except Exception as e:
        logger.error(f"❌ Ошибка при парсинге: {e}")
        logger.exception("Подробности ошибки:")


async def send_to_channel():
    """Отправка данных в канал"""
    draft_laws = get_all_draft_laws()

    if not draft_laws:
        logger.info("📤 Нечего отправлять - база пуста")
        return

    try:
        # Получаем даты для указания в сообщении
        lookback_date = (datetime.now() - timedelta(days=DAYS_TO_LOOK_BACK)).strftime('%d.%m.%Y')
        today = datetime.now().strftime('%d.%m.%Y')

        # Отправляем общую информацию
        header = (
            f"⚡️ Экологические законопроекты за период ({lookback_date} - {today}) ⚡️\n\n"
            f"Всего найдено: {len(draft_laws)} шт."
        )
        await bot.send_message(chat_id=CHANNEL_ID, text=header)
        logger.info(f"📤 Начинаю отправку {len(draft_laws)} законопроектов")

        # Ждем после отправки заголовка
        await asyncio.sleep(SLEEP_AFTER_HEADER)

        # Отправляем каждый законопроект
        for law in draft_laws:
            while True:
                try:
                    project_id = law[0]
                    title = law[1]
                    status = law[2]

                    # Формируем ссылку на проект
                    project_url = f"https://regulation.gov.ru/projects#npa={project_id}"

                    message = (
                        f"📌 <b>{title}</b>\n\n"
                        f"📊 Статус: <b>{status}</b>\n"
                        f"🆔 ID: <code>{project_id}</code>\n"
                        f"🔗 <a href='{project_url}'>Ссылка на проект</a>"
                    )
                    await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="HTML",
                                           disable_web_page_preview=True)
                    await asyncio.sleep(SLEEP_BETWEEN_MESSAGES)  # Задержка между сообщениями
                    break
                except TelegramRetryAfter as e:
                    logger.warning(f"⚠️ Превышен лимит отправки. Ждем {e.retry_after} секунд...")
                    await asyncio.sleep(e.retry_after)
                except Exception as e:
                    logger.error(f"❌ Неожиданная ошибка при отправке: {e}")
                    await asyncio.sleep(5)
                    break

        # Отправляем финальное сообщение
        footer = "✅ Отчет по экологическим законопроектам завершен."
        await bot.send_message(chat_id=CHANNEL_ID, text=footer)

        # Очищаем базу после успешной отправки
        clear_db()
        logger.info("✅ Все данные успешно отправлены и база очищена")

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке в канал: {e}")
        logger.exception("Подробности ошибки:")


@dp.message(Command("all"))
async def cmd_all(message: types.Message):
    """Обработчик команды /all"""
    draft_laws = get_all_draft_laws()

    if not draft_laws:
        await message.answer("⚡️ База данных пуста ⚡️")
        return

    await message.answer(f"⚡️ Все законопроекты в базе ({len(draft_laws)} шт.) ⚡️")

    for law in draft_laws:
        msg = (
            "=================\n"
            f"📌 ID: {law[0]}\n"
            f"📝 Название: {law[1]}\n"
            f"📊 Статус: {law[2]}\n"
            "================="
        )
        await message.answer(msg)
        await asyncio.sleep(0.5)


@dp.message(Command("parse"))
async def cmd_parse(message: types.Message):
    """Обработчик команды /parse - ручной запуск парсинга"""
    await message.answer("🔄 Запускаю парсинг экологических законопроектов...")

    # Запускаем парсинг
    await parse_website()

    # Получаем результаты
    draft_laws = get_all_draft_laws()

    if draft_laws:
        await message.answer(f"✅ Парсинг завершен. Найдено {len(draft_laws)} проектов.")
    else:
        await message.answer("⚠️ Парсинг завершен. Экологических проектов не найдено.")


@dp.message(Command("send"))
async def cmd_send(message: types.Message):
    """Обработчик команды /send - ручная отправка сообщений в канал"""
    await message.answer(f"📤 Запускаю отправку данных в канал {CHANNEL_ID}...")

    # Отправляем данные
    await send_to_channel()

    await message.answer("✅ Отправка завершена.")


async def periodic_sending():
    """Еженедельная отправка данных в канал по расписанию"""
    while True:
        try:
            # Проверяем текущий день недели и время
            current_day = datetime.now().weekday()
            current_hour = datetime.now().hour
            current_minute = datetime.now().minute

            # Если наступил нужный день недели и время
            if current_day == SEND_DAY_OF_WEEK and current_hour == SEND_HOUR and current_minute < 5:
                logger.info(
                    f"📆 {['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'][SEND_DAY_OF_WEEK]}, {SEND_HOUR}:00 - время отправки отчета!")

                # Сначала собираем данные за прошедший период
                await parse_website()

                # Затем отправляем собранные данные
                await send_to_channel()

                # Ждем 23 часа, чтобы не выполнять отправку повторно в этот же день
                logger.info("⏳ Отчет отправлен, следующая проверка через 23 часа")
                await asyncio.sleep(23 * 60 * 60)
            else:
                # Рассчитываем, сколько времени осталось до следующей отправки
                days_until_send_day = (SEND_DAY_OF_WEEK - current_day) % 7

                if days_until_send_day == 0 and current_hour >= SEND_HOUR:  # Если сегодня день отправки, но время уже прошло
                    days_until_send_day = 7

                hours_until_send = (24 * days_until_send_day) - current_hour + SEND_HOUR
                if days_until_send_day == 0:  # Если сегодня день отправки и время еще не наступило
                    hours_until_send = SEND_HOUR - current_hour

                logger.info(f"⏳ Следующий отчет будет отправлен через ~{hours_until_send} часов")

                # Проверяем время отправки с заданным интервалом
                await asyncio.sleep(CHECK_INTERVAL_HOURS * 60 * 60)

        except Exception as e:
            logger.error(f"❌ Ошибка в цикле отправки: {e}")
            await asyncio.sleep(ERROR_SLEEP_TIME)  # При ошибке ждем и пробуем снова


async def main():
    # Инициализация базы данных
    init_db()

    # Запуск фоновых задач
    asyncio.create_task(periodic_sending())

    # Запуск бота
    logger.info("🚀 Бот запущен и готов к работе")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())