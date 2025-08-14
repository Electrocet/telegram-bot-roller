# Основной код бота

import logging
from telegram import Update, Poll
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PollAnswerHandler, MessageHandler, MessageReactionHandler, filters
import datetime
import requests
import asyncio
import sqlite3
import telegram  # Добавляем для telegram.error

# В начале: Импорт re для regex (опционально для лучшего матча)
import re
import os
import json

# Для работы с переменными окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv не установлен, используем системные переменные

# Перемещаем настройку логирования в начало, перед bad_words
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Затем bad_words
import os
bad_words_path = os.path.join(os.path.dirname(__file__), 'bad_words.txt')
try:
    with open(bad_words_path, 'r', encoding='utf-8') as f:
        BAD_WORDS = [word.strip().lower() for word in f.readlines() if word.strip() and not word.strip().startswith('#')]
    logger.info(f"Loaded {len(BAD_WORDS)} bad words from {bad_words_path}")
except FileNotFoundError:
    BAD_WORDS = []  # Placeholder, добавьте слова
    logger.warning(f"bad_words.txt not found at {bad_words_path}! Anti-mat disabled.")

# Исправляем и улучшаем check_for_bad_words
async def check_for_bad_words(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Проверяем только группы (не приваты), игнорируем ботов
    if update.effective_chat.type == 'private' or update.effective_user.is_bot:
        return
    
    # Отслеживаем активность пользователя (сообщения)
    if update.message and update.effective_user:
        update_user_activity(update.effective_user, 'message')
    
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.lower()
    logger.info(f"Checking message from {update.effective_user.username}: '{text[:50]}...'")
    
    # Проверяем каждое слово из списка
    found_bad_word = None
    for word in BAD_WORDS:
        if word.startswith('#') or len(word) < 2:  # Пропускаем комментарии и короткие
            continue
        # Ищем целые слова (с границами) или как подстроку для коротких матов
        if len(word) >= 4:
            pattern = r'\b' + re.escape(word) + r'\b'
        else:
            pattern = re.escape(word)
        
        if re.search(pattern, text, re.IGNORECASE):
            found_bad_word = word
            break
    
    if found_bad_word:
        logger.info(f"Found bad word '{found_bad_word}' in message from {update.effective_user.username}")
        try:
            # Проверяем права бота
            bot_member = await context.bot.get_chat_member(update.effective_chat.id, context.bot.id)
            if bot_member.status not in ['administrator'] or not bot_member.can_delete_messages:
                logger.error("Bot doesn't have rights to delete messages")
                await context.bot.send_message(update.effective_chat.id, "⚠️ Бот не может удалять сообщения. Сделайте его администратором с правом удаления!")
                return
            
            # Удаляем сообщение
            await update.message.delete()
            username = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
            await context.bot.send_message(update.effective_chat.id, f"{username} Ай-яй-яй, мат в нашем сообществе запрещён!")
            logger.info(f"Deleted message with bad word from {username}")
            
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
            # Если не можем удалить, хотя бы предупредим
            username = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
            await context.bot.send_message(update.effective_chat.id, f"{username} Пожалуйста, не используйте мат в нашем сообществе!")

# Настройка логирования
# Добавляем словарь для русских месяцев и дней недели
MONTHS = {
    1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая', 6: 'июня',
    7: 'июля', 8: 'августа', 9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
}
WEEKDAYS = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']

# Константы (теперь из переменных окружения для Heroku)
TOKEN = os.getenv("TELEGRAM_TOKEN", "7638087297:AAGa2ZPRJDOq_Tvvx_hNwNiFGPm1Btr_bPI")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-1002448216356"))
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "7b8b7d0c3b8b8b5e4bb8d5dd8f58e7dd")
CITY = os.getenv("CITY", "Lipetsk")  # Город для погоды
POLL_DURATION_DAYS = 2  # Сколько дней длится опрос
REMINDER_INTERVAL_HOURS = 24  # Напоминание каждые 24 часа

# В начале, после импортов, добавляем словарь для голосов
# Инициализация базы данных для хранения истории
# Инициализация БД: Используем абсолютный путь в папке с ботом
db_path = os.path.join(os.path.dirname(__file__), 'bot_data.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()
logger.info(f"Database initialized at: {db_path}")

c.execute('''CREATE TABLE IF NOT EXISTS events
             (date TEXT, participants INTEGER)''')

# В инициализации БД: Добавляем таблицу welcome с entities
c.execute('''CREATE TABLE IF NOT EXISTS welcome
             (id INTEGER PRIMARY KEY, text TEXT, photo_id TEXT, entities TEXT)''')

# Создаем таблицу для хранения информации о текущем опросе
c.execute('''CREATE TABLE IF NOT EXISTS current_poll
             (id INTEGER PRIMARY KEY, poll_id TEXT, message_id INTEGER, chat_id INTEGER, created_at TEXT)''')

# Создаем таблицу для отслеживания активности пользователей
c.execute('''CREATE TABLE IF NOT EXISTS user_activity
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER,
              username TEXT,
              first_name TEXT,
              last_name TEXT,
              last_message_date TEXT,
              last_reaction_date TEXT,
              last_poll_vote_date TEXT,
              message_count INTEGER DEFAULT 0,
              reaction_count INTEGER DEFAULT 0,
              poll_vote_count INTEGER DEFAULT 0,
              first_seen_date TEXT,
              last_updated TEXT,
              UNIQUE(user_id))''')

# Добавляем столбец entities если его нет (для существующих БД)
try:
    c.execute("ALTER TABLE welcome ADD COLUMN entities TEXT")
    logger.info("Added entities column to welcome table")
except sqlite3.OperationalError:
    # Столбец уже существует
    pass
if c.execute("SELECT COUNT(*) FROM welcome").fetchone()[0] == 0:
    default_text = "Добро пожаловать в группу роллеров, {username}! Здесь мы организуем покатушки. Голосуй в опросах за удобные даты!"
    c.execute("INSERT INTO welcome (text, photo_id, entities) VALUES (?, ?, ?)", (default_text, None, None))
    logger.info("Default welcome message created")
conn.commit()

# Перемещаем функции перед main
async def close_poll(context: ContextTypes.DEFAULT_TYPE) -> None:
    poll_id = context.bot_data.get('current_poll_id')
    chat_id = context.job.data['chat_id']
    if poll_id:
        logger.info(f"Closing poll {poll_id} in chat {chat_id}")
        await context.bot.stop_poll(chat_id, poll_id)
        logger.info("Опрос закрыт автоматически")
        await check_and_announce(context)  # Анализируем результаты

async def reminder_before_close(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.data['chat_id']
    await context.bot.send_message(chat_id, "Опрос закроется через час! Успейте проголосовать! @all")

async def start_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update else None
    chat_type = update.effective_chat.type if update else None
    target_chat_id = GROUP_CHAT_ID if chat_type == 'private' else update.effective_chat.id
    
    # Проверка админа
    if update:
        try:
            if chat_type == 'private':
                member = await context.bot.get_chat_member(GROUP_CHAT_ID, user_id)
            else:
                member = await context.bot.get_chat_member(target_chat_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("Только администраторы группы могут запускать опрос.")
                return
        except telegram.error.ChatMigrated as e:
            await update.message.reply_text(f"Группа мигрировала в supergroup. Новый ID: {e.migrate_to_chat_id}. Обновите GROUP_CHAT_ID в коде!")
            return
    
    today = datetime.date.today()
    weekday = today.weekday()  # 0=понедельник, 6=воскресенье
    
    # Находим ближайшую пятницу, субботу, воскресенье (на этой неделе)
    next_weekend = []
    for day_offset in [4, 5, 6]:  # Пятница=4, Сб=5, Вс=6
        days_to_add = (day_offset - weekday) % 7
        if days_to_add == 0: days_to_add = 7  # Если уже этот день, на следующей неделе - но только текущая, так что skip если прошло
        target_date = today + datetime.timedelta(days=days_to_add)
        if target_date <= today: continue  # Пропускаем прошедшие дни
        day_str = f"{target_date.day} {MONTHS[target_date.month]} ({WEEKDAYS[target_date.weekday()]})"
        next_weekend.append(day_str)
    
    if not next_weekend:
        await update.message.reply_text("На этой неделе нет доступных дней для опроса.")
        return
    
    question = "Какой из дней в эти выходные вам удобен для вечерних совместных покатушек? (Выберите все подходящие)"
    options = next_weekend + ["Никакие из этих"]  # Добавляем вариант для отказа
    
    # Расчёт open_period с логированием
    now = datetime.datetime.now()
    next_thursday = today + datetime.timedelta(days=(3 - weekday) % 7)
    thursday_end = datetime.datetime.combine(next_thursday, datetime.time(23, 59))
    open_period = max(int((thursday_end - now).total_seconds()), 600)  # Минимум 10 мин
    logger.info(f"Calculated open_period: {open_period} seconds until {thursday_end}")
    
    # В start_poll: После расчёта thursday_end, планируем job для закрытия
    seconds_to_close = max(int((thursday_end - now).total_seconds()), 600)  # Минимум 10 мин
    context.job_queue.run_once(close_poll, seconds_to_close, data={'chat_id': target_chat_id})

    # Send poll без open_period
    message = await context.bot.send_poll(
        chat_id=target_chat_id,
        question=question,
        options=options,
        is_anonymous=False,
        allows_multiple_answers=True,
        # Нет open_period
    )
    
    context.bot_data['current_poll_id'] = message.poll.id
    context.bot_data['poll_options'] = options  # Сохраняем опции
    context.bot_data['poll_votes'] = {idx: set() for idx in range(len(options))}  # Dict для голосов: {option_id: set(user_ids)}
    
    # Сохраняем в БД информацию о текущем опросе
    c.execute("DELETE FROM current_poll")  # Удаляем предыдущий опрос
    c.execute("INSERT INTO current_poll (poll_id, message_id, chat_id, created_at) VALUES (?, ?, ?, ?)",
              (message.poll.id, message.message_id, target_chat_id, datetime.datetime.now().isoformat()))
    conn.commit()
    
    logger.info("Опрос запущен")

    # Подтверждение в приват
    if chat_type == 'private':
        await update.message.reply_text("Опрос успешно запущен в группе!")

    # Планируем напоминание за 1 час до закрытия
    if seconds_to_close > 3600:
        context.job_queue.run_once(reminder_before_close, seconds_to_close - 3600, data={'chat_id': target_chat_id})

async def receive_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    answer = update.poll_answer
    
    # Отслеживаем активность пользователя (голосования)
    if answer.user:
        update_user_activity(answer.user, 'poll_vote')
    
    poll_id = context.bot_data.get('current_poll_id')
    if answer.poll_id == poll_id:
        user_id = answer.user.id
        votes = context.bot_data['poll_votes']
        # Снимаем предыдущие голоса пользователя (если изменил)
        for opt in votes:
            votes[opt].discard(user_id)
        # Добавляем новые
        for opt_id in answer.option_ids:
            votes[opt_id].add(user_id)

# Обработчик реакций на сообщения
async def handle_message_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message_reaction and update.message_reaction.user:
        user = update.message_reaction.user
        if not user.is_bot:
            # Отслеживаем активность пользователя (реакции)
            update_user_activity(user, 'reaction')
            logger.info(f"Reaction from {user.first_name} ({user.id})")

async def check_and_announce(context: ContextTypes.DEFAULT_TYPE) -> None:
    # Эта функция вызывается по таймеру после опроса
    poll_id = context.bot_data.get('current_poll_id')
    if not poll_id:
        return
    
    votes = context.bot_data['poll_votes']
    options = context.bot_data['poll_options']
    
    # Находим опцию с максимум голосами (игнорируем "Никакие")
    max_votes = -1
    selected_idx = -1
    for idx in range(len(options) - 1):  # Без последнего
        count = len(votes[idx])
        if count > max_votes:
            max_votes = count
            selected_idx = idx
    
    if selected_idx == -1 or max_votes == 0:
        await context.bot.send_message(context.job.data.get('chat_id', GROUP_CHAT_ID), "Никто не проголосовал или все выбрали 'Никакие'. Запускаю новый опрос.")
        await start_poll(None, context)
        return
    
    selected_date = options[selected_idx]
    
    # Проверка погоды (ежедневный прогноз)
    weather_ok = await check_weather(selected_date.split(' ')[0])  # Только дата YYYY-MM-DD
    
    if weather_ok:
        await context.bot.send_message(context.job.data.get('chat_id', GROUP_CHAT_ID), f"Решено! Покатаемся {selected_date}. Кто идёт? Реагируйте 👍")
        # Сохраняем в БД
        c.execute("INSERT INTO events VALUES (?, ?)", (selected_date, max_votes))
        conn.commit()
    else:
        await context.bot.send_message(context.job.data.get('chat_id', GROUP_CHAT_ID), f"На {selected_date} ожидается плохая погода. Запускаю новый опрос.")
        await start_poll(None, context)
        return
    
    # Очищаем данные
    if 'current_poll_id' in context.bot_data:
        del context.bot_data['current_poll_id']
    if 'poll_votes' in context.bot_data:
        del context.bot_data['poll_votes']
    if 'poll_options' in context.bot_data:
        del context.bot_data['poll_options']
    
    # Очищаем информацию о опросе из базы данных
    c.execute("DELETE FROM current_poll")
    conn.commit()
    
    # Планируем следующий цикл через неделю (job_queue для повторения)
    context.job_queue.run_once(lambda ctx: start_poll(None, ctx), 7 * 86400)

async def check_weather(date_str: str) -> bool:
    # Преобразуем дату в unix time (начало дня)
    date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
    unix_time = int(date.timestamp())
    
    # Используем forecast API для дня
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={CITY}&appid={WEATHER_API_KEY}&units=metric"
    response = requests.get(url)
    if response.status_code == 200:
        forecasts = response.json()['list']
        for forecast in forecasts:
            if forecast['dt'] >= unix_time and forecast['dt'] < unix_time + 86400:  # В пределах дня
                weather = forecast['weather'][0]['main']
                if weather not in ['Clear', 'Clouds']:  # Если хоть один плохой - false
                    return False
        return True
    return False  # По умолчанию false если ошибка

# Функция для обновления активности пользователя
def update_user_activity(user, activity_type='message', date=None):
    """
    Обновляет активность пользователя в базе данных
    activity_type: 'message', 'reaction', 'poll_vote'
    """
    if not date:
        date = datetime.datetime.now().isoformat()
    
    user_id = user.id
    username = user.username or ''
    first_name = user.first_name or ''
    last_name = user.last_name or ''
    
    try:
        # Проверяем, есть ли уже пользователь в базе
        existing = c.execute("SELECT * FROM user_activity WHERE user_id = ?", (user_id,)).fetchone()
        
        if existing:
            # Обновляем существующую запись
            update_fields = []
            params = []
            
            if activity_type == 'message':
                update_fields.extend(['last_message_date = ?', 'message_count = message_count + 1'])
                params.append(date)
            elif activity_type == 'reaction':
                update_fields.extend(['last_reaction_date = ?', 'reaction_count = reaction_count + 1'])
                params.append(date)
            elif activity_type == 'poll_vote':
                update_fields.extend(['last_poll_vote_date = ?', 'poll_vote_count = poll_vote_count + 1'])
                params.append(date)
            
            # Обновляем также общую информацию
            update_fields.extend(['username = ?', 'first_name = ?', 'last_name = ?', 'last_updated = ?'])
            params.extend([username, first_name, last_name, date])
            
            query = f"UPDATE user_activity SET {', '.join(update_fields)} WHERE user_id = ?"
            params.append(user_id)
            
            c.execute(query, params)
        else:
            # Создаем новую запись
            initial_data = {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'last_message_date': None,
                'last_reaction_date': None,
                'last_poll_vote_date': None,
                'message_count': 0,
                'reaction_count': 0,
                'poll_vote_count': 0,
                'first_seen_date': date,
                'last_updated': date
            }
            
            if activity_type == 'message':
                initial_data['last_message_date'] = date
                initial_data['message_count'] = 1
            elif activity_type == 'reaction':
                initial_data['last_reaction_date'] = date
                initial_data['reaction_count'] = 1
            elif activity_type == 'poll_vote':
                initial_data['last_poll_vote_date'] = date
                initial_data['poll_vote_count'] = 1
            
            c.execute('''INSERT INTO user_activity 
                         (user_id, username, first_name, last_name, last_message_date, last_reaction_date, 
                          last_poll_vote_date, message_count, reaction_count, poll_vote_count, first_seen_date, last_updated)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (initial_data['user_id'], initial_data['username'], initial_data['first_name'], 
                       initial_data['last_name'], initial_data['last_message_date'], initial_data['last_reaction_date'],
                       initial_data['last_poll_vote_date'], initial_data['message_count'], initial_data['reaction_count'],
                       initial_data['poll_vote_count'], initial_data['first_seen_date'], initial_data['last_updated']))
        
        conn.commit()
        logger.info(f"Updated {activity_type} activity for user {user_id} ({first_name})")
        
    except Exception as e:
        logger.error(f"Error updating user activity: {e}")

# Определение функции schedule_weekly_poll
def schedule_weekly_poll(application):
    now = datetime.datetime.now()
    days_to_monday = (0 - now.weekday()) % 7
    if days_to_monday == 0: days_to_monday = 7
    next_monday = now + datetime.timedelta(days=days_to_monday)
    next_monday = next_monday.replace(hour=9, minute=0, second=0)  # Утро понедельника
    seconds_to_next = (next_monday - now).total_seconds()
    application.job_queue.run_once(lambda ctx: start_poll(None, ctx), seconds_to_next, data={'chat_id': GROUP_CHAT_ID})
    # Повтор каждые 7 дней после первого запуска
    application.job_queue.run_repeating(lambda ctx: start_poll(None, ctx), interval=7*86400, first=seconds_to_next + 86400, data={'chat_id': GROUP_CHAT_ID})

def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start_poll", start_poll))
    application.add_handler(PollAnswerHandler(receive_poll_answer))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("cancel", cancel_poll))
    application.add_handler(CommandHandler("getchatid", get_chat_id))
    application.add_handler(CommandHandler("test_send", test_send))
    application.add_handler(CommandHandler("myid", my_id))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("set_welcome", set_welcome))
    application.add_handler(CommandHandler("get_welcome", get_welcome))
    application.add_handler(CommandHandler("inactive_users", inactive_users))
    application.add_handler(CommandHandler("activity_stats", activity_stats))
    application.add_handler(CommandHandler("scan_recent", scan_recent_messages))
    # Добавляем обработчик для фото с командой в caption
    application.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, handle_photo_command))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    application.add_handler(MessageReactionHandler(handle_message_reaction))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_for_bad_words))
    
    # Job для check_and_announce после опроса
    application.job_queue.run_once(check_and_announce, POLL_DURATION_DAYS * 86400, data={'chat_id': GROUP_CHAT_ID})
    
    # Напоминания во время опроса
    application.job_queue.run_repeating(reminder, interval=REMINDER_INTERVAL_HOURS * 3600, first=3600, data={'chat_id': GROUP_CHAT_ID})
    
    # Автоматический запуск по понедельникам (еженедельно)
    schedule_weekly_poll(application)

    application.run_polling()

async def reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    # Для отладки: Если job, используем сохранённый chat_id или фиксированный
    await context.bot.send_message(context.job.data.get('chat_id', GROUP_CHAT_ID), "Эй, роллеры! Не забудьте проголосовать в опросе! @all")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    target_chat_id = GROUP_CHAT_ID if chat_type == 'private' else update.effective_chat.id
    
    try:
        if chat_type == 'private':
            member = await context.bot.get_chat_member(GROUP_CHAT_ID, user_id)
        else:
            member = await context.bot.get_chat_member(target_chat_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("Только администраторы группы могут просматривать историю.")
            return
    except telegram.error.ChatMigrated as e:
        await update.message.reply_text(f"Группа мигрировала в supergroup. Новый ID: {e.migrate_to_chat_id}. Обновите GROUP_CHAT_ID в коде!")
        return
    c.execute("SELECT * FROM events ORDER BY date DESC LIMIT 5")
    rows = c.fetchall()
    if not rows:
        await update.message.reply_text("История покатушек пуста.")
        return
    msg = "Последние покатушки:\n"
    for row in rows:
        msg += f"{row[0]} - {row[1]} участников\n"
    await update.message.reply_text(msg)

async def cancel_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    target_chat_id = GROUP_CHAT_ID if chat_type == 'private' else update.effective_chat.id
    
    try:
        if chat_type == 'private':
            member = await context.bot.get_chat_member(GROUP_CHAT_ID, user_id)
        else:
            member = await context.bot.get_chat_member(target_chat_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("Только администраторы группы могут отменять опрос.")
            return
    except telegram.error.ChatMigrated as e:
        await update.message.reply_text(f"Группа мигрировала в supergroup. Новый ID: {e.migrate_to_chat_id}. Обновите GROUP_CHAT_ID в коде!")
        return
    
    poll_cancelled = False
    
    # Способ 1: Если есть сохранённые данные опроса
    if 'current_poll_id' in context.bot_data:
        poll_id = context.bot_data['current_poll_id']
        logger.info(f"Attempting to cancel poll {poll_id} in chat {target_chat_id}")
        
        try:
            await context.bot.stop_poll(target_chat_id, poll_id)
            logger.info("Poll cancelled successfully via bot_data")
            poll_cancelled = True
        except Exception as e:
            logger.error(f"Error stopping poll via bot_data: {e}")
    
    # Способ 2: Ищем активный опрос в базе данных
    if not poll_cancelled:
        try:
            logger.info("Searching for active poll in database...")
            poll_record = c.execute("SELECT poll_id, message_id, chat_id FROM current_poll ORDER BY id DESC LIMIT 1").fetchone()
            
            if poll_record:
                db_poll_id, db_message_id, db_chat_id = poll_record
                
                # Проверяем, что это тот же чат
                if db_chat_id == target_chat_id:
                    try:
                        await context.bot.stop_poll(target_chat_id, db_message_id)
                        logger.info(f"Found and cancelled poll {db_poll_id} via database")
                        poll_cancelled = True
                    except Exception as e:
                        logger.error(f"Error stopping poll {db_poll_id}: {e}")
                        
        except Exception as e:
            logger.error(f"Error searching database for polls: {e}")
    
    # Отменяем все запланированные задачи для опросов
    current_jobs = context.job_queue.jobs()
    for job in current_jobs:
        if job.callback in [close_poll, reminder_before_close]:
            job.schedule_removal()
            logger.info(f"Cancelled job: {job.callback.__name__}")
    
    # Очищаем данные опроса
    if 'current_poll_id' in context.bot_data:
        del context.bot_data['current_poll_id']
    if 'poll_votes' in context.bot_data:
        del context.bot_data['poll_votes']
    if 'poll_options' in context.bot_data:
        del context.bot_data['poll_options']
    
    # Очищаем информацию о опросе из базы данных
    c.execute("DELETE FROM current_poll")
    conn.commit()
    
    if poll_cancelled:
        await update.message.reply_text("Опрос отменён.")
    else:
        await update.message.reply_text("Активный опрос не найден. Возможно, он уже был закрыт или отменён ранее.")

async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"ID этого чата: {chat_id}")

async def test_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id, "Тестовое сообщение от бота. Если вы это видите, бот может отправлять сообщения в этот чат.")

async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Ваш user ID: {update.effective_user.id}")

# Обработчик для фото с командами в caption
async def handle_photo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    caption = update.message.caption or ""
    logger.info(f"Photo with caption received: '{caption}'")
    
    if caption.startswith('/set_welcome '):
        # Имитируем context.args для команды
        args = caption[13:].split() if len(caption) > 13 else []
        context.args = args
        await set_welcome(update, context)
    elif caption.startswith('/get_welcome'):
        await get_welcome(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    target_chat_id = GROUP_CHAT_ID if chat_type == 'private' else update.effective_chat.id
    
    try:
        if chat_type == 'private':
            member = await context.bot.get_chat_member(GROUP_CHAT_ID, user_id)
        else:
            member = await context.bot.get_chat_member(target_chat_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("Только администраторы могут использовать /help.")
            return
    except telegram.error.ChatMigrated as e:
        await update.message.reply_text(f"Группа мигрировала в supergroup. Новый ID: {e.migrate_to_chat_id}. Обновите GROUP_CHAT_ID в коде!")
        return
    
    help_text = (
        "🤖 *Меню команд для администраторов:*\n\n"
        "📊 /start\\_poll - Запустить опрос по выбору даты покатушек\n"
        "📈 /history - Просмотреть последние 5 событий\n"
        "❌ /cancel - Отменить текущий опрос\n\n"
        "👋 /set\\_welcome - Изменить приветствие для новых участников\n"
        "👀 /get\\_welcome - Посмотреть текущее приветствие\n\n"
        "📊 /inactive\\_users - Показать неактивных пользователей (6+ месяцев)\n"
        "📈 /activity\\_stats - Общая статистика активности\n"
        "🔍 /scan\\_recent - Сканировать участников группы (медленно)\n\n"
        "🆔 /getchatid - Получить ID чата\n"
        "🆔 /myid - Получить ваш user ID\n"
        "🧪 /test\\_send - Тестовое сообщение\n"
        "ℹ️ /help - Это меню\n\n"
        "_Команды можно отправлять как в группе, так и в личных сообщениях боту._\n\n"
        "💡 *Для изменения приветствия:*\n"
        "• Отправьте `/set\\_welcome новый текст`\n"
        "• Можно прикрепить фото с командой в подписи\n"
        "• Доступны плейсхолдеры: `{username}`, `{first_name}`, `{name}`"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# Команда для анализа неактивных пользователей
async def inactive_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    target_chat_id = GROUP_CHAT_ID if chat_type == 'private' else update.effective_chat.id
    
    try:
        if chat_type == 'private':
            member = await context.bot.get_chat_member(GROUP_CHAT_ID, user_id)
        else:
            member = await context.bot.get_chat_member(target_chat_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("Только администраторы могут просматривать статистику активности.")
            return
    except telegram.error.ChatMigrated as e:
        await update.message.reply_text(f"Группа мигрировала в supergroup. Новый ID: {e.migrate_to_chat_id}. Обновите GROUP_CHAT_ID в коде!")
        return
    
    # Получаем все записи пользователей
    six_months_ago = (datetime.datetime.now() - datetime.timedelta(days=180)).isoformat()
    
    # Запрос неактивных пользователей
    inactive_query = '''
        SELECT user_id, username, first_name, last_name, 
               last_message_date, last_reaction_date, last_poll_vote_date,
               message_count, reaction_count, poll_vote_count, first_seen_date
        FROM user_activity 
        WHERE (last_message_date IS NULL OR last_message_date < ?) 
          AND (last_reaction_date IS NULL OR last_reaction_date < ?)
          AND (last_poll_vote_date IS NULL OR last_poll_vote_date < ?)
          AND first_seen_date < ?
        ORDER BY first_seen_date ASC
    '''
    
    inactive_users_data = c.execute(inactive_query, (six_months_ago, six_months_ago, six_months_ago, six_months_ago)).fetchall()
    
    if not inactive_users_data:
        await update.message.reply_text("🎉 Все пользователи активны! Неактивных за последние 6 месяцев не найдено.")
        return
    
    # Формируем отчет
    report = "📊 **Неактивные пользователи (более 6 месяцев):**\n\n"
    
    for user_data in inactive_users_data[:20]:  # Ограничиваем 20 пользователями для первого сообщения
        user_id, username, first_name, last_name, last_msg, last_reaction, last_poll, msg_count, reaction_count, poll_count, first_seen = user_data
        
        # Формируем имя пользователя
        name_parts = []
        if first_name:
            name_parts.append(first_name)
        if last_name:
            name_parts.append(last_name)
        display_name = ' '.join(name_parts) if name_parts else f"ID:{user_id}"
        
        if username:
            display_name += f" (@{username})"
        
        # Находим последнюю активность
        last_activities = []
        if last_msg:
            last_activities.append(('сообщение', last_msg))
        if last_reaction:
            last_activities.append(('реакция', last_reaction))
        if last_poll:
            last_activities.append(('голосование', last_poll))
        
        if last_activities:
            # Берем самую последнюю активность
            last_activities.sort(key=lambda x: x[1], reverse=True)
            last_activity_type, last_activity_date = last_activities[0]
            last_activity_str = f"{last_activity_type}: {last_activity_date[:10]}"
        else:
            last_activity_str = "никогда"
        
        # Общая статистика
        total_activity = msg_count + reaction_count + poll_count
        
        report += f"• **{display_name}**\n"
        report += f"  Последняя активность: {last_activity_str}\n"
        report += f"  Всего действий: {total_activity} (сообщ: {msg_count}, реакц: {reaction_count}, голос: {poll_count})\n"
        report += f"  В группе с: {first_seen[:10]}\n\n"
    
    if len(inactive_users_data) > 20:
        report += f"... и ещё {len(inactive_users_data) - 20} пользователей.\n\n"
    
    report += f"**Всего неактивных: {len(inactive_users_data)} из {c.execute('SELECT COUNT(*) FROM user_activity').fetchone()[0]} отслеживаемых**"
    
    await update.message.reply_text(report, parse_mode='Markdown')

# Команда для общей статистики активности
async def activity_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    target_chat_id = GROUP_CHAT_ID if chat_type == 'private' else update.effective_chat.id
    
    try:
        if chat_type == 'private':
            member = await context.bot.get_chat_member(GROUP_CHAT_ID, user_id)
        else:
            member = await context.bot.get_chat_member(target_chat_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("Только администраторы могут просматривать статистику активности.")
            return
    except telegram.error.ChatMigrated as e:
        await update.message.reply_text(f"Группа мигрировала в supergroup. Новый ID: {e.migrate_to_chat_id}. Обновите GROUP_CHAT_ID в коде!")
        return
    
    try:
        # Общая статистика
        total_users = c.execute("SELECT COUNT(*) FROM user_activity").fetchone()[0]
        
        if total_users == 0:
            await update.message.reply_text("📊 База данных активности пустая.\nИспользуйте /scan_recent для начального сканирования.")
            return
        
        # Статистика по периодам
        now = datetime.datetime.now()
        
        # За последний месяц
        month_ago = (now - datetime.timedelta(days=30)).isoformat()
        active_month = c.execute("""
            SELECT COUNT(*) FROM user_activity 
            WHERE last_message_date > ? OR last_reaction_date > ? OR last_poll_vote_date > ?
        """, (month_ago, month_ago, month_ago)).fetchone()[0]
        
        # За последние 3 месяца  
        three_months_ago = (now - datetime.timedelta(days=90)).isoformat()
        active_3months = c.execute("""
            SELECT COUNT(*) FROM user_activity 
            WHERE last_message_date > ? OR last_reaction_date > ? OR last_poll_vote_date > ?
        """, (three_months_ago, three_months_ago, three_months_ago)).fetchone()[0]
        
        # За последние 6 месяцев
        six_months_ago = (now - datetime.timedelta(days=180)).isoformat()
        active_6months = c.execute("""
            SELECT COUNT(*) FROM user_activity 
            WHERE last_message_date > ? OR last_reaction_date > ? OR last_poll_vote_date > ?
        """, (six_months_ago, six_months_ago, six_months_ago)).fetchone()[0]
        
        # Неактивные более 6 месяцев
        inactive_6months = total_users - active_6months
        
        # Топ-5 самых активных пользователей
        top_active = c.execute("""
            SELECT first_name, username, 
                   (message_count + reaction_count + poll_vote_count) as total_activity
            FROM user_activity 
            WHERE total_activity > 0
            ORDER BY total_activity DESC 
            LIMIT 5
        """).fetchall()
        
        # Общая статистика активности
        total_stats = c.execute("""
            SELECT SUM(message_count), SUM(reaction_count), SUM(poll_vote_count)
            FROM user_activity
        """).fetchone()
        
        total_messages, total_reactions, total_polls = total_stats or (0, 0, 0)
        
        # Формируем отчет
        report = "📊 **Статистика активности группы**\n\n"
        
        report += f"👥 **Всего отслеживаемых пользователей:** {total_users}\n\n"
        
        report += "⏰ **Активность по периодам:**\n"
        report += f"• За последний месяц: {active_month} ({active_month/total_users*100:.1f}%)\n"
        report += f"• За последние 3 месяца: {active_3months} ({active_3months/total_users*100:.1f}%)\n"
        report += f"• За последние 6 месяцев: {active_6months} ({active_6months/total_users*100:.1f}%)\n"
        report += f"• Неактивные 6+ месяцев: {inactive_6months} ({inactive_6months/total_users*100:.1f}%)\n\n"
        
        report += "📈 **Общая активность:**\n"
        report += f"• Сообщений: {total_messages or 0}\n"
        report += f"• Реакций: {total_reactions or 0}\n"
        report += f"• Голосований: {total_polls or 0}\n\n"
        
        if top_active:
            report += "🏆 **Топ-5 самых активных:**\n"
            for i, (first_name, username, activity) in enumerate(top_active, 1):
                name = first_name or f"Пользователь"
                if username:
                    name += f" (@{username})"
                report += f"{i}. {name} - {activity} действий\n"
        
        await update.message.reply_text(report, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error generating activity stats: {e}")
        await update.message.reply_text(f"❌ Ошибка при формировании статистики: {e}")

# Команда для сканирования последних сообщений (тестирование)
async def scan_recent_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    target_chat_id = GROUP_CHAT_ID if chat_type == 'private' else update.effective_chat.id
    
    try:
        if chat_type == 'private':
            member = await context.bot.get_chat_member(GROUP_CHAT_ID, user_id)
        else:
            member = await context.bot.get_chat_member(target_chat_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("Только администраторы могут запускать сканирование.")
            return
    except telegram.error.ChatMigrated as e:
        await update.message.reply_text(f"Группа мигрировала в supergroup. Новый ID: {e.migrate_to_chat_id}. Обновите GROUP_CHAT_ID в коде!")
        return
    
    await update.message.reply_text("🔍 Начинаю сканирование участников группы...")
    
    try:
        # Альтернативный метод: получаем участников группы напрямую
        processed_count = 0
        members_processed = 0
        
        # Получаем список администраторов (они точно активны)
        try:
            admins = await context.bot.get_chat_administrators(target_chat_id)
            for admin in admins:
                if not admin.user.is_bot:
                    # Добавляем админов как активных пользователей
                    current_time = datetime.datetime.now().isoformat()
                    update_user_activity(admin.user, 'message', current_time)
                    members_processed += 1
                    
            logger.info(f"Processed {members_processed} administrators")
            
            # Добавляем задержку
            await asyncio.sleep(1)
            
        except Exception as admin_error:
            logger.error(f"Error getting administrators: {admin_error}")
        
        # Пытаемся получить информацию о текущем пользователе (кто запросил)
        try:
            current_time = datetime.datetime.now().isoformat()
            update_user_activity(update.effective_user, 'message', current_time)
            processed_count += 1
        except Exception as user_error:
            logger.error(f"Error processing current user: {user_error}")
        
        # Получаем участников через get_chat_member для известных ID (из существующих записей)
        try:
            existing_users = c.execute("SELECT DISTINCT user_id FROM user_activity").fetchall()
            
            for (existing_user_id,) in existing_users[:20]:  # Ограничиваем для избежания rate limit
                try:
                    member_info = await context.bot.get_chat_member(target_chat_id, existing_user_id)
                    if member_info.user and not member_info.user.is_bot:
                        # Обновляем информацию о пользователе (без изменения активности)
                        existing_record = c.execute("SELECT * FROM user_activity WHERE user_id = ?", (existing_user_id,)).fetchone()
                        if existing_record:
                            # Обновляем только профильную информацию
                            c.execute("""UPDATE user_activity 
                                        SET username = ?, first_name = ?, last_name = ?, last_updated = ?
                                        WHERE user_id = ?""", 
                                     (member_info.user.username or '', 
                                      member_info.user.first_name or '', 
                                      member_info.user.last_name or '',
                                      datetime.datetime.now().isoformat(),
                                      existing_user_id))
                            processed_count += 1
                    
                    # Добавляем небольшую задержку между запросами
                    await asyncio.sleep(0.1)
                    
                except telegram.error.BadRequest as br:
                    if "user not found" in str(br).lower():
                        # Пользователь покинул группу, отмечаем это
                        logger.info(f"User {existing_user_id} not found in group (left)")
                        continue
                    else:
                        logger.error(f"BadRequest for user {existing_user_id}: {br}")
                        continue
                except Exception as member_error:
                    logger.error(f"Error getting member {existing_user_id}: {member_error}")
                    continue
                    
        except Exception as members_error:
            logger.error(f"Error processing existing members: {members_error}")
        
        conn.commit()
        
        await update.message.reply_text(
            f"✅ Сканирование завершено!\n"
            f"• Обработано пользователей: {processed_count}\n"
            f"• Администраторов найдено: {members_processed}\n"
            f"• Теперь используйте /inactive_users для просмотра статистики."
        )
        
    except Exception as e:
        logger.error(f"Error scanning messages: {e}")
        await update.message.reply_text(
            f"❌ Ошибка при сканировании: {str(e)[:200]}...\n\n"
            "💡 Попробуйте:\n"
            "1. Подождать 1-2 минуты и повторить\n"
            "2. Использовать /inactive_users для текущей статистики"
        )

# Новый обработчик для new members с логированием
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"New member(s) joined chat {update.effective_chat.id}")
    for member in update.message.new_chat_members:
        if member.is_bot:
            logger.info(f"Skipping bot {member.username}")
            continue
        
        logger.info(f"Welcoming new member: {member.username or member.first_name}")
        # Проверяем, есть ли столбец entities
        try:
            c.execute("SELECT text, photo_id, entities FROM welcome")
        except sqlite3.OperationalError:
            # Если столбца entities нет, используем старый формат
            c.execute("SELECT text, photo_id, NULL FROM welcome")
        row = c.fetchone()
        if row:
            # Подготавливаем различные варианты имени
            username = member.username or member.first_name
            username_with_at = f"@{member.username}" if member.username else member.first_name
            first_name = member.first_name or "новый участник"
            
            # Обрабатываем entities перед заменой плейсхолдеров
            entities = None
            original_text = row[0]
            
            if row[2]:  # Если есть сохранённые entities
                import json
                try:
                    entities_data = json.loads(row[2])
                    from telegram import MessageEntity
                    
                    # Сначала заменяем плейсхолдеры, чтобы рассчитать смещение
                    text_before = original_text
                    text_after = text_before.format(
                        username=username_with_at,
                        first_name=first_name,
                        name=username_with_at
                    )
                    
                    # Рассчитываем смещение для каждого плейсхолдера
                    def calculate_offset_shift(text_before, text_after, original_offset):
                        # Находим все замены плейсхолдеров
                        import re
                        placeholders = ['{username}', '{first_name}', '{name}']
                        shift = 0
                        
                        for placeholder in placeholders:
                            while placeholder in text_before:
                                pos = text_before.find(placeholder)
                                if pos < original_offset:
                                    # Плейсхолдер находится перед нашей ссылкой
                                    if placeholder == '{username}' or placeholder == '{name}':
                                        replacement = username_with_at
                                    else:
                                        replacement = first_name
                                    shift += len(replacement) - len(placeholder)
                                    text_before = text_before.replace(placeholder, replacement, 1)
                                else:
                                    break
                        return shift
                    
                    # Корректируем offset для каждой entity
                    entities = []
                    for entity_data in entities_data:
                        offset_shift = calculate_offset_shift(original_text, text_after, entity_data['offset'])
                        new_entity = entity_data.copy()
                        new_entity['offset'] += offset_shift
                        entities.append(MessageEntity(**new_entity))
                        
                except Exception as e:
                    logger.error(f"Error processing entities: {e}")
                    entities = None
            
            # Заменяем плейсхолдеры в тексте
            text = original_text.format(
                username=username_with_at,
                first_name=first_name,
                name=username_with_at
            )
            logger.info(f"Sending welcome message to {username}")
            
            if row[1]:  # Если есть фото
                await context.bot.send_photo(update.effective_chat.id, photo=row[1], caption=text, caption_entities=entities)
            else:
                await context.bot.send_message(update.effective_chat.id, text, entities=entities)
        else:
            logger.error("No welcome message found in database")

# Команда /set_welcome
async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"set_welcome called by user {update.effective_user.username}")
    logger.info(f"Message type: photo={bool(update.message.photo)}, text={bool(update.message.text)}, caption={bool(update.message.caption)}")
    
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    target_chat_id = GROUP_CHAT_ID if chat_type == 'private' else update.effective_chat.id
    
    try:
        if chat_type == 'private':
            member = await context.bot.get_chat_member(GROUP_CHAT_ID, user_id)
        else:
            member = await context.bot.get_chat_member(target_chat_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("Только администраторы могут изменять приветствие.")
            return
    except telegram.error.ChatMigrated as e:
        await update.message.reply_text(f"Группа мигрировала. Новый ID: {e.migrate_to_chat_id}. Обновите GROUP_CHAT_ID!")
        return
    
    # Получаем текст из text или caption (для фото)
    command_text = update.message.text or update.message.caption or ""
    logger.info(f"Command text: '{command_text}'")
    logger.info(f"Context args: {context.args}")
    
    if context.args or (command_text and command_text.startswith('/set_welcome ')):
        # Получаем текст после команды, сохраняя переводы строк
        if command_text.startswith('/set_welcome '):
            new_text = command_text[13:]  # Убираем "/set_welcome "
        else:
            new_text = ' '.join(context.args)
        
        photo_id = update.message.photo[-1].file_id if update.message.photo else None
        
        # Сохраняем entities (ссылки) как JSON
        entities_json = None
        # Для фото entities находятся в caption_entities, для текста - в entities
        message_entities = update.message.caption_entities if update.message.photo else update.message.entities
        
        if message_entities:
            import json
            # Фильтруем entities, убираем bot_command
            filtered_entities = []
            for entity in message_entities:
                if entity.type != 'bot_command':
                    # Сдвигаем offset на длину команды
                    new_entity = {
                        'type': entity.type,
                        'offset': entity.offset - 13,  # Убираем "/set_welcome "
                        'length': entity.length
                    }
                    if entity.url:
                        new_entity['url'] = entity.url
                    if new_entity['offset'] >= 0:  # Только entities после команды
                        filtered_entities.append(new_entity)
            
            if filtered_entities:
                entities_json = json.dumps(filtered_entities)
        
        c.execute("UPDATE welcome SET text = ?, photo_id = ?, entities = ? WHERE id = 1", (new_text, photo_id, entities_json))
        conn.commit()
        logger.info(f"Welcome message updated. Photo: {'Yes' if photo_id else 'No'}, Entities: {'Yes' if entities_json else 'No'}")
        help_text = (
            "Приветствие обновлено!\n\n"
            "Доступные плейсхолдеры:\n"
            "{username} - имя с @ (если есть) или имя\n"
            "{first_name} - только имя пользователя\n"
            "{name} - то же что {username}\n\n"
            "Пример: {username}, добро пожаловать!"
        )
        await update.message.reply_text(help_text)
    else:
        help_text = (
            "Использование: /set_welcome [новый текст] (прикрепите фото если нужно)\n\n"
            "💡 ВАЖНО: Для многострочного текста просто напишите всё после /set_welcome:\n"
            "/set_welcome {username}, добро пожаловать!\n\n"
            "Здесь может быть несколько строк\n"
            "с переводами строк.\n\n"
            "Доступные плейсхолдеры:\n"
            "{username} - имя с @ (если есть) или имя\n"
            "{first_name} - только имя пользователя\n"
            "{name} - то же что {username}"
        )
        await update.message.reply_text(help_text)

# Команда /get_welcome
async def get_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Аналогичная проверка админа как в set_welcome
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    target_chat_id = GROUP_CHAT_ID if chat_type == 'private' else update.effective_chat.id
    
    try:
        if chat_type == 'private':
            member = await context.bot.get_chat_member(GROUP_CHAT_ID, user_id)
        else:
            member = await context.bot.get_chat_member(target_chat_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("Только администраторы могут просматривать приветствие.")
            return
    except telegram.error.ChatMigrated as e:
        await update.message.reply_text(f"Группа мигрировала. Новый ID: {e.migrate_to_chat_id}. Обновите GROUP_CHAT_ID!")
        return
    
    # Проверяем, есть ли столбец entities
    try:
        c.execute("SELECT text, photo_id, entities FROM welcome")
    except sqlite3.OperationalError:
        # Если столбца entities нет, используем старый формат
        c.execute("SELECT text, photo_id, NULL FROM welcome")
    row = c.fetchone()
    if row:
        text = row[0]
        
        # Восстанавливаем entities для preview (без замены плейсхолдеров)
        entities = None
        if row[2]:
            import json
            try:
                entities_data = json.loads(row[2])
                from telegram import MessageEntity
                entities = [MessageEntity(**entity) for entity in entities_data]
            except:
                entities = None
        
        if row[1]:
            await context.bot.send_photo(update.effective_chat.id, photo=row[1], caption=text, caption_entities=entities)
        else:
            await update.message.reply_text(text, entities=entities)
    else:
        await update.message.reply_text("Приветствие не задано.")

if __name__ == '__main__':
    main()
