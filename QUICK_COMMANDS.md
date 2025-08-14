# 🚀 Быстрые команды для управления ботом на VPS

## 📋 Основные команды SSH

### Подключение к серверу:
```bash
ssh root@ВАШ_IP_АДРЕС
```

### Переход к пользователю бота:
```bash
su - botuser
cd telegram-bot/telegram-roller-bot
```

## 🔧 Управление ботом

### Просмотр статуса:
```bash
sudo systemctl status telegram-bot
```

### Перезапуск бота:
```bash
sudo systemctl restart telegram-bot
```

### Остановка бота:
```bash
sudo systemctl stop telegram-bot
```

### Запуск бота:
```bash
sudo systemctl start telegram-bot
```

### Просмотр логов (в реальном времени):
```bash
sudo journalctl -u telegram-bot -f
```

### Просмотр последних 50 строк логов:
```bash
sudo journalctl -u telegram-bot -n 50
```

## 📝 Редактирование файлов

### Редактирование кода бота:
```bash
nano bot.py
```

### Редактирование переменных окружения:
```bash
nano .env
```

### Редактирование списка плохих слов:
```bash
nano bad_words.txt
```

## 🔄 Обновление бота

### Через GitHub:
```bash
git pull origin main
sudo systemctl restart telegram-bot
```

### Просмотр изменений:
```bash
git status
git log --oneline -5
```

## 🛡️ Безопасность и обслуживание

### Обновление системы:
```bash
sudo apt update && sudo apt upgrade -y
```

### Просмотр использования ресурсов:
```bash
htop
```

### Просмотр места на диске:
```bash
df -h
```

### Просмотр сетевых соединений:
```bash
netstat -tlnp
```

## 💾 Резервное копирование

### Создание бэкапа базы данных:
```bash
cp bot_data.db bot_data_backup_$(date +%Y%m%d).db
```

### Создание архива всех файлов:
```bash
tar -czf bot_backup_$(date +%Y%m%d).tar.gz *.py *.txt *.db .env
```

## 🚨 Устранение проблем

### Если бот не запускается:
1. Проверьте логи: `sudo journalctl -u telegram-bot -n 20`
2. Проверьте файл .env: `cat .env`
3. Проверьте права: `ls -la`
4. Попробуйте запустить вручную: `python3 bot.py`

### Если нет соединения с Telegram:
1. Проверьте интернет: `ping 8.8.8.8`
2. Проверьте токен: `cat .env | grep TOKEN`
3. Проверьте файрвол: `ufw status`

### Если база данных заблокирована:
```bash
sudo systemctl stop telegram-bot
rm -f bot_data.db-lock
sudo systemctl start telegram-bot
```

## 📞 Полезные ссылки

- **Панель Beget:** https://cp.beget.com
- **Документация VPS:** https://beget.com/kb/vps
- **Техподдержка:** чат в панели управления

## 💡 Советы

1. **Всегда делайте бэкапы** перед изменениями
2. **Проверяйте логи** при проблемах
3. **Обновляйте систему** раз в неделю
4. **Мониторьте ресурсы** через htop
5. **Используйте screen/tmux** для длительных операций
