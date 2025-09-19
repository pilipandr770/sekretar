# AI Secretary SaaS Platform

Платформа AI Secretary для управления задачами и автоматизации бизнес-процессов с поддержкой ИИ, интеграцией внешних сервисов и многопользовательским режимом.

## Быстрый старт

### Требования

- Python 3.8 или выше
- Git
- (Опционально) Docker для контейнеризированного запуска

### 1. Клонирование репозитория

```bash
git clone https://github.com/pilipandr770/sekretar.git
cd sekretar
```

### 2. Локальный запуск (рекомендуется)

Самый простой способ запустить приложение локально:

```bash
python start.py
```

Этот скрипт автоматически:
- Создаст виртуальное окружение (если нужно)
- Создаст `.env` файл из `.env.example`
- Установит зависимости
- Инициализирует базу данных
- Запустит приложение

### 3. Ручная настройка (альтернативный способ)

Если вы предпочитаете настроить все вручную:

#### 3.1. Создание виртуального окружения

```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

#### 3.2. Установка зависимостей

```bash
pip install -r requirements.txt
```

#### 3.3. Настройка переменных окружения

```bash
cp .env.example .env
```

Отредактируйте `.env` файл и настройте необходимые переменные:

```bash
# Обязательные настройки
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here
DATABASE_URL=sqlite:///ai_secretary.db

# Опциональные API ключи (для полной функциональности)
OPENAI_API_KEY=sk-your-openai-api-key-here
STRIPE_SECRET_KEY=sk_test_your-stripe-key
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

#### 3.4. Инициализация базы данных

```bash
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

#### 3.5. Запуск приложения

```bash
python run.py
```

### 4. Доступ к приложению

После запуска приложение будет доступно по адресу:
- **Основное приложение**: http://localhost:5000
- **API документация**: http://localhost:5000/api/v1/docs
- **Проверка здоровья**: http://localhost:5000/api/v1/health

### 5. Вход в систему

По умолчанию создается администратор:
- **Email**: admin@ai-secretary.com
- **Пароль**: admin123

## Конфигурация

### Основные переменные окружения

| Переменная | Обязательная | Описание |
|------------|--------------|----------|
| `SECRET_KEY` | ✅ | Секретный ключ Flask для безопасности |
| `JWT_SECRET_KEY` | ✅ | Ключ для подписи JWT токенов |
| `DATABASE_URL` | ✅ | URL подключения к базе данных |
| `OPENAI_API_KEY` | ❌ | API ключ OpenAI для ИИ функций |
| `STRIPE_SECRET_KEY` | ❌ | Ключ Stripe для платежей |
| `GOOGLE_CLIENT_ID` | ❌ | ID клиента Google OAuth |
| `GOOGLE_CLIENT_SECRET` | ❌ | Секрет клиента Google OAuth |
| `TELEGRAM_BOT_TOKEN` | ❌ | Токен Telegram бота |
| `REDIS_URL` | ❌ | URL Redis для кэширования |

### Примеры конфигурации

#### Локальная разработка (SQLite)
```bash
DATABASE_URL=sqlite:///ai_secretary.db
DEBUG=true
FLASK_ENV=development
```

#### Продакшн (PostgreSQL)
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/ai_secretary
DEBUG=false
FLASK_ENV=production
```

## Структура проекта

```
ai_secretary/
├── app/                    # Основной код приложения
│   ├── api/               # API endpoints
│   ├── auth/              # Аутентификация
│   ├── models/            # Модели базы данных
│   ├── services/          # Бизнес-логика
│   └── utils/             # Утилиты
├── migrations/            # Миграции базы данных
├── tests/                 # Тесты
├── docs/                  # Документация
├── scripts/               # Скрипты управления
├── .env.example          # Пример конфигурации
├── requirements.txt       # Python зависимости
├── start.py              # Скрипт локального запуска
├── start-prod.py         # Скрипт продакшн запуска
└── run.py                # Основная точка входа
```

## Основные функции

### 🤖 ИИ Ассистент
- Интеграция с OpenAI GPT для обработки запросов
- Автоматическая обработка задач и документов
- Интеллектуальные рекомендации

### 👥 Управление пользователями
- Многопользовательская система
- Ролевая модель доступа
- OAuth интеграция (Google)

### 💰 Биллинг и подписки
- Интеграция со Stripe
- Управление подписками
- Отслеживание использования

### 📊 CRM система
- Управление контактами
- Отслеживание взаимодействий
- Аналитика и отчеты

### 📅 Календарь
- Интеграция с Google Calendar
- Управление событиями
- Напоминания и уведомления

### 💬 Коммуникации
- Telegram интеграция
- Signal поддержка
- Email уведомления

### 📄 Управление знаниями
- Загрузка и обработка документов
- Поиск по содержимому
- Векторный поиск

## Разработка

### Запуск тестов

```bash
# Все тесты
python -m pytest

# Конкретный тест
python -m pytest tests/test_api_endpoints.py

# С покрытием
python -m pytest --cov=app
```

### Работа с базой данных

```bash
# Создание миграции
flask db migrate -m "Description of changes"

# Применение миграций
flask db upgrade

# Откат миграции
flask db downgrade
```

### Линтинг и форматирование

```bash
# Проверка кода
ruff check .

# Форматирование
ruff format .

# Проверка типов
mypy app/
```

## Docker

### Локальная разработка

```bash
docker-compose up -d
```

### Продакшн

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Деплой

Для деплоя на продакшн платформы (Render, Heroku, и др.) используйте:

```bash
python start-prod.py
```

Подробные инструкции по деплою см. в [DEPLOYMENT.md](DEPLOYMENT.md).

## Безопасность

⚠️ **Важные правила безопасности:**

1. **Никогда не коммитьте файл `.env`** с реальными ключами
2. **Используйте сильные секретные ключи** (минимум 32 символа)
3. **Регулярно обновляйте зависимости** для устранения уязвимостей
4. **Используйте HTTPS** в продакшене
5. **Ограничьте доступ к базе данных** только необходимыми правами

## Поддержка и документация

- **API документация**: Доступна по адресу `/api/v1/docs` после запуска
- **Руководство разработчика**: [DEVELOPMENT.md](DEVELOPMENT.md)
- **Руководство по деплою**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Issues**: [GitHub Issues](https://github.com/pilipandr770/sekretar/issues)

## Лицензия

MIT License - см. файл [LICENSE](LICENSE) для подробностей.