
# Telegram-бот для заявок в АХО (Service Desk)

Простой бот для приема и обработки внутренних заявок сотрудников (мебель, электрика, уборка и т.д.).  
Стек: Python (aiogram 3.x) + асинхронная SQLite.

## Возможности

**Для сотрудников**
- Подача заявки за ~30 секунд: Категория → Срочность → Описание + Фото.
- Просмотр статуса своих заявок (Новая / В работе / Выполнено).
- Уведомления об изменении статуса заявки.

**Для администраторов (АХО)**
- Мгновенные уведомления о новых заявках.
- Поддержка нескольких администраторов.
- Панель “Активные заявки” (все невыполненные).
- Управление статусами в один клик (Взять в работу / Выполнить / Отклонить).
- Защита от спама и дублей (например, фотоальбомов).

## Локальный запуск

### Предварительные требования
- Python 3.10+
- Токен бота от [@BotFather](https://t.me/BotFather)

### Установка
### 1. Клонирование репозитория:
```bash
git clone https://github.com/hixday28/aho-bot.git
cd aho-bot
```

### 2. Виртуальное окружение:

**Windows**
```bat
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Установка зависимостей:
```bash
pip install -r requirements.txt
```

### 4. Настройка конфигурации:
```bash
cp .env.example .env
```

Откройте `.env` и заполните:
```ini
BOT_TOKEN=123466:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
# ID администраторов через запятую
ADMIN_IDS=123456789,987654321
```

### 5. Запуск бота:
```bash
python main.py
```

При первом запуске бот автоматически создаст базу данных `aho_requests.db`.

## Деплой на Linux (опционально)

Инструкция для запуска 24/7 на Ubuntu/Debian через systemd (службы `.service` управляются systemd и описываются unit-файлами).

### 1. Подготовка сервера
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3-pip python3-venv
```

### 2. Установка проекта
```bash
git clone https://github.com/hixday28/aho-bot.git
cd aho-bot
```

### 3. Окружение и конфиг
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

nano .env
```

### 4. Systemd unit (автозапуск)
Создайте файл службы:
```bash
sudo nano /etc/systemd/system/aho-bot.service
```

Вставьте конфигурацию (обязательно замените `User`, `WorkingDirectory`, `ExecStart` на свои значения; `WorkingDirectory` и `ExecStart` — стандартные директивы systemd для задания рабочей директории и команды запуска). [web:31][web:32]
```ini
[Unit]
Description=AHO Telegram Bot
After=network.target

[Service]
User=YOUR_LINUX_USER
Group=YOUR_LINUX_USER

WorkingDirectory=/home/YOUR_LINUX_USER/aho-bot
ExecStart=/home/YOUR_LINUX_USER/aho-bot/venv/bin/python main.py

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Примените изменения и запустите сервис (после правок unit-файлов обычно выполняют `systemctl daemon-reload`). [web:30]
```bash
sudo systemctl daemon-reload
sudo systemctl enable aho-bot
sudo systemctl start aho-bot
```

### Управление и логи
```bash
sudo systemctl status aho-bot
sudo systemctl restart aho-bot
sudo systemctl stop aho-bot
journalctl -u aho-bot -f
```
Режим “follow” для `journalctl` используется для просмотра логов в реальном времени. [web:44]

## Безопасность и структура проекта

- `.env` и `*.db` должны быть в `.gitignore`: токен бота нельзя публиковать в открытом доступе.
- Структура проекта:
```text
aho-bot/
├── main.py           # Точка входа, логика бота
├── db.py             # Работа с SQLite базой данных
├── requirements.txt  # Зависимости
├── .env              # Конфигурация (не коммитить)
├── .env.example      # Пример конфигурации
└── aho_requests.db   # База данных (создается автоматически)
```
