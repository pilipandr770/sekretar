# Design Document

## Overview

Дизайн решения критических проблем AI Secretary приложения включает исправление аутентификации, оптимизацию производительности, стабилизацию сервисов, исправление системы переводов и улучшение конфигурации базы данных.

## Architecture

### Problem Analysis

Основные проблемы выявленные из логов:
1. **Redis Connection Issues**: Множественные ошибки "Connection refused" к localhost:6379
2. **Slow Requests**: Запросы занимают 4-20+ секунд вместо миллисекунд
3. **Database Configuration Issues**: Неправильная конфигурация PostgreSQL DSN
4. **Translation System Failures**: Проблемы с загрузкой переводов
5. **Service Health Problems**: Множественные сервисы показывают статус "unhealthy"
6. **Authentication Issues**: Проблемы с JWT токенами и сессиями

### Solution Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
├─────────────────────────────────────────────────────────────┤
│  Authentication Fix  │  Translation Fix  │  Performance Fix  │
├─────────────────────────────────────────────────────────────┤
│                   Service Layer                             │
├─────────────────────────────────────────────────────────────┤
│   Redis Fallback   │   DB Optimization  │   Health Monitor  │
├─────────────────────────────────────────────────────────────┤
│                 Infrastructure Layer                        │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Authentication System Fix

**Problem:** Пользователей выбрасывает после входа
**Root Cause:** JWT токены не сохраняются корректно, проблемы с сессиями

**Solution Components:**
- JWT Token Management Fix
- Session Persistence Improvement
- Cookie Configuration Fix
- Redirect Logic Correction

**Implementation:**
```python
# app/auth/routes.py - исправление логики входа
@auth_bp.route('/login', methods=['POST'])
def login():
    # Исправить создание JWT токенов
    # Исправить установку cookies
    # Исправить редирект после входа
    pass

# config.py - исправление JWT конфигурации
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)  # Увеличить время жизни
JWT_COOKIE_SECURE = False  # Для development
JWT_COOKIE_CSRF_PROTECT = False  # Упростить для отладки
```

### 2. Translation System Fix

**Problem:** Переводы не работают
**Root Cause:** Проблемы с компиляцией .mo файлов, неправильная инициализация Babel

**Solution Components:**
- Babel Configuration Fix
- Translation File Compilation
- Language Detection Fix
- Fallback Mechanism

**Implementation:**
```python
# app/utils/i18n.py - исправление системы переводов
from flask_babel import Babel, get_locale
from flask import request, session

def init_babel(app):
    babel = Babel(app)
    
    @babel.localeselector
    def get_locale():
        # Исправить логику определения языка
        return request.args.get('lang') or \
               session.get('language') or \
               request.accept_languages.best_match(['en', 'de', 'uk']) or 'en'
```

### 3. Performance Optimization

**Problem:** Медленные запросы (4-20+ секунд)
**Root Cause:** Неэффективные запросы к БД, проблемы с Redis, медленная инициализация

**Solution Components:**
- Database Query Optimization
- Redis Connection Pooling
- Lazy Loading Implementation
- Caching Strategy

**Implementation:**
```python
# app/utils/performance_optimizer.py
class PerformanceOptimizer:
    def __init__(self, app):
        self.app = app
        self.setup_database_optimization()
        self.setup_caching_strategy()
        self.setup_lazy_loading()
    
    def setup_database_optimization(self):
        # Оптимизация подключений к БД
        # Настройка connection pooling
        # Индексы для частых запросов
        pass
```

### 4. Service Stability Fix

**Problem:** Множественные ошибки сервисов
**Root Cause:** Неправильная конфигурация Redis, проблемы с fallback механизмами

**Solution Components:**
- Redis Fallback Implementation
- Service Health Monitoring
- Graceful Degradation
- Error Handling Improvement

**Implementation:**
```python
# app/utils/service_manager.py
class ServiceManager:
    def __init__(self, app):
        self.app = app
        self.setup_redis_fallback()
        self.setup_health_monitoring()
    
    def setup_redis_fallback(self):
        # Реализация fallback для Redis
        if not self.test_redis_connection():
            self.app.config['CACHE_TYPE'] = 'simple'
            self.app.config['CELERY_BROKER_URL'] = None
```

### 5. Database Configuration Fix

**Problem:** Неправильная конфигурация PostgreSQL DSN
**Root Cause:** Некорректный формат DATABASE_URL, проблемы со схемами

**Solution Components:**
- Database URL Validation
- Schema Management Fix
- SQLite/PostgreSQL Switching
- Connection String Correction

**Implementation:**
```python
# config.py - исправление конфигурации БД
def fix_database_configuration():
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # Исправить формат PostgreSQL URL
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        # Проверить корректность URL
        if 'sqlite:///' in database_url:
            # SQLite mode - отключить схемы
            return {
                'SQLALCHEMY_DATABASE_URI': database_url,
                'DB_SCHEMA': None,
                'SQLALCHEMY_ENGINE_OPTIONS': get_sqlite_options()
            }
        else:
            # PostgreSQL mode
            return {
                'SQLALCHEMY_DATABASE_URI': database_url,
                'DB_SCHEMA': 'ai_secretary',
                'SQLALCHEMY_ENGINE_OPTIONS': get_postgresql_options()
            }
```

## Data Models

### Performance Metrics Model
```python
class PerformanceMetric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.String(255), nullable=False)
    response_time_ms = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status_code = db.Column(db.Integer)
```

### Service Health Model
```python
class ServiceHealth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # healthy, degraded, unavailable
    last_check = db.Column(db.DateTime, default=datetime.utcnow)
    error_message = db.Column(db.Text)
```

## Error Handling

### Authentication Error Handling
```python
@auth_bp.errorhandler(401)
def handle_auth_error(error):
    return jsonify({
        'error': 'Authentication failed',
        'message': _('Please log in again'),
        'redirect': url_for('auth.login')
    }), 401
```

### Service Error Handling
```python
class ServiceErrorHandler:
    def handle_redis_error(self, error):
        # Переключение на simple cache
        self.app.config['CACHE_TYPE'] = 'simple'
        logger.warning(f"Redis unavailable, using simple cache: {error}")
    
    def handle_database_error(self, error):
        # Graceful degradation для БД
        if 'connection' in str(error).lower():
            return self.switch_to_readonly_mode()
```

## Testing Strategy

### Performance Testing
```python
def test_response_times():
    """Тест времени ответа для критических эндпоинтов"""
    endpoints = ['/api/v1/auth/login', '/dashboard', '/api/v1/auth/me']
    
    for endpoint in endpoints:
        start_time = time.time()
        response = client.get(endpoint)
        response_time = (time.time() - start_time) * 1000
        
        assert response_time < 2000, f"{endpoint} too slow: {response_time}ms"
```

### Authentication Testing
```python
def test_login_persistence():
    """Тест сохранения сессии после входа"""
    # Вход в систему
    response = client.post('/api/v1/auth/login', json={
        'email': 'test@example.com',
        'password': 'password'
    })
    
    # Проверка JWT токена
    assert 'access_token' in response.json
    
    # Проверка доступа к защищенным ресурсам
    headers = {'Authorization': f'Bearer {response.json["access_token"]}'}
    protected_response = client.get('/api/v1/auth/me', headers=headers)
    assert protected_response.status_code == 200
```

### Translation Testing
```python
def test_translation_system():
    """Тест системы переводов"""
    with app.test_request_context('/?lang=de'):
        assert get_locale() == 'de'
        assert _('Welcome') == 'Willkommen'
    
    with app.test_request_context('/?lang=uk'):
        assert get_locale() == 'uk'
        assert _('Welcome') == 'Ласкаво просимо'
```

## Implementation Plan

### Phase 1: Critical Fixes (Priority 1)
1. Fix authentication system
2. Fix database configuration
3. Implement Redis fallback
4. Fix translation system

### Phase 2: Performance Optimization (Priority 2)
1. Optimize database queries
2. Implement caching strategy
3. Add performance monitoring
4. Optimize static assets

### Phase 3: Monitoring & Stability (Priority 3)
1. Enhanced error handling
2. Service health monitoring
3. User feedback system
4. Comprehensive logging

## Configuration Changes

### Environment Variables Fix
```bash
# .env исправления
DATABASE_URL=sqlite:///ai_secretary.db  # Исправить формат
REDIS_URL=  # Очистить для fallback
CACHE_TYPE=simple  # Использовать simple cache
JWT_ACCESS_TOKEN_EXPIRES=86400  # 24 часа
```

### Application Configuration
```python
# config.py обновления
class FixedConfig(Config):
    # Исправления для стабильности
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': {'check_same_thread': False} if 'sqlite' in DATABASE_URL else {}
    }
    
    # Упрощенная конфигурация для отладки
    JWT_COOKIE_CSRF_PROTECT = False
    WTF_CSRF_ENABLED = False
    
    # Fallback конфигурация
    CACHE_TYPE = 'simple'
    CELERY_BROKER_URL = None
```