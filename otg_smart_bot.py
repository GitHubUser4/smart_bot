import logging
from collections import deque, defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# === НАСТРОЙКИ ===
TELEGRAM_TOKEN = "8774538532:AAE6DtVDHCLgx2UzIgrwrYasKKmbLk1c4Kk"
GEMINI_API_KEY = "AIzaSyBFeaiY0VdbuHAw1cixkl4AGFuA96dgIE0"

# Настройка логирования для отслеживания ошибок
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
# Используем быструю и легкую модель, отлично подходящую для текста
model = genai.GenerativeModel('gemini-2.5-flash') 

# Хранилище сообщений: chat_id -> очередь из последних 200 сообщений
# deque автоматически удаляет самые старые сообщения при превышении maxlen
chat_history = defaultdict(lambda: deque(maxlen=200))

async def store_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняет все входящие текстовые сообщения в память."""
    if not update.message or not update.message.text:
        return
    
    chat_id = update.message.chat_id
    user = update.message.from_user.first_name or update.message.from_user.username
    text = update.message.text
    
    # Сохраняем в формате "Имя: текст сообщения"
    chat_history[chat_id].append(f"{user}: {text}")

async def summarize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /summary [n]. Собирает последние n сообщений и отправляет в Gemini."""
    chat_id = update.message.chat_id
    
    # Проверяем, передал ли пользователь количество сообщений (по умолчанию 20)
    n = 20
    if context.args and context.args[0].isdigit():
        n = int(context.args[0])
        # Ограничим максимальный запрос, чтобы не упереться в лимиты памяти/токенов
        n = min(n, 200) 

    history = chat_history[chat_id]
    
    if not history:
        await update.message.reply_text("Я пока не видел ни одного сообщения в этом чате.")
        return

    # Берем последние n сообщений
    messages_to_summarize = list(history)[-n:]
    chat_text = "\n".join(messages_to_summarize)
    
    # Формируем промпт для нейросети
    prompt = (
        f"Сделай краткую, но информативную выжимку (суть) следующих {len(messages_to_summarize)} "
        "сообщений из чата. Выдели главные темы обсуждения, кто что предлагал и к чему пришли. "
        f"Вот сообщения:\n\n{chat_text}"
    )
    
    # Сообщаем пользователю, что начали думать
    await update.message.reply_text("Анализирую сообщения, подождите немного...")

    try:
        # Отправляем запрос в Gemini
        response = model.generate_content(prompt)
        await update.message.reply_text(f"**Саммари последних {len(messages_to_summarize)} сообщений:**\n\n{response.text}", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Ошибка Gemini API: {e}")
        await update.message.reply_text("Произошла ошибка при обращении к нейросети. Попробуйте позже.")

def main():
    """Запуск бота."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Обработчик команды /summary
    application.add_handler(CommandHandler("summary", summarize))
    
    # Обработчик всех текстовых сообщений (кроме команд), чтобы бот их запоминал
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, store_message))

    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()