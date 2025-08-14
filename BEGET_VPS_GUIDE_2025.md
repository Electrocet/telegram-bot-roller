# 🚀 Подробная инструкция: Размещение Telegram бота на Beget VPS (2025)

## 📋 Что вам потребуется:
- Аккаунт на Beget (у вас уже есть)
- Файлы бота (уже готовы)
- 15-30 минут времени
- 210₽/месяц за VPS

## 🔧 Шаг 1: Заказ VPS на Beget

### 1.1 Вход в панель управления
1. Перейдите на https://beget.com
2. Нажмите "Вход" (правый верхний угол)
3. Введите логин и пароль от вашего аккаунта

### 1.2 Заказ VPS
1. В панели управления найдите раздел **"VPS/VDS"** или **"Серверы"**
   - Может быть в главном меню или в разделе "Услуги"
2. Нажмите **"Заказать VPS"** или **"Создать сервер"**
3. Выберите конфигурацию:
   - **Тариф:** "Старт" или минимальный (1 CPU, 1GB RAM, 10GB SSD)
   - **Операционная система:** Ubuntu 22.04 LTS или Ubuntu 24.04 LTS
   - **Период:** 1 месяц (для начала)
4. **Важно:** Запишите данные для входа (логин, пароль, IP адрес)
5. Нажмите **"Оплатить"** и дождитесь создания сервера (5-15 минут)

## 🔧 Шаг 2: Подключение к серверу

### 2.1 Получение данных для подключения
После создания VPS вы получите:
- **IP адрес сервера** (например: 185.123.45.67)
- **Логин:** root
- **Пароль:** (высылается на email или в панели)

### 2.2 Подключение через SSH
**Для Windows:**
1. Скачайте **PuTTY** с https://putty.org
2. Запустите PuTTY
3. В поле "Host Name" введите IP адрес сервера
4. Port: 22
5. Connection type: SSH
6. Нажмите "Open"
7. Login as: **root**
8. Password: **ваш пароль**

**Для Windows 10/11 (встроенный SSH):**
1. Нажмите Win+R, введите **cmd**
2. В командной строке введите:
```bash
ssh root@185.123.45.67
```
(замените на ваш IP)
3. Введите пароль

## 🔧 Шаг 3: Настройка сервера

### 3.1 Обновление системы
Выполните команды по порядку:
```bash
apt update && apt upgrade -y
```

### 3.2 Установка Python и необходимых пакетов
```bash
apt install python3 python3-pip python3-venv git nano htop -y
```

### 3.3 Создание пользователя для бота (для безопасности)
```bash
adduser botuser
usermod -aG sudo botuser
su - botuser
```

### 3.4 Создание рабочей директории
```bash
mkdir telegram-bot
cd telegram-bot
```

## 🔧 Шаг 4: Загрузка файлов бота

### Вариант 1: Через GitHub (рекомендуется)

#### 4.1 Создание репозитория на GitHub
1. Перейдите на https://github.com
2. Зарегистрируйтесь или войдите в аккаунт
3. Нажмите **"New repository"**
4. Repository name: **telegram-roller-bot**
5. Поставьте галочку **"Add a README file"**
6. Нажмите **"Create repository"**

#### 4.2 Загрузка файлов
1. На странице репозитория нажмите **"uploading an existing file"**
2. Перетащите все файлы из папки "Бот для телеграм":
   - bot.py
   - bad_words.txt
   - requirements.txt (если нет - создайте)
3. Commit message: "Initial bot files"
4. Нажмите **"Commit changes"**

#### 4.3 Клонирование на сервер
```bash
git clone https://github.com/ВАШ_ЛОГИН/telegram-roller-bot.git
cd telegram-roller-bot
```

### Вариант 2: Через SFTP (FileZilla)
1. Скачайте FileZilla с https://filezilla-project.org
2. Подключитесь к серверу:
   - Host: ваш IP адрес
   - Username: botuser
   - Password: пароль от botuser
   - Port: 22
3. Загрузите все файлы в папку `/home/botuser/telegram-bot`

## 🔧 Шаг 5: Создание файла requirements.txt

Если файла нет, создайте его:
```bash
nano requirements.txt
```

Содержимое файла:
```
python-telegram-bot[job-queue]==20.7
requests==2.31.0
```

Сохранение в nano: Ctrl+X, Y, Enter

## 🔧 Шаг 6: Настройка окружения

### 6.1 Создание виртуального окружения
```bash
python3 -m venv bot_env
source bot_env/bin/activate
```

