# AI Secretary - Translation System Guide

## Overview

AI Secretary поддерживает многоязычность с помощью Flask-Babel. Система переводов включает:
- 3 языка: English (en), Deutsch (de), Українська (uk)
- Автоматическое определение языка пользователя
- Fallback на английский язык при отсутствии перевода
- Поддержка переводов в HTML шаблонах, Python коде и JavaScript

## Startup Commands

### Локальная разработка (SQLite)
```powershell
.\scripts\dev-local.ps1
```

**Особенности:**
- Использует SQLite базу данных
- Отключены внешние сервисы (Redis, Celery)
- Простой кеш в памяти
- Режим отладки включен
- Порт: 5000 (по умолчанию)

**Дополнительные параметры:**
```powershell
.\scripts\dev-local.ps1 -Clean -Verbose -Port 8000
```

### Развертывание на Render.com (PostgreSQL)
```powershell
.\scripts\dev-render.ps1
```

**Особенности:**
- Использует PostgreSQL (DATABASE_URL от Render)
- Включены внешние сервисы
- Redis кеш (REDIS_URL от Render)
- Продакшн режим
- Проверка переменных окружения

**Дополнительные параметры:**
```powershell
.\scripts\dev-render.ps1 -Verbose
```

## Translation System Status

### ✅ Completed Components

1. **Flask-Babel Integration**
   - Babel инициализирован в `app/utils/i18n.py`
   - Конфигурация в `babel.cfg`
   - Поддержка 3 языков

2. **Translation Files**
   - `.po` файлы для всех языков обновлены
   - `.mo` файлы скомпилированы
   - Переводы загружаются автоматически

3. **HTML Templates**
   - Все основные шаблоны используют `{{ _('text') }}`
   - Поддержка переключения языков
   - Локализованные формы и сообщения

4. **Startup Scripts**
   - `dev-local.ps1` для локальной разработки
   - `dev-render.ps1` для Render развертывания
   - Автоматическая компиляция переводов

## Available URLs

### Локальная разработка
- **Приложение:** http://localhost:5000
- **API Документация:** http://localhost:5000/api/v1/docs
- **Проверка здоровья:** http://localhost:5000/api/v1/health

### Render развертывание
- URLs будут предоставлены Render после развертывания
- Те же эндпоинты доступны на домене Render

## Translation Management

### Извлечение новых сообщений
```powershell
& ".\.venv\Scripts\Activate.ps1"
pybabel extract -F babel.cfg -k _l -o messages.pot .
```

### Обновление переводов
```powershell
# Все языки
pybabel update -i messages.pot -d app\translations

# Конкретный язык
pybabel update -i messages.pot -d app\translations -l de
```

### Компиляция переводов
```powershell
# Все языки
pybabel compile -d app\translations

# Конкретный язык
pybabel compile -d app\translations -l uk
```

## Environment Variables

### Обязательные для Render
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Flask secret key
- `JWT_SECRET_KEY` - JWT signing key

### Опциональные сервисы
- `REDIS_URL` - Redis cache
- `OPENAI_API_KEY` - OpenAI integration
- `STRIPE_SECRET_KEY` - Stripe billing
- `GOOGLE_CLIENT_ID` - Google OAuth
- `TELEGRAM_BOT_TOKEN` - Telegram bot

### Локальная разработка
Все переменные автоматически настраиваются скриптом `dev-local.ps1`

## Language Support

### Supported Languages
- **English (en)** - Default language, fallback
- **Deutsch (de)** - German translations
- **Українська (uk)** - Ukrainian translations

### Language Detection Priority
1. URL parameter (`?lang=de`)
2. Session storage
3. User profile setting
4. Browser Accept-Language header
5. Default (English)

## Troubleshooting

### Translation Issues
- Убедитесь, что .mo файлы скомпилированы
- Проверьте синтаксис в .po файлах
- Перезапустите приложение после изменений

### Startup Issues
- Проверьте виртуальное окружение (`.venv`)
- Убедитесь, что все зависимости установлены
- Проверьте переменные окружения для Render

### Database Issues
- Локально: SQLite создается автоматически
- Render: Проверьте DATABASE_URL в настройках

## Next Steps

1. **Для локальной разработки:**
   ```powershell
   .\scripts\dev-local.ps1
   ```

2. **Для развертывания на Render:**
   - Настройте переменные окружения в Render dashboard
   - Используйте `.\scripts\dev-render.ps1` для тестирования
   - Deploy через Render interface

3. **Для добавления новых переводов:**
   - Добавьте `{{ _('New text') }}` в шаблоны
   - Запустите извлечение сообщений
   - Переведите в .po файлах
   - Скомпилируйте переводы