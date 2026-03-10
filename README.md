# 🤖 Gemini Chat Summarizer Bot

Telegram-бот на базе **Google Gemini API**, предназначенный для автоматического анализа и суммаризации переписки в групповых чатах. Позволяет мгновенно получить суть обсуждения, выделить задачи или просто посмеяться над контекстом, не перечитывая сотни сообщений.

---

### **📋 Требования**

* **Python:** 3.9 или выше
* **Gemini API Key:** Получите в [Google AI Studio](https://aistudio.google.com/)
* **Telegram Bot Token:** Получите у [@BotFather](https://t.me/botfather)

---

### **🛠 Установка на VPS (Ubuntu/Debian)**

### **1. Подготовка системы**

Обновите пакеты и установите необходимые системные зависимости:

```bash
sudo apt update && sudo apt install python3-pip python3-venv -y
```

### **2. Клонирование и настройка**

Создайте директорию проекта и настройте виртуальное окружение:

```bash
mkdir smart_bot && cd smart_bot
python3 -m venv venv
source venv/bin/activate
pip install python-telegram-bot google-generativeai python-dotenv
```

### **3. Размещение файлов**

Поместите в папку /home/USER/smart_bot следующие компоненты:

bot.py — основной код бота.

.env — файл с настройками (содержимое: TELEGRAM_TOKEN=... и GEMINI_API_KEY=...).

chat_history.json — (создастся автоматически) файл для хранения истории сообщений.

---

### **⚙️ Автозапуск через Systemd**

Чтобы бот работал 24/7 и автоматически перезапускался при сбоях или перезагрузке сервера, настройте его как системную службу.

### **1. Создание файла службы**
```bash
sudo nano /etc/systemd/system/smart_bot.service
```

### **2. Конфигурация**

Вставьте следующее содержимое, заменив USER на ваше реальное имя пользователя в системе:
```ini
[Unit]
Description=Gemini Chat Summarizer Bot
After=network.target

[Service]
# Путь к папке с ботом
WorkingDirectory=/home/USER/smart_bot
# Путь к python внутри venv и путь к скрипту
ExecStart=/home/USER/smart_bot/venv/bin/python3 /home/USER/smart_bot/bot.py
Restart=always
RestartSec=5
User=USER

[Install]
WantedBy=multi-user.target
```

### **3. Активация службы**

Выполните команды по очереди для регистрации и запуска:
```bash
sudo systemctl daemon-reload
sudo systemctl enable smart_bot
sudo systemctl start smart_bot
```
### **📖 Использование и команды**

Аргументы команды /summary можно указывать в любом порядке.

| Действие | Команда |
| --- | --- |
| **Краткая суть** |	`/summary (последние 20 сообщений)` |
| **Выбор объема** |	`/summary 100 (последние 100 сообщений)` |
| **Шуточный стиль** |	`/summary j 50` |
| **Деловой стиль** |	`/summary w 30` |
| **По пользователю** |	`/summary @username 50` |

## ⚠️ **Решение проблем**

**Бот не видит сообщения:** Убедитесь, что бот назначен **Администратором** группы и у него есть доступ к сообщениям (отключен Privacy Mode в @BotFather).

**Ошибка API Gemini:** Проверьте правильность ключа в `.env` и лимиты в Google AI Studio.

**Бот не отвечает:** Проверьте статус службы через `sudo systemctl status smart_bot` и логи.

---
