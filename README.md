# AI Secretary SaaS Platform

Омніканальна платформа з мультиагентним AI-секретарем для SMB, що включає Inbox, CRM, Календар, RAG-знання, інвойсинг через Stripe та KYB-моніторинг контрагентів.

## Особливості

- **Омніканальна комунікація**: Telegram Bot, Signal, Web Widget
- **Мультиагентна AI система**: Router, Supervisor та спеціалізовані агенти
- **CRM функціональність**: Ліди, пайплайн, задачі, нотатки
- **Інтеграція з календарем**: Google Calendar OAuth, бронювання слотів
- **RAG база знань**: Завантаження документів, пошук з цитатами
- **Stripe інтеграція**: Інвойсинг та підписки з 3-денним trial
- **KYB моніторинг**: VIES, санкції, неплатоспроможність, LEI
- **Multi-tenant архітектура**: Ізоляція даних та ролі користувачів
- **GDPR/DSGVO відповідність**: Мінімізація PII, аудит логи
- **Багатомовність**: Підтримка англійської, німецької та української мов

## Технології

- **Backend**: Flask, SQLAlchemy, PostgreSQL, Redis
- **Background Tasks**: Celery
- **AI**: OpenAI API
- **Payments**: Stripe
- **Authentication**: JWT
- **Real-time**: WebSocket (SocketIO)

## Швидкий старт

### Вимоги

- Python 3.11+
- PostgreSQL 13+
- Redis 6+
- Node.js 18+ (для frontend)

### Встановлення (Windows)

1. **Клонування репозиторію**:
```powershell
git clone <repository-url>
cd ai-secretary-saas
```

2. **Запуск скрипта налаштування**:
```powershell
.\scripts\setup.ps1
```

3. **Налаштування змінних середовища**:
```powershell
# Скопіюйте .env.example в .env та налаштуйте значення
copy .env.example .env
# Відредагуйте .env файл з вашими налаштуваннями
```

4. **Ініціалізація бази даних**:
```powershell
.\scripts\init-db.ps1
```

5. **Запуск додатку**:
```powershell
# Термінал 1: Основний сервер
.\scripts\run-dev.ps1

# Термінал 2: Celery worker
.\scripts\run-celery.ps1
```

### Налаштування зовнішніх сервісів

#### PostgreSQL
```sql
CREATE DATABASE ai_secretary;
CREATE DATABASE ai_secretary_test;
CREATE USER ai_secretary_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE ai_secretary TO ai_secretary_user;
GRANT ALL PRIVILEGES ON DATABASE ai_secretary_test TO ai_secretary_user;
```

#### Redis
Встановіть та запустіть Redis сервер на порту 6379.

#### OpenAI API
Отримайте API ключ з https://platform.openai.com/

#### Stripe
Налаштуйте Stripe акаунт та отримайте API ключі.

#### Google Calendar
Створіть OAuth 2.0 credentials в Google Cloud Console.

## Структура проекту

```
ai-secretary-saas/
├── app/                    # Основний код додатку
│   ├── api/               # API endpoints
│   ├── auth/              # Аутентифікація
│   ├── billing/           # Stripe інтеграція
│   ├── calendar/          # Google Calendar
│   ├── channels/          # Канали комунікації
│   ├── crm/               # CRM функціональність
│   ├── inbox/             # Управління повідомленнями
│   ├── knowledge/         # RAG база знань
│   ├── kyb/               # KYB моніторинг
│   ├── models/            # SQLAlchemy моделі
│   ├── services/          # Бізнес логіка
│   ├── utils/             # Утиліти
│   └── workers/           # Celery задачі
├── migrations/            # Міграції бази даних
├── scripts/               # PowerShell скрипти
├── tests/                 # Тести
├── config.py              # Конфігурація
├── requirements.txt       # Python залежності
└── run.py                 # Точка входу
```

## API Документація

API документація доступна за адресою `/api/v1/docs` після запуску сервера.

### Основні endpoints:

- `GET /api/v1/health` - Перевірка здоров'я
- `POST /api/v1/auth/login` - Вхід
- `POST /api/v1/auth/register` - Реєстрація
- `GET /api/v1/inbox/messages` - Список повідомлень
- `POST /api/v1/crm/leads` - Створення ліда
- `GET /api/v1/calendar/events` - Події календаря
- `POST /api/v1/knowledge/upload` - Завантаження документів
- `POST /api/v1/billing/checkout` - Створення Stripe сесії
- `POST /api/v1/kyb/counterparties` - Додавання контрагента

## Тестування

```powershell
# Запуск всіх тестів
.\scripts\test.ps1

# Запуск конкретного тесту
pytest tests/test_app.py -v

# Запуск з покриттям
pytest --cov=app tests/
```

## Інтернаціоналізація (i18n)

Система підтримує три мови: англійську, німецьку та українську.

### Робота з перекладами

```powershell
# Витягнути рядки для перекладу
.\scripts\extract-messages.ps1

# Оновити переклади
.\scripts\update-translations.ps1

# Скомпілювати переклади
.\scripts\compile-translations.ps1
```

### API для мов

```http
# Отримати доступні мови
GET /api/v1/languages

# Встановити мову
POST /api/v1/language
{"language": "de"}
```

Детальна документація: [docs/i18n.md](docs/i18n.md)

## Розгортання

### Development
```powershell
.\scripts\run-dev.ps1
```

### Production на Render.com

#### Підготовка до deployment:
```powershell
.\scripts\deploy-render.ps1
```

#### Налаштування на Render.com:

1. **Створіть PostgreSQL базу даних**:
   - Додайте PostgreSQL сервіс в Render dashboard
   - Скопіюйте DATABASE_URL

2. **Створіть Redis інстанс**:
   - Додайте Redis сервіс
   - Скопіюйте REDIS_URL

3. **Створіть Web Service**:
   - Підключіть GitHub репозиторій
   - Build Command: `pip install --upgrade pip && pip install -r requirements.txt`
   - Start Command: `python -c "from app import create_app; from app.utils.schema import init_database_schema; app = create_app('production'); init_database_schema(app)" && flask db upgrade && gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 run:app`

4. **Створіть Worker Service** (для Celery):
   - Start Command: `celery -A celery_app.celery worker --loglevel=info --concurrency=2`

5. **Налаштуйте змінні середовища**:
   ```
   DATABASE_URL=<auto-provided>
   REDIS_URL=<auto-provided>
   SECRET_KEY=<generate-random>
   JWT_SECRET_KEY=<generate-random>
   OPENAI_API_KEY=<your-openai-key>
   STRIPE_SECRET_KEY=<your-stripe-key>
   DB_SCHEMA=ai_secretary
   FLASK_ENV=production
   ```

#### Особливості схеми бази даних:
- Проект використовує окрему схему `ai_secretary` в PostgreSQL
- Це дозволяє ізолювати таблиці від інших проектів в тій же базі
- Схема створюється автоматично при першому deployment
- Всі міграції виконуються в межах цієї схеми

### Docker Deployment
```bash
# Build image
docker build -t ai-secretary .

# Run container
docker run -p 5000:5000 --env-file .env ai-secretary
```

## Моніторинг та логи

- Логи зберігаються в директорії `logs/`
- Метрики доступні через Prometheus endpoints
- Health check: `GET /api/v1/health`
- Status check: `GET /api/v1/status`

## Безпека

- JWT токени для аутентифікації
- CORS налаштування
- Rate limiting
- Input validation
- SQL injection захист
- XSS захист

## Ліцензія

[Вкажіть ліцензію]

## Підтримка

Для питань та підтримки створіть issue в репозиторії.