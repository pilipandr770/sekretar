# AI Secretary - Руководство разработчика

Это руководство поможет вам настроить локальную среду разработки и понять архитектуру проекта AI Secretary.

## Содержание

- [Быстрый старт](#быстрый-старт)
- [Архитектура проекта](#архитектура-проекта)
- [Настройка среды разработки](#настройка-среды-разработки)
- [Работа с базой данных](#работа-с-базой-данных)
- [Тестирование](#тестирование)
- [API разработка](#api-разработка)
- [Фронтенд разработка](#фронтенд-разработка)
- [Стандарты кода](#стандарты-кода)
- [Отладка](#отладка)
- [Полезные команды](#полезные-команды)

## Быстрый старт

### 1. Клонирование и настройка

```bash
# Клонирование репозитория
git clone https://github.com/pilipandr770/sekretar.git
cd sekretar

# Автоматическая настройка (рекомендуется)
python start.py
```

Скрипт `start.py` автоматически:
- Создаст виртуальное окружение
- Установит зависимости
- Создаст `.env` файл
- Инициализирует базу данных
- Запустит приложение в режиме разработки

### 2. Ручная настройка

Если предпочитаете настроить все вручную:

```bash
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env файл

# Инициализация базы данных
flask db upgrade

# Запуск в режиме разработки
python run.py
```

## Архитектура проекта

### Структура директорий

```
ai_secretary/
├── app/                          # Основное приложение
│   ├── __init__.py              # Фабрика приложения
│   ├── admin/                   # Административная панель
│   ├── api/                     # REST API endpoints
│   │   ├── v1/                  # API версия 1
│   │   │   ├── auth/           # Аутентификация
│   │   │   ├── billing/        # Биллинг и подписки
│   │   │   ├── calendar/       # Календарь
│   │   │   ├── channels/       # Каналы связи
│   │   │   ├── crm/           # CRM функции
│   │   │   ├── inbox/         # Входящие сообщения
│   │   │   ├── knowledge/     # База знаний
│   │   │   ├── kyb/           # Know Your Business
│   │   │   └── tasks/         # Управление задачами
│   ├── auth/                    # Модуль аутентификации
│   ├── billing/                 # Биллинг система
│   ├── calendar/                # Календарь интеграция
│   ├── channels/                # Каналы связи (Telegram, Signal)
│   ├── cli/                     # CLI команды
│   ├── config/                  # Конфигурация
│   ├── crm/                     # CRM модуль
│   ├── inbox/                   # Обработка входящих сообщений
│   ├── knowledge/               # База знаний
│   ├── kyb/                     # KYB модуль
│   ├── main/                    # Основные маршруты
│   ├── models/                  # Модели базы данных
│   ├── secretary/               # ИИ секретарь
│   ├── services/                # Бизнес-логика
│   ├── static/                  # Статические файлы
│   ├── tasks/                   # Фоновые задачи
│   ├── templates/               # HTML шаблоны
│   ├── translations/            # Переводы
│   ├── utils/                   # Утилиты
│   └── workers/                 # Celery воркеры
├── migrations/                   # Миграции базы данных
├── tests/                       # Тесты
├── docs/                        # Документация
├── scripts/                     # Скрипты управления
├── deployment/                  # Конфигурации деплоя
└── uploads/                     # Загруженные файлы
```

### Основные компоненты

#### 1. Фабрика приложения (`app/__init__.py`)
Создает и настраивает Flask приложение с использованием паттерна Application Factory.

#### 2. Модели данных (`app/models/`)
SQLAlchemy модели для всех сущностей системы:
- `User` - пользователи
- `Tenant` - тенанты (мультитенантность)
- `Contact` - контакты CRM
- `Task` - задачи
- `Document` - документы
- `Subscription` - подписки

#### 3. API (`app/api/v1/`)
RESTful API с версионированием, документированный через OpenAPI/Swagger.

#### 4. Сервисы (`app/services/`)
Бизнес-логика приложения:
- `AIService` - интеграция с OpenAI
- `BillingService` - обработка платежей
- `CalendarService` - работа с календарем
- `NotificationService` - уведомления

#### 5. Воркеры (`app/workers/`)
Celery задачи для фоновой обработки:
- Обработка документов
- Отправка уведомлений
- Синхронизация данных

## Настройка среды разработки

### Переменные окружения для разработки

Создайте `.env` файл с настройками для разработки:

```bash
# === ОСНОВНЫЕ НАСТРОЙКИ ===
SECRET_KEY=dev-secret-key-change-in-production
JWT_SECRET_KEY=dev-jwt-secret-key
FLASK_ENV=development
DEBUG=true

# === БАЗА ДАННЫХ ===
# SQLite для локальной разработки
DATABASE_URL=sqlite:///ai_secretary.db

# Или PostgreSQL для более реалистичного тестирования
# DATABASE_URL=postgresql://user:password@localhost:5432/ai_secretary_dev

# === ВНЕШНИЕ СЕРВИСЫ (опционально) ===
# OPENAI_API_KEY=sk-your-openai-key-here
# STRIPE_SECRET_KEY=sk_test_your-stripe-test-key
# GOOGLE_CLIENT_ID=your-google-client-id
# GOOGLE_CLIENT_SECRET=your-google-client-secret

# === РАЗРАБОТКА ===
TEMPLATES_AUTO_RELOAD=true
LOG_LEVEL=DEBUG
LOG_FORMAT=text
WTF_CSRF_ENABLED=false  # Отключить CSRF для тестирования API
```

### IDE настройки

#### VS Code
Рекомендуемые расширения:
- Python
- Pylance
- Python Docstring Generator
- GitLens
- REST Client

Настройки `.vscode/settings.json`:
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": false,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests/"],
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    }
}
```

#### PyCharm
1. Откройте проект в PyCharm
2. Настройте интерпретатор Python: `File` → `Settings` → `Project` → `Python Interpreter`
3. Выберите виртуальное окружение `venv/bin/python`
4. Настройте запуск: `Run` → `Edit Configurations` → добавьте конфигурацию Flask

## Работа с базой данных

### Миграции

```bash
# Создание новой миграции
flask db migrate -m "Описание изменений"

# Применение миграций
flask db upgrade

# Откат миграции
flask db downgrade

# История миграций
flask db history

# Текущая версия
flask db current
```

### Работа с моделями

Пример создания новой модели:

```python
# app/models/example.py
from app import db
from datetime import datetime

class Example(db.Model):
    __tablename__ = 'examples'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref='examples')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<Example {self.name}>'
```

### Сидеры (заполнение тестовыми данными)

```bash
# Создание тестовых данных
python -c "from app.utils.data_seeder import DataSeeder; DataSeeder().seed_all()"

# Очистка базы данных
python -c "from app.utils.data_seeder import DataSeeder; DataSeeder().clean_all()"
```

## Тестирование

### Запуск тестов

```bash
# Все тесты
python -m pytest

# Конкретный файл
python -m pytest tests/test_api_endpoints.py

# Конкретный тест
python -m pytest tests/test_api_endpoints.py::test_user_creation

# С покрытием кода
python -m pytest --cov=app --cov-report=html

# Параллельное выполнение
python -m pytest -n auto

# Только быстрые тесты
python -m pytest -m "not slow"
```

### Структура тестов

```
tests/
├── conftest.py                  # Общие фикстуры
├── test_models.py              # Тесты моделей
├── test_api_endpoints.py       # Тесты API
├── test_services.py            # Тесты сервисов
├── test_auth.py                # Тесты аутентификации
├── test_billing.py             # Тесты биллинга
└── infrastructure/             # Инфраструктурные тесты
    ├── test_database.py
    └── test_external_services.py
```

### Написание тестов

Пример теста API:

```python
# tests/test_api_example.py
import pytest
from app import create_app, db
from app.models import User

@pytest.fixture
def client():
    app = create_app('testing')
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()

def test_create_user(client):
    """Тест создания пользователя через API"""
    response = client.post('/api/v1/users', json={
        'email': 'test@example.com',
        'password': 'password123',
        'name': 'Test User'
    })
    
    assert response.status_code == 201
    data = response.get_json()
    assert data['email'] == 'test@example.com'
    assert 'id' in data
```

## API разработка

### Структура API endpoint

```python
# app/api/v1/example.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Example
from app.services import ExampleService
from app.utils.validators import validate_json

bp = Blueprint('example', __name__)

@bp.route('/examples', methods=['GET'])
@jwt_required()
def get_examples():
    """Получить список примеров"""
    user_id = get_jwt_identity()
    examples = ExampleService.get_user_examples(user_id)
    return jsonify([example.to_dict() for example in examples])

@bp.route('/examples', methods=['POST'])
@jwt_required()
@validate_json(['name'])
def create_example():
    """Создать новый пример"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    example = ExampleService.create_example(
        user_id=user_id,
        name=data['name'],
        description=data.get('description')
    )
    
    return jsonify(example.to_dict()), 201

@bp.route('/examples/<int:example_id>', methods=['GET'])
@jwt_required()
def get_example(example_id):
    """Получить конкретный пример"""
    user_id = get_jwt_identity()
    example = ExampleService.get_example(example_id, user_id)
    
    if not example:
        return jsonify({'error': 'Example not found'}), 404
    
    return jsonify(example.to_dict())
```

### Документация API

API автоматически документируется через OpenAPI. Доступно по адресу `/api/v1/docs`.

Для добавления документации к endpoint используйте docstring:

```python
@bp.route('/examples', methods=['POST'])
@jwt_required()
def create_example():
    """
    Создать новый пример
    ---
    tags:
      - Examples
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - name
          properties:
            name:
              type: string
              description: Название примера
            description:
              type: string
              description: Описание примера
    responses:
      201:
        description: Пример успешно создан
        schema:
          $ref: '#/definitions/Example'
      400:
        description: Ошибка валидации
      401:
        description: Не авторизован
    """
    # код endpoint
```

## Фронтенд разработка

### Структура шаблонов

```
app/templates/
├── base.html                   # Базовый шаблон
├── auth/                       # Шаблоны аутентификации
│   ├── login.html
│   └── register.html
├── dashboard/                  # Панель управления
│   ├── index.html
│   └── settings.html
└── components/                 # Переиспользуемые компоненты
    ├── navbar.html
    └── sidebar.html
```

### Статические файлы

```
app/static/
├── css/                        # Стили
│   ├── main.css
│   └── components/
├── js/                         # JavaScript
│   ├── main.js
│   ├── api.js                 # API клиент
│   └── components/
├── img/                        # Изображения
└── vendor/                     # Внешние библиотеки
```

### Интернационализация (i18n)

```bash
# Извлечение строк для перевода
pybabel extract -F babel.cfg -k _l -o messages.pot .

# Создание нового языка
pybabel init -i messages.pot -d app/translations -l ru

# Обновление переводов
pybabel update -i messages.pot -d app/translations

# Компиляция переводов
pybabel compile -d app/translations
```

## Стандарты кода

### Форматирование

Используется Black для форматирования кода:

```bash
# Форматирование всего проекта
black .

# Проверка без изменений
black --check .
```

### Линтинг

```bash
# Проверка с flake8
flake8 app/ tests/

# Проверка с pylint
pylint app/

# Проверка типов с mypy
mypy app/
```

### Pre-commit hooks

Установите pre-commit hooks для автоматической проверки:

```bash
pip install pre-commit
pre-commit install
```

### Стиль кода

1. **Именование**:
   - Классы: `PascalCase`
   - Функции и переменные: `snake_case`
   - Константы: `UPPER_SNAKE_CASE`

2. **Docstrings**: используйте Google style
   ```python
   def example_function(param1: str, param2: int) -> bool:
       """
       Краткое описание функции.
       
       Args:
           param1: Описание первого параметра
           param2: Описание второго параметра
           
       Returns:
           Описание возвращаемого значения
           
       Raises:
           ValueError: Когда возникает эта ошибка
       """
       pass
   ```

3. **Импорты**: группируйте в порядке:
   ```python
   # Стандартная библиотека
   import os
   import sys
   
   # Внешние библиотеки
   from flask import Flask
   import sqlalchemy
   
   # Локальные импорты
   from app.models import User
   from app.services import UserService
   ```

## Отладка

### Логирование

```python
import logging

logger = logging.getLogger(__name__)

def example_function():
    logger.debug("Отладочная информация")
    logger.info("Информационное сообщение")
    logger.warning("Предупреждение")
    logger.error("Ошибка")
    logger.critical("Критическая ошибка")
```

### Отладчик

```python
# Добавьте точку останова
import pdb; pdb.set_trace()

# Или используйте встроенный breakpoint() (Python 3.7+)
breakpoint()
```

### Flask Debug Toolbar

Для разработки включен Flask Debug Toolbar:

```python
# В .env файле
DEBUG=true
```

Toolbar показывает:
- SQL запросы
- Время выполнения
- Переменные шаблонов
- Конфигурацию

### Профилирование

```bash
# Профилирование с cProfile
python -m cProfile -o profile.stats run.py

# Анализ результатов
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative'); p.print_stats(20)"
```

## Полезные команды

### Управление базой данных

```bash
# Создание всех таблиц
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"

# Удаление всех таблиц
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.drop_all()"

# Создание администратора
python -c "from app.cli.admin import create_admin_user; create_admin_user('admin@example.com', 'password123')"
```

### Работа с Celery

```bash
# Запуск воркера
celery -A celery_app.celery worker --loglevel=info

# Запуск планировщика
celery -A celery_app.celery beat --loglevel=info

# Мониторинг задач
celery -A celery_app.celery flower
```

### Утилиты разработки

```bash
# Проверка конфигурации
python -c "from app.utils.config_validator import ConfigValidator; ConfigValidator().validate_all()"

# Проверка здоровья сервисов
python -c "from app.utils.health_validator import HealthValidator; HealthValidator().validate_all_services()"

# Генерация секретных ключей
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32)); print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

### Git hooks

```bash
# Установка pre-commit hook
echo '#!/bin/bash
black --check .
flake8 app/ tests/
python -m pytest tests/ -x' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## Архитектурные решения

### Паттерны проектирования

1. **Application Factory** - создание приложения
2. **Blueprint** - модульная структура
3. **Service Layer** - бизнес-логика
4. **Repository Pattern** - доступ к данным
5. **Dependency Injection** - внедрение зависимостей

### Принципы

1. **SOLID** - следование принципам SOLID
2. **DRY** - не повторяйтесь
3. **KISS** - простота решений
4. **YAGNI** - не реализуйте то, что не нужно

### Безопасность

1. **Валидация входных данных**
2. **Санитизация вывода**
3. **CSRF защита**
4. **Rate limiting**
5. **Логирование безопасности**

## Вклад в проект

### Процесс разработки

1. Создайте feature branch: `git checkout -b feature/new-feature`
2. Внесите изменения и добавьте тесты
3. Убедитесь, что все тесты проходят
4. Создайте Pull Request
5. Дождитесь code review

### Стандарты коммитов

Используйте Conventional Commits:

```
feat: добавить новую функцию
fix: исправить ошибку
docs: обновить документацию
style: изменения форматирования
refactor: рефакторинг кода
test: добавить тесты
chore: обновить зависимости
```

### Code Review

При review обращайте внимание на:
- Соответствие стандартам кода
- Покрытие тестами
- Производительность
- Безопасность
- Документацию

Это руководство поможет вам эффективно разрабатывать AI Secretary. Для дополнительной информации обращайтесь к документации конкретных модулей или создавайте Issues в репозитории.