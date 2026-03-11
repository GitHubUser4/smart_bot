import os
import logging
import json
from dotenv import load_dotenv # Добавляем импорт
from collections import deque, defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# Загружаем переменные из .env
load_dotenv()

# === НАСТРОЙКИ ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HISTORY_FILE = "chat_history.json"
MAX_HISTORY = 500 # Максимальное количество хранимых сообщений для каждого чата

# Проверка, что ключи загружены
if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Ошибка: Токены не найдены в файле .env!")
    
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash') 

# === ФАЙЛОВАЯ СИСТЕМА (Элегантное хранение) ===
def load_history():
    """Загружает историю из JSON файла при запуске."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                # Восстанавливаем deque (очереди) с ограничением maxlen
                return defaultdict(lambda: deque(maxlen=MAX_HISTORY),
                                   {int(k): deque(v, maxlen=MAX_HISTORY) for k, v in data.items()})
            except Exception as e:
                logging.error(f"Ошибка чтения истории: {e}")
    return defaultdict(lambda: deque(maxlen=MAX_HISTORY))

def save_history():
    """Сохраняет текущую историю в JSON файл."""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        # Преобразуем deque в обычные списки для сохранения
        data = {k: list(v) for k, v in chat_history.items()}
        json.dump(data, f, ensure_ascii=False, indent=2)

# Загружаем историю при старте
chat_history = load_history()

# === ОСНОВНАЯ ЛОГИКА ===
async def store_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняет текстовые сообщения и обновляет файл."""
    if not update.message or not update.message.text:
        return
        
    chat_id = update.message.chat_id
    username = update.message.from_user.username
    first_name = update.message.from_user.first_name
    
    # Формируем имя автора (приоритет юзернейму для удобного поиска)
    author = f"@{username}" if username else first_name

    # Сохраняем сообщение как словарь для удобной фильтрации
    chat_history[chat_id].append({
        "author": author,
        "text": update.message.text
    })
    
    # Сразу обновляем файл
    save_history()

async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Умная команда /summary [j/w] [n] [@username]"""
    limit_instruction = "ВАЖНО: Твой ответ ОБЯЗАТЕЛЬНО должен быть короче 4000 символов, чтобы уместиться в одно сообщение Telegram. Пиши максимально емко."
    chat_id = update.message.chat_id
    args = context.args or []

    # Настройки по умолчанию
    style = "normal"
    count = 20
    target_user = None

    # Разбираем аргументы (в любом порядке)
    for arg in args:
        if arg.lower() in ['j', 'w']:
            style = arg.lower()
        elif arg.isdigit():
            count = int(arg)
        elif arg.startswith('@'):
            target_user = arg

    # Ограничиваем запрос, чтобы не перегрузить API
    count = min(count, 300)

    history = chat_history[chat_id]
    if not history:
        await update.message.reply_text("Я пока не накопил сообщений для анализа.")
        return

    # Фильтруем сообщения (отматываем с конца)
    filtered_messages = []
    for msg in reversed(history):
        if target_user:
            # Ищем сообщения конкретного пользователя
            if msg["author"].lower() == target_user.lower():
                filtered_messages.append(msg)
        else:
            filtered_messages.append(msg)
            
        if len(filtered_messages) == count:
            break

    # Разворачиваем обратно в хронологическом порядке
    filtered_messages.reverse()

    if not filtered_messages:
        await update.message.reply_text("Не найдено сообщений по вашим критериям.")
        return

    # Формируем текст для нейросети
    chat_text = "\n".join([f"{m['author']}: {m['text']}" for m in filtered_messages])
    context_info = f"сообщений пользователя {target_user}" if target_user else "сообщений из чата"

    # Выбираем промпт на основе флага
    if style == 'w':
        prompt = (f"{limit_instruction}\n\n"
                  f"Сделай строгий деловой отчет на основе последних {len(filtered_messages)} сообщений. "
                  f"Выдели суть, принятые решения и задачи. Текст сообщений:\n\n{chat_text}")
    elif style == 'j':
        prompt = (f"{limit_instruction}\n\n"
                  f"Сделай смешной и ироничный пересказ последних {len(filtered_messages)} сообщений. "
                  f"Высмей ключевые моменты. Текст сообщений:\n\n{chat_text}")
    else:
        prompt = (f"{limit_instruction}\n\n"
                  f"Сделай краткую выжимку последних {len(filtered_messages)} сообщений. "
                  f"Только факты и самая суть. Текст сообщений:\n\n{chat_text}")

    message = await update.message.reply_text("⏳ Читаю переписку...")

    try:
        response = model.generate_content(prompt)
        res_text = response.text
        
        # Резервная проверка: если ИИ всё же превысил лимит, мягко обрезаем
        if len(res_text) > 4000:
            res_text = res_text[:3950] + "...\n\n*(отрезано из-за лимита длины)*"
        
        full_response = f"**Саммари ({len(filtered_messages)} сообщ.):**\n\n{res_text}"

        try:
            # Попытка №1: Красивая разметка
            await message.edit_text(full_response, parse_mode='Markdown')
        except Exception as parse_error:
            # Попытка №2: Если разметка битая, отправляем чистый текст
            logging.warning(f"Ошибка разметки Markdown: {parse_error}")
            await message.edit_text(full_response.replace('*', '').replace('_', ''), parse_mode=None)

    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        await message.edit_text("Не удалось обработать ответ от нейросети.")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("summary", cmd_summary))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, store_message)) 
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()