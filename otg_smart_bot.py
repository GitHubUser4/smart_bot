import os
import logging
import json
from dotenv import load_dotenv
from collections import deque, defaultdict, Counter
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HISTORY_FILE = "chat_history.json"
MAX_HISTORY = 500 

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
    
    # 3. Собираем имя и фамилию
    first = user.first_name or ""
    last = user.last_name or ""
    full_name = f"{first} {last}".strip()
    
    # Если имени вообще нет (бывает редко), берем ник
    if not full_name:
        full_name = f"@{user.username}" if user.username else "Аноним"

    username_str = f"@{user.username.lower()}" if user.username else ""

    chat_history[chat_id].append({
        "user_id": user.id,  # Уникальный и вечный ID
        "author": full_name,
        "username": username_str,
        "text": update.message.text
    })

    save_history()

async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    args = context.args or []

    style = "normal"
    count = 20
    target_user = None

    for arg in args:
        if arg.lower() == 'j':
            style = 'j'
        elif arg.isdigit():
            count = int(arg)
        elif arg.startswith('@'):
            target_user = arg.lower()

    count = min(count, 300)
    history = chat_history[chat_id]
    
    if not history:
        await update.message.reply_text("Я пока не накопил сообщений для анализа.")
        return

    filtered_messages = []
    for msg in reversed(history):
        if target_user:
            # Ищем по сохраненному username или если кто-то упоминается по имени с @
            if msg.get("username") == target_user or msg.get("author", "").lower() == target_user[1:]:
                filtered_messages.append(msg)
        else:
            filtered_messages.append(msg)

        if len(filtered_messages) == count:
            break

    filtered_messages.reverse()

    if not filtered_messages:
        await update.message.reply_text("Не найдено сообщений по вашим критериям.")
        return

    chat_text = "\n".join([f"{m['author']}: {m['text']}" for m in filtered_messages])
    
    # 4. Вычисляем самого активного участника (если нет фильтра по юзеру)
    most_active_text = ""
    if not target_user and filtered_messages:
        # Группируем по ID (если есть) или по имени (для старых логов)
        authors = [m.get("user_id", m["author"]) for m in filtered_messages]

        # Чтобы в статистике красиво вывести имя, а не цифры ID:
        top_user_val = Counter(authors).most_common(1)[0][0]

        # Находим имя этого счастливчика для вывода в чат
        top_author_name = next(m["author"] for m in filtered_messages 
                               if m.get("user_id") == top_user_val or m["author"] == top_user_val)

        most_active_text = f"\n\n🏆 **Самый активный болтун:** {top_author_name}"

    limit_instruction = "ВАЖНО: Твой ответ ОБЯЗАТЕЛЬНО должен быть короче 4000 символов. Пиши максимально емко."

    # 1 и 2. Убрали 'w', разделили логику имен для 'j' и 'normal'
    if style == 'j':
        prompt = (f"{limit_instruction}\n\n"
                  f"Сделай смешной и ироничный пересказ последних {len(filtered_messages)} сообщений. "
                  f"ОБЯЗАТЕЛЬНО используй Имена и Фамилии авторов (как они указаны в логе), высмеивая конкретные реплики конкретных людей. Текст:\n\n{chat_text}")
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
            # Чистим текст от битой разметки, но оставляем значок кубка
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