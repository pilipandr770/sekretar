# AI Secretary - Руководство по деплою

Это руководство описывает процесс деплоя AI Secretary на различные платформы, с основным фокусом на Render.com.

## Содержание

- [Деплой на Render.com](#деплой-на-rendercom)
- [Деплой на Heroku](#деплой-на-heroku)
- [Деплой на VPS](#деплой-на-vps)
- [Docker деплой](#docker-деплой)
- [Переменные окружения](#переменные-окружения)
- [Troubleshooting](#troubleshooting)

## Деплой на Render.com

Render.com - рекомендуемая платформа для деплоя AI Secretary благодаря простоте настройки и хорошей поддержке Python приложений.

### Предварительные требования

1. Аккаунт на [Render.com](https://render.com)
2. Репозиторий с кодом на GitHub/GitLab
3. Настроенная база данных PostgreSQL (можно создать на Render)

### Пошаговая инструкция

#### 1. Создание базы данных PostgreSQL

1. Войдите в панель управления Render
2. Нажмите **"New"** → **"PostgreSQL"**
3. Заполните параметры:
   - **Name**: `ai-secretary-db`
   - **Database**: `ai_secretary`
   - **User**: `ai_secretary_user`
   - **Region**: выберите ближайший регион
   - **PostgreSQL Version**: 15 (рекомендуется)
   - **Plan**: выберите подходящий план

4. Нажмите **"Create Database"**
5. Сохраните **Internal Database URL** - он понадобится для настройки приложения

#### 2. Создание Web Service

1. В панели управления Render нажмите **"New"** → **"Web Service"**
2. Подключите ваш GitHub/GitLab репозиторий
3. Заполните настройки:

**Основные настройки:**
- **Name**: `ai-secretary`
- **Region**: тот же регион, что и база данных
- **Branch**: `main` (или ваша основная ветка)
- **Root Directory**: оставьте пустым
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python start-prod.py`

**Дополнительные настройки:**
- **Plan**: выберите подходящий план (минимум Starter)
- **Auto-Deploy**: включите для автоматического деплоя при изменениях

#### 3. Настройка переменных окружения

В разделе **Environment** добавьте следующие переменные:

**Обязательные переменные:**

```bash
# Безопасность
SECRET_KEY=your-super-secret-key-at-least-32-characters-long
JWT_SECRET_KEY=your-jwt-secret-key-at-least-32-characters-long

# База данных (используйте Internal Database URL из шага 1)
DATABASE_URL=postgresql://ai_secretary_user:password@dpg-xxxxx-a.oregon-postgres.render.com/ai_secretary

# Приложение
FLASK_ENV=production
DEBUG=false
APP_NAME=AI Secretary
APP_URL=https://your-app-name.onrender.com
```

**Опциональные переменные (для полной функциональности):**

```bash
# OpenAI для ИИ функций
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4

# Stripe для платежей
STRIPE_SECRET_KEY=sk_live_your-stripe-secret-key
STRIPE_PUBLISHABLE_KEY=pk_live_your-stripe-publishable-key
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://your-app-name.onrender.com/api/v1/auth/google/callback

# Telegram интеграция
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_WEBHOOK_URL=https://your-app-name.onrender.com/api/v1/channels/telegram/webhook

# Redis (опционально, можно создать на Render)
REDIS_URL=redis://red-xxxxx:6379

# Email настройки
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Мониторинг
LOG_LEVEL=INFO
LOG_FORMAT=json
```

#### 4. Создание Redis (опционально)

Для кэширования и фоновых задач:

1. Нажмите **"New"** → **"Redis"**
2. Настройте:
   - **Name**: `ai-secretary-redis`
   - **Plan**: выберите подходящий план
   - **Region**: тот же регион
3. Добавьте **Redis URL** в переменные окружения приложения

#### 5. Деплой

1. Нажмите **"Create Web Service"**
2. Render автоматически начнет процесс деплоя
3. Следите за логами в разделе **"Logs"**
4. После успешного деплоя приложение будет доступно по URL

### Настройка домена (опционально)

1. В настройках Web Service перейдите в **"Settings"**
2. В разделе **"Custom Domains"** добавьте ваш домен
3. Настройте DNS записи согласно инструкциям Render
4. Обновите `APP_URL` в переменных окружения

## Деплой на Heroku

### Подготовка

1. Установите [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli)
2. Войдите в аккаунт: `heroku login`

### Создание приложения

```bash
# Создание приложения
heroku create ai-secretary-app

# Добавление PostgreSQL
heroku addons:create heroku-postgresql:mini

# Добавление Redis
heroku addons:create heroku-redis:mini

# Настройка переменных окружения
heroku config:set SECRET_KEY=your-secret-key
heroku config:set JWT_SECRET_KEY=your-jwt-secret-key
heroku config:set FLASK_ENV=production
heroku config:set DEBUG=false

# Деплой
git push heroku main
```

### Настройка Procfile

Создайте файл `Procfile` в корне проекта:

```
web: python start-prod.py
worker: celery -A celery_app.celery worker --loglevel=info
```

## Деплой на VPS

### Требования к серверу

- Ubuntu 20.04+ или CentOS 8+
- Python 3.8+
- PostgreSQL 12+
- Redis 6+
- Nginx
- Минимум 1GB RAM, 1 CPU

### Установка зависимостей

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Python и зависимостей
sudo apt install python3 python3-pip python3-venv postgresql postgresql-contrib redis-server nginx -y

# Установка Node.js (для фронтенда, если нужно)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs -y
```

### Настройка PostgreSQL

```bash
# Создание пользователя и базы данных
sudo -u postgres psql
CREATE USER ai_secretary WITH PASSWORD 'secure_password';
CREATE DATABASE ai_secretary OWNER ai_secretary;
GRANT ALL PRIVILEGES ON DATABASE ai_secretary TO ai_secretary;
\q
```

### Деплой приложения

```bash
# Клонирование репозитория
git clone https://github.com/your-username/ai-secretary.git
cd ai-secretary

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env файл

# Инициализация базы данных
python start-prod.py
```

### Настройка Nginx

Создайте файл `/etc/nginx/sites-available/ai-secretary`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /path/to/ai-secretary/app/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

Активируйте конфигурацию:

```bash
sudo ln -s /etc/nginx/sites-available/ai-secretary /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Настройка systemd service

Создайте файл `/etc/systemd/system/ai-secretary.service`:

```ini
[Unit]
Description=AI Secretary Web Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/ai-secretary
Environment=PATH=/path/to/ai-secretary/venv/bin
ExecStart=/path/to/ai-secretary/venv/bin/python start-prod.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Запустите сервис:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-secretary
sudo systemctl start ai-secretary
```

## Docker деплой

### Локальный Docker

```bash
# Сборка образа
docker build -t ai-secretary .

# Запуск с docker-compose
docker-compose up -d
```

### Продакшн Docker

```bash
# Сборка продакшн образа
docker build -f Dockerfile.prod -t ai-secretary:prod .

# Запуск продакшн стека
docker-compose -f docker-compose.prod.yml up -d
```

### Docker на VPS

```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Клонирование и запуск
git clone https://github.com/your-username/ai-secretary.git
cd ai-secretary
cp .env.example .env
# Отредактируйте .env
docker-compose -f docker-compose.prod.yml up -d
```

## Переменные окружения

### Критически важные

| Переменная | Описание | Пример |
|------------|----------|---------|
| `SECRET_KEY` | Секретный ключ Flask | `your-super-secret-key-32-chars` |
| `JWT_SECRET_KEY` | Ключ для JWT токенов | `your-jwt-secret-key-32-chars` |
| `DATABASE_URL` | URL базы данных | `postgresql://user:pass@host:5432/db` |

### Внешние сервисы

| Переменная | Описание | Обязательная |
|------------|----------|--------------|
| `OPENAI_API_KEY` | OpenAI API ключ | Нет |
| `STRIPE_SECRET_KEY` | Stripe секретный ключ | Нет |
| `GOOGLE_CLIENT_ID` | Google OAuth ID | Нет |
| `TELEGRAM_BOT_TOKEN` | Telegram бот токен | Нет |
| `REDIS_URL` | Redis URL | Нет |

### Настройки приложения

| Переменная | Значение по умолчанию | Описание |
|------------|----------------------|----------|
| `FLASK_ENV` | `production` | Окружение Flask |
| `DEBUG` | `false` | Режим отладки |
| `LOG_LEVEL` | `INFO` | Уровень логирования |
| `APP_URL` | - | URL приложения |

## Troubleshooting

### Частые проблемы

#### 1. Ошибка подключения к базе данных

**Симптомы:**
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) could not connect to server
```

**Решение:**
- Проверьте правильность `DATABASE_URL`
- Убедитесь, что база данных запущена и доступна
- Проверьте сетевые настройки и firewall

#### 2. Ошибки миграций

**Симптомы:**
```
alembic.util.exc.CommandError: Can't locate revision identified by 'xxxxx'
```

**Решение:**
```bash
# Сброс миграций (ОСТОРОЖНО: потеря данных!)
flask db stamp head
flask db migrate -m "Reset migrations"
flask db upgrade
```

#### 3. Проблемы с переменными окружения

**Симптомы:**
```
KeyError: 'SECRET_KEY'
```

**Решение:**
- Убедитесь, что все обязательные переменные установлены
- Проверьте синтаксис в `.env` файле
- Перезапустите приложение после изменения переменных

#### 4. Ошибки SSL/TLS

**Симптомы:**
```
ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Решение:**
- Обновите сертификаты: `pip install --upgrade certifi`
- Проверьте настройки прокси
- Используйте `PYTHONHTTPSVERIFY=0` только для тестирования

#### 5. Проблемы с памятью на Render

**Симптомы:**
- Приложение падает с ошибкой памяти
- Медленная работа

**Решение:**
- Увеличьте план на Render
- Оптимизируйте код и запросы к БД
- Используйте Redis для кэширования

### Мониторинг и логи

#### Render.com
- Логи доступны в разделе "Logs" панели управления
- Используйте `LOG_LEVEL=DEBUG` для детальных логов

#### Heroku
```bash
# Просмотр логов
heroku logs --tail

# Логи конкретного dyno
heroku logs --dyno web.1
```

#### VPS
```bash
# Логи systemd сервиса
sudo journalctl -u ai-secretary -f

# Логи Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Проверка здоровья приложения

После деплоя проверьте:

1. **Основная страница**: `https://your-app.com/`
2. **API здоровья**: `https://your-app.com/api/v1/health`
3. **API документация**: `https://your-app.com/api/v1/docs`

Пример ответа health check:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "services": {
    "database": "available",
    "redis": "available",
    "openai": "configured"
  }
}
```

### Получение помощи

Если проблема не решается:

1. Проверьте [Issues на GitHub](https://github.com/your-username/ai-secretary/issues)
2. Создайте новый Issue с подробным описанием проблемы
3. Включите логи и информацию об окружении
4. Укажите шаги для воспроизведения проблемы

### Полезные команды

```bash
# Проверка статуса всех сервисов
python -c "from app.utils.health_validator import HealthValidator; HealthValidator().validate_all_services()"

# Тест подключения к базе данных
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); print('DB OK' if db.engine.execute('SELECT 1').scalar() == 1 else 'DB Error')"

# Создание администратора
python -c "from app.cli.admin import create_admin_user; create_admin_user('admin@example.com', 'password123')"
```

## Безопасность в продакшене

### Обязательные меры безопасности

1. **Используйте HTTPS** - настройте SSL сертификаты
2. **Сильные пароли** - минимум 32 символа для секретных ключей
3. **Ограничьте доступ к БД** - используйте отдельного пользователя с минимальными правами
4. **Регулярные обновления** - обновляйте зависимости и систему
5. **Мониторинг** - настройте алерты на ошибки и необычную активность
6. **Бэкапы** - регулярно создавайте резервные копии данных

### Рекомендуемые настройки

```bash
# Продакшн переменные безопасности
FLASK_ENV=production
DEBUG=false
WTF_CSRF_ENABLED=true
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
PERMANENT_SESSION_LIFETIME=3600
```

Это руководство покрывает основные сценарии деплоя AI Secretary. Для специфических случаев обращайтесь к документации конкретной платформы или создавайте Issue в репозитории проекта.