### 6.2 Установка зависимостей
```bash
pip install -r requirements.txt
```

### 6.3 Создание файла с переменными окружения
```bash
nano .env
```

Содержимое:
```
TELEGRAM_TOKEN=7638087297:AAGa2ZPRJDOq_Tvvx_hNwNiFGPm1Btr_bPI
GROUP_CHAT_ID=-1002448216356
WEATHER_API_KEY=7b8b7d0c3b8b8b5e4bb8d5dd8f58e7dd
CITY=Lipetsk
```

## 🔧 Шаг 7: Обновление кода бота для переменных окружения

Отредактируйте bot.py:
```bash
nano bot.py
```

Найдите строки с константами и замените на:
```python
import os
from dotenv import load_dotenv

load_dotenv()

# Константы из переменных окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID"))
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
CITY = os.getenv("CITY", "Lipetsk")
```

Установите python-dotenv:
```bash
pip install python-dotenv
```

## 🔧 Шаг 8: Тестовый запуск

### 8.1 Проверка работы
```bash
python3 bot.py
```

Если появились сообщения о запуске - отлично! Остановите Ctrl+C.

### 8.2 Если есть ошибки
- Проверьте правильность токена
- Убедитесь что все библиотеки установлены
- Проверьте права доступа к файлам

## 🔧 Шаг 9: Настройка автозапуска (systemd)

### 9.1 Создание сервисного файла
```bash
sudo nano /etc/systemd/system/telegram-bot.service
```

Содержимое файла:
```ini
[Unit]
Description=Telegram Roller Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/telegram-bot/telegram-roller-bot
Environment=PATH=/home/botuser/telegram-bot/telegram-roller-bot/bot_env/bin
ExecStart=/home/botuser/telegram-bot/telegram-roller-bot/bot_env/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 9.2 Включение и запуск сервиса
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
```

### 9.3 Проверка статуса
```bash
sudo systemctl status telegram-bot
```

## 🔧 Шаг 10: Мониторинг и управление

### 10.1 Просмотр логов
```bash
sudo journalctl -u telegram-bot -f
```

### 10.2 Перезапуск бота
```bash
sudo systemctl restart telegram-bot
```

### 10.3 Остановка бота
```bash
sudo systemctl stop telegram-bot
```

## ✅ Проверка работы

1. **Отправьте команду `/help` боту в Telegram**
2. **Проверьте логи:** `sudo journalctl -u telegram-bot -f`
3. **Попробуйте команды:** `/start_poll`, `/activity_stats`

## 🔧 Обновление бота

### Через GitHub:
```bash
cd /home/botuser/telegram-bot/telegram-roller-bot
git pull origin main
sudo systemctl restart telegram-bot
```

### Ручное редактирование:
```bash
nano bot.py
sudo systemctl restart telegram-bot
```

## 🚨 Важные моменты безопасности

### 1. Смена пароля root
```bash
passwd root
```

### 2. Настройка файрвола
```bash
ufw enable
ufw allow ssh
ufw allow 80
ufw allow 443
```

### 3. Обновления безопасности
```bash
apt update && apt upgrade -y
```
(Выполняйте раз в неделю)

## 📞 Если что-то не работает

### Проверьте:
1. **Статус сервиса:** `sudo systemctl status telegram-bot`
2. **Логи:** `sudo journalctl -u telegram-bot -f`
3. **Права на файлы:** `ls -la`
4. **Переменные окружения:** `cat .env`

### Частые ошибки:
- **"Permission denied"** → Проверьте права: `chmod +x bot.py`
- **"Module not found"** → Переустановите: `pip install -r requirements.txt`
- **"Token invalid"** → Проверьте токен в .env файле

## 💰 Стоимость

- **VPS Beget "Старт":** 210₽/месяц
- **Дополнительные расходы:** 0₽
- **Итого:** 210₽/месяц за постоянно работающего бота

## 🎯 Преимущества этого решения

✅ **Ваш привычный провайдер** (Beget)  
✅ **Не влияет на сайты** (отдельный сервер)  
✅ **Полный контроль** над ботом  
✅ **Русскоязычная поддержка**  
✅ **Автоматический перезапуск** при сбоях  
✅ **Простое обновление** кода  

## 📱 Связь с поддержкой

Если возникли проблемы:
1. **Техподдержка Beget:** онлайн-чат в панели управления
2. **Документация:** https://beget.com/kb/vps
3. **Сообщество:** форумы Beget

---

**Ваш бот будет работать 24/7 на надежном сервере Beget! 🚀**
