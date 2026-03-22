# 🤖 Gemini Chat Summarizer Bot (v2.0)

Telegram-бот на базе **Google Gemini 2.0 Flash**, предназначенный для умного анализа переписки в группах. Он не просто копирует текст, а понимает контекст, выделяет главное и умеет иронично "прожаривать" участников по их реальным именам.

---

### **✨ Что нового в v2.0**
*   **Тайм-фреймы:** Саммари за последние `30m`, `5h` или `2d`.
*   **Идентификация:** Корректная работа с пользователями по `user_id` (даже если они меняют ники).
*   **Персонализация:** Режим шутки (`j`) теперь привязывается к именам и фамилиям участников.
*   **Лидерборд:** Автоматическое определение самого активного "болтуна" в выборке.
*   **Изоляция чатов:** Бот разделяет историю разных групп и не смешивает их.

---

### **📊 Команды и использование**

Команда `/summary` стала максимально гибкой. Аргументы можно комбинировать в любом порядке.

| Команда | Что произойдет |
| :--- | :--- |
| `/summary` | Краткая суть последних 20 сообщений. |
| `/summary 100` | Анализ последних 100 сообщений. |
| `/summary 1h` | Саммари обсуждения за последний час (доступны `m`, `h`, `d`). |
| `/summary j 30m` | Ироничный пересказ событий за последние 30 минут с упоминанием имен. |
| `/summary @username` | Выборка только по конкретному пользователю. |

---

### **🛠 Установка и развертывание**

#### **1. Требования**
* **Python 3.9+**
* **Gemini API Key** (взять в [Google AI Studio](https://aistudio.google.com/))
* **Telegram Bot Token** (взять у [@BotFather](https://t.me/botfather))

---

#### **2. Быстрый старт на VPS**

# Клонируем и настраиваем окружение
```bash
mkdir smart_bot && cd smart_bot
python3 -m venv venv
source venv/bin/activate
```
# Устанавливаем зависимости
```bash
pip install python-telegram-bot google-generativeai python-dotenv
```
---

#### **3. Настройка переменных**

Создайте файл .env в корне проекта:
```ini
TELEGRAM_TOKEN=ваш_токен_от_botfather
GEMINI_API_KEY=ваш_ключ_от_google
```
___

#### ⚙️ Настройка Systemd (Автозапуск 24/7)

Создайте файл службы:
```bash
sudo nano /etc/systemd/system/smart_bot.service
```
```ini
[Unit]
Description=Gemini Chat Summarizer Bot
After=network.target

[Service]
WorkingDirectory=/home/USER/smart_bot
ExecStart=/home/USER/smart_bot/venv/bin/python3 /home/USER/smart_bot/bot.py
Restart=always
RestartSec=5
User=USER

[Install]
WantedBy=multi-user.target
```
Замените USER на имя вашего пользователя в системе.

Запустите службу:
```bash
sudo systemctl daemon-reload
sudo systemctl enable smart_bot
sudo systemctl start smart_bot
```
___
### 💾 Технические детали

#### База данных: JSON-файл chat_history.json (хранит последние 1000 сообщений для каждого чата).
#### Безопасность: Файл истории и .env должны быть добавлены в .gitignore.
#### Privacy: Для корректной работы в группах отключите Privacy Mode в настройках @BotFather и дайте боту права администратора.

---
