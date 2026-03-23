import os
import logging
import json
import time
import re
from dotenv import load_dotenv
from collections import deque, defaultdict, Counter
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HISTORY_FILE = "chat_history.json"
MAX_HISTORY = 1000 

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Ошибка: Токены не найдены в файле .env!")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                return defaultdict(lambda: deque(maxlen=MAX_HISTORY),
                                   {int(k): deque(v, maxlen=MAX_HISTORY) for k, v in data.items()})
            except Exception as e:
                logging.error(f"Ошибка чтения истории: {e}")
    return defaultdict(lambda: deque(maxlen=MAX_HISTORY))

def save_history():
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        data = {k: list(v) for k, v in chat_history.items()}
        json.dump(data, f, ensure_ascii=False, indent=2)

chat_history = load_history()

async def store_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.message.chat_id
    user = update.message.from_user
    
    first = user.first_name or ""
    last = user.last_name or ""
    full_name = f"{first} {last}".strip()
    
    if not full_name:
        full_name = f"@{user.username}" if user.username else "Аноним"

    username_str = f"@{user.username.lower()}" if user.username else ""

    chat_history[chat_id].append({
        "user_id": user.id,
        "author": full_name,
        "username": username_str,
        "text": update.message.text,
        "timestamp": time.time() # Сохраняем текущее время
    })

    save_history()

async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    args = context.args or []

    style = "normal"
    count_limit = 20
    time_limit = None
    target_user = None

    # Парсим аргументы
    for arg in args:
        arg_lower = arg.lower()
        if arg_lower == 'j':
            style = 'j'
        elif re.match(r'^\d+[mhd]$', arg_lower):
            # Если формат 30m, 5h, 2d
            val = int(arg_lower[:-1])
            unit = arg_lower[-1]
            if unit == 'm': time_limit = val * 60
            elif unit == 'h': time_limit = val * 3600
            elif unit == 'd': time_limit = val * 86400
        elif arg.isdigit():
            count_limit = int(arg)
        elif arg.startswith('@'):
            target_user = arg_lower

    history = chat_history[chat_id]
    
    if not history:
        await update.message.reply_text("Я пока не накопил сообщений для анализа.")
        return

    filtered_messages = []
    current_time = time.time()

    for msg in reversed(history):
        # Фильтр по пользователю
        if target_user:
            if msg.get("username") != target_user and msg.get("author", "").lower() != target_user[1:]:
                continue

        # Фильтр по времени или количеству
        if time_limit:
            msg_time = msg.get("timestamp", 0)
            if current_time - msg_time <= time_limit:
                filtered_messages.append(msg)
            else:
                break # Дошли до сообщений старше указанного времени
        else:
            filtered_messages.append(msg)
            if len(filtered_messages) == count_limit:
                break

        # Жесткий лимит, чтобы не перегрузить API (даже если за 1 час написали 1000 сообщений)
        if len(filtered_messages) >= 500:
            break

    filtered_messages.reverse()

    if not filtered_messages:
        await update.message.reply_text("Не найдено сообщений по вашим критериям.")
        return

    chat_text = "\n".join([f"{m['author']}: {m['text']}" for m in filtered_messages])
    
    most_active_text = ""
    if not target_user and filtered_messages:
        authors = [m.get("user_id", m["author"]) for m in filtered_messages]
        top_user_val = Counter(authors).most_common(1)[0][0]
        
        top_author_name = next(m["author"] for m in filtered_messages 
                               if m.get("user_id") == top_user_val or m["author"] == top_user_val)
        
        most_active_text = f"\n\n🏆 **Самый активный болтун:** {top_author_name}"

    limit_instruction = "ВАЖНО: Твой ответ ОБЯЗАТЕЛЬНО должен быть короче 4000 символов. Пиши максимально емко."

    if style == 'j':
        prompt = (f"{limit_instruction}\n\n"
                  f"Сделай смешной и ироничный пересказ последних {len(filtered_messages)} сообщений. "
                  f"ОБЯЗАТЕЛЬНО используй Имена и Фамилии авторов (как они указаны в логе), высмеивая конкретные реплики конкретных людей, иронизируй. Текст:\n\n{chat_text}")
    else:
        prompt = (f"{limit_instruction}\n\n"
                  f"Сделай краткую выжимку последних {len(filtered_messages)} сообщений. "
                  f"Только факты и суть обсуждения. Привязываться к именам авторов не обязательно. Текст:\n\n{chat_text}")

    message = await update.message.reply_text("⏳ Читаю переписку...")

    try:
        response = model.generate_content(prompt)
        res_text = response.text
        
        if len(res_text) > 4000:
            res_text = res_text[:3950] + "...\n*(обрезано)*"
            
        full_response = f"**Саммари ({len(filtered_messages)} сообщ.):**\n\n{res_text}{most_active_text}"

        try:
            await message.edit_text(full_response, parse_mode='Markdown')
        except Exception as parse_error:
            logging.warning(f"Ошибка разметки Markdown: {parse_error}")
            clean_text = full_response.replace('*', '').replace('_', '')
            await message.edit_text(clean_text, parse_mode=None)

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