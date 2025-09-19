# Дизайн системы подготовки проекта к деплою

## Обзор

Данный документ описывает архитектуру и подход к подготовке Flask-приложения AI Secretary для продакшн деплоя. Система включает автоматизированную очистку проекта, унификацию конфигурации, исправление ошибок и создание оптимизированных скриптов запуска.

## Архитектура

### Компоненты системы

```mermaid
graph TB
    A[Cleanup Manager] --> B[File Scanner]
    A --> C[Directory Cleaner]
    
    D[Config Manager] --> E[Environment Validator]
    D --> F[Config Unifier]
    
    G[Error Fixer] --> H[Database Fixer]
    G --> I[Route Validator]
    
    J[Deploy Optimizer] --> K[Script Generator]
    J --> L[Gitignore Optimizer]
    
    B --> M[Cleanup Report]
    E --> N[Config Report]
    H --> O[Fix Report]
    K --> P[Deploy Scripts]
```

### Структура проекта после очистки

```
ai_secretary/
├── app/                    # Основное приложение
├── migrations/             # Миграции базы данных
├── scripts/               # Скрипты управления (оптимизированные)
├── docs/                  # Документация (только необходимая)
├── .env.example           # Шаблон конфигурации
├── .gitignore            # Оптимизированный gitignore
├── requirements.txt       # Зависимости
├── run.py                # Точка входа
├── config.py             # Конфигурация
├── render.yaml           # Конфигурация Render
└── README.md             # Документация проекта
```

## Компоненты и интерфейсы

### 1. Cleanup Manager

**Назначение:** Управление процессом очистки проекта от ненужных файлов.

**Интерфейс:**
```python
class CleanupManager:
    def scan_project(self) -> Dict[str, List[str]]
    def identify_junk_files(self) -> List[str]
    def clean_directories(self, directories: List[str]) -> CleanupReport
    def optimize_structure(self) -> None
```

**Логика работы:**
- Сканирование всех файлов и папок проекта
- Идентификация мусорных файлов по паттернам
- Безопасное удаление с созданием бэкапа
- Оптимизация структуры папок

**Паттерны для удаления:**
- `test_execution_*` - логи выполнения тестов
- `final_reports/` - отчеты (кроме последнего)
- `evidence/` - временные файлы доказательств
- `examples/` - демо файлы
- `*.db` в корне - тестовые базы данных
- `__pycache__/` - кэш Python
- `.pytest_cache/` - кэш pytest
- Дублирующиеся .env файлы

### 2. Config Manager

**Назначение:** Унификация и оптимизация конфигурации окружения.

**Интерфейс:**
```python
class ConfigManager:
    def analyze_env_files(self) -> Dict[str, Any]
    def create_unified_env(self) -> str
    def generate_env_example(self) -> str
    def validate_config(self) -> ValidationReport
```

**Стратегия унификации:**
1. Анализ всех существующих .env файлов
2. Выделение уникальных переменных
3. Создание единого .env.example с документацией
4. Удаление дублирующихся файлов
5. Создание .env для локальной разработки

**Структура .env.example:**
```bash
# === КРИТИЧНЫЕ НАСТРОЙКИ ===
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# === БАЗА ДАННЫХ ===
DATABASE_URL=postgresql://user:pass@localhost:5432/db
# Для локальной разработки используйте SQLite:
# DATABASE_URL=sqlite:///ai_secretary.db

# === ВНЕШНИЕ СЕРВИСЫ ===
OPENAI_API_KEY=your-openai-key
STRIPE_SECRET_KEY=your-stripe-key
# ... остальные с описанием
```

### 3. Error Fixer

**Назначение:** Исправление критических ошибок приложения.

**Интерфейс:**
```python
class ErrorFixer:
    def fix_database_errors(self) -> FixReport
    def validate_routes(self) -> RouteReport
    def fix_performance_monitoring(self) -> None
    def fix_context_errors(self) -> None
```

**Исправления:**

#### 3.1 Database Errors
- Создание отсутствующей таблицы `performance_alerts`
- Исправление миграций
- Добавление проверок существования таблиц

#### 3.2 Context Errors
- Исправление ошибок "Working outside of application context"
- Добавление app_context() где необходимо
- Оптимизация health checks

#### 3.3 Route Validation
- Проверка всех зарегистрированных маршрутов
- Исправление дублирующихся роутов
- Валидация API endpoints

### 4. Deploy Optimizer

**Назначение:** Создание оптимизированных скриптов и конфигураций для деплоя.

**Интерфейс:**
```python
class DeployOptimizer:
    def create_startup_script(self) -> str
    def optimize_gitignore(self) -> str
    def generate_render_config(self) -> Dict[str, Any]
    def create_health_checks(self) -> None
```

**Создаваемые скрипты:**

#### 4.1 start.py (для локальной разработки)
```python
#!/usr/bin/env python3
"""Локальный запуск приложения"""
import os
import sys
from pathlib import Path

def setup_environment():
    """Настройка окружения для локальной разработки"""
    # Проверка .env файла
    # Создание необходимых папок
    # Инициализация базы данных

def main():
    setup_environment()
    from run import main as run_main
    run_main()

if __name__ == '__main__':
    main()
```

#### 4.2 start-prod.py (для Render)
```python
#!/usr/bin/env python3
"""Продакшн запуск для Render"""
import os
import sys

def setup_production():
    """Настройка продакшн окружения"""
    # Валидация переменных окружения
    # Применение миграций
    # Проверка сервисов

def main():
    setup_production()
    from run import main as run_main
    run_main()

if __name__ == '__main__':
    main()
```

## Модели данных

### CleanupReport
```python
@dataclass
class CleanupReport:
    deleted_files: List[str]
    deleted_directories: List[str]
    space_saved: int  # в байтах
    warnings: List[str]
    errors: List[str]
    backup_location: Optional[str]
```

### ConfigReport
```python
@dataclass
class ConfigReport:
    unified_variables: Dict[str, str]
    removed_duplicates: List[str]
    missing_variables: List[str]
    validation_errors: List[str]
    recommendations: List[str]
```

### FixReport
```python
@dataclass
class FixReport:
    fixed_issues: List[str]
    remaining_issues: List[str]
    database_fixes: List[str]
    route_fixes: List[str]
    performance_fixes: List[str]
```

## Обработка ошибок

### Стратегия обработки ошибок

1. **Безопасность операций**
   - Создание бэкапов перед удалением
   - Валидация операций
   - Откат изменений при ошибках

2. **Логирование**
   - Детальное логирование всех операций
   - Сохранение отчетов в файлы
   - Уведомления о критических ошибках

3. **Восстановление**
   - Автоматическое восстановление из бэкапов
   - Ручные инструкции для критических случаев
   - Валидация после восстановления

### Обработка специфических ошибок

#### Database Connection Errors
```python
def handle_database_error(error: Exception) -> None:
    if "no such table: performance_alerts" in str(error):
        create_performance_alerts_table()
    elif "Working outside of application context" in str(error):
        fix_context_usage()
    else:
        log_unknown_database_error(error)
```

#### Configuration Errors
```python
def handle_config_error(error: Exception) -> None:
    if "SECRET_KEY" in str(error):
        generate_secret_keys()
    elif "DATABASE_URL" in str(error):
        setup_default_database()
    else:
        log_config_error(error)
```

## Стратегия тестирования

### Unit Tests
- Тестирование каждого компонента отдельно
- Мокирование файловых операций
- Валидация логики очистки

### Integration Tests
- Тестирование полного процесса очистки
- Проверка работы с реальными файлами
- Валидация конфигурации

### End-to-End Tests
- Тестирование деплоя на тестовом окружении
- Проверка работы приложения после очистки
- Валидация всех функций

### Test Environment Setup
```python
def setup_test_environment():
    """Создание тестового окружения"""
    # Создание временной структуры проекта
    # Копирование тестовых файлов
    # Настройка изолированной среды
```

## Мониторинг и валидация

### Health Checks
- Проверка доступности базы данных
- Валидация конфигурации
- Мониторинг производительности

### Metrics Collection
- Время выполнения операций очистки
- Количество удаленных файлов
- Размер освобожденного места

### Alerting
- Уведомления о критических ошибках
- Отчеты о завершении операций
- Рекомендации по оптимизации

## Безопасность

### File Operations Security
- Валидация путей файлов
- Проверка прав доступа
- Предотвращение удаления критических файлов

### Configuration Security
- Валидация переменных окружения
- Проверка секретных ключей
- Защита от утечки конфиденциальных данных

### Backup Strategy
- Автоматическое создание бэкапов
- Сжатие и архивирование
- Восстановление по требованию