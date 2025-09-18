# Design Document

## Overview

Система переводов в AI Secretary использует Flask-Babel для интернационализации. Необходимо проверить и исправить все компоненты системы переводов, включая извлечение сообщений, компиляцию переводов, и создание команд запуска для разных сред.

## Architecture

### Translation System Components

1. **Flask-Babel Integration**
   - Конфигурация в `config.py` с поддержкой языков: en, de, uk
   - Babel конфигурация в `babel.cfg`
   - Функции перевода `_()` и `_l()` в шаблонах и коде

2. **Translation Files Structure**
   ```
   app/translations/
   ├── en/LC_MESSAGES/
   │   ├── messages.po
   │   └── messages.mo
   ├── de/LC_MESSAGES/
   │   ├── messages.po
   │   └── messages.mo
   └── uk/LC_MESSAGES/
       ├── messages.po
       └── messages.mo
   ```

3. **PowerShell Scripts**
   - `extract-messages.ps1` - извлечение переводимых строк
   - `update-translations.ps1` - обновление .po файлов
   - `compile-translations.ps1` - компиляция в .mo файлы

4. **Application Startup Commands**
   - Локальная разработка с SQLite
   - Развертывание на Render.com с PostgreSQL

## Components and Interfaces

### 1. Translation Extraction System

**Purpose:** Автоматическое извлечение всех переводимых строк из кода

**Components:**
- Babel configuration (`babel.cfg`)
- PowerShell script для извлечения
- Template scanning для HTML файлов

**Interface:**
```powershell
.\scripts\extract-messages.ps1
```

### 2. Translation Update System

**Purpose:** Обновление существующих переводов новыми строками

**Components:**
- PyBabel update command
- Automatic .po file management
- Language-specific handling

**Interface:**
```powershell
.\scripts\update-translations.ps1 [-Language <lang>]
```

### 3. Translation Compilation System

**Purpose:** Компиляция .po файлов в бинарные .mo файлы

**Components:**
- PyBabel compile command
- Binary file generation
- Verification system

**Interface:**
```powershell
.\scripts\compile-translations.ps1 [-Language <lang>]
```

### 4. Application Startup System

**Purpose:** Различные режимы запуска приложения

**Components:**
- Local development mode (SQLite)
- Production mode (PostgreSQL for Render.com)
- Environment configuration switching

**Interfaces:**
```powershell
# Локальная разработка
.\scripts\dev-local.ps1

# Развертывание на Render
.\scripts\dev-render.ps1
```

## Data Models

### Translation Configuration

```python
# config.py
LANGUAGES = {
    'en': 'English',
    'de': 'Deutsch', 
    'uk': 'Українська'
}
BABEL_DEFAULT_LOCALE = 'en'
BABEL_DEFAULT_TIMEZONE = 'UTC'
```

### Environment Configurations

```python
# Local Development
SQLALCHEMY_DATABASE_URI = 'sqlite:///ai_secretary.db'
CACHE_TYPE = 'simple'
CELERY_BROKER_URL = None

# Render Production
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
CACHE_TYPE = 'redis'
CELERY_BROKER_URL = os.environ.get('REDIS_URL')
```

## Error Handling

### Translation Fallbacks

1. **Missing Translation:** Fallback to English
2. **Missing .mo File:** Use .po file directly
3. **Compilation Errors:** Show detailed error messages
4. **Language Detection:** Default to English if invalid language

### Script Error Handling

1. **Virtual Environment:** Check and activate automatically
2. **File Permissions:** Verify write access to translation directories
3. **Babel Installation:** Verify PyBabel is installed
4. **Command Failures:** Provide clear error messages and suggestions

## Testing Strategy

### Translation System Tests

1. **Unit Tests:**
   - Translation function tests
   - Language switching tests
   - Fallback mechanism tests

2. **Integration Tests:**
   - Full translation workflow
   - Script execution tests
   - Environment switching tests

3. **Manual Tests:**
   - UI language switching
   - All pages translation verification
   - Error message translation verification

### Script Testing

1. **PowerShell Script Tests:**
   - Extract messages functionality
   - Update translations functionality
   - Compile translations functionality
   - Error handling scenarios

2. **Environment Tests:**
   - Local SQLite mode
   - Render PostgreSQL mode
   - Configuration switching

## Implementation Plan

### Phase 1: Fix Translation Compilation
- Verify and fix .po files
- Compile all .mo files
- Test translation loading

### Phase 2: Create Startup Commands
- Create local development script
- Create Render deployment script
- Test environment switching

### Phase 3: Verify HTML Templates
- Check all templates for translation functions
- Add missing translations
- Test UI language switching

### Phase 4: Complete Translation Coverage
- Extract all messages
- Update all .po files
- Verify all translations are complete