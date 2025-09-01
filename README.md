# AI Secretary SaaS Platform

Платформа AI Secretary для управления задачами и автоматизации бизнес-процессов.

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/pilipandr770/sekretar.git
cd sekretar
```

### 2. Настройка переменных окружения

Скопируйте файл с примером переменных окружения:

```bash
cp .env.example .env
```

Отредактируйте `.env` файл и добавьте ваши реальные API ключи:

- `OPENAI_API_KEY` - ваш OpenAI API ключ
- `STRIPE_PUBLISHABLE_KEY` и `STRIPE_SECRET_KEY` - ключи Stripe для платежей
- `GOOGLE_CLIENT_ID` и `GOOGLE_CLIENT_SECRET` - для Google OAuth
- Другие необходимые ключи

### 3. Запуск с Docker

```bash
docker-compose up -d
```

### 4. Доступ к приложению

Приложение будет доступно по адресу: http://localhost:5000

## Структура проекта

- `app/` - основной код приложения
- `migrations/` - миграции базы данных
- `tests/` - тесты
- `docker-compose.yml` - конфигурация Docker
- `.env.example` - пример переменных окружения

## Безопасность

⚠️ **Важно**: Никогда не коммитьте файл `.env` с реальными API ключами в репозиторий!

Файл `.env` добавлен в `.gitignore` и не будет отслеживаться Git.

## Разработка

### Установка зависимостей

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### Запуск в режиме разработки

```bash
flask run
```

## Лицензия

MIT License