# AI Secretary Setup & KYB Integration Plan

## 🎯 Обзор системы

AI Secretary - это интеллектуальная система, которая:
1. **Управляет коммуникациями** через множественные каналы
2. **Проверяет контрагентов** по открытым реестрам ЕС
3. **Мониторит изменения** и отправляет уведомления
4. **Интегрируется с CRM** для управления данными

## 📱 1. Настройка каналов коммуникации

### 1.1 Поддерживаемые каналы
- **📞 Телефон** - голосовые вызовы (LiveKit/Twilio)
- **📧 Email** - SMTP/IMAP интеграция
- **💬 Telegram** - Bot API
- **📘 Facebook** - Messenger API
- **📸 Instagram** - Business API
- **💚 WhatsApp** - Business API
- **🐦 X (Twitter)** - API v2
- **💼 LinkedIn** - Messaging API (если доступно)

### 1.2 Конфигурация каналов
```json
{
  "channels": {
    "phone": {
      "enabled": true,
      "provider": "livekit",
      "number": "+49123456789",
      "voice_settings": {
        "language": "de-DE",
        "voice": "neural",
        "speed": 1.0
      }
    },
    "email": {
      "enabled": true,
      "smtp_server": "smtp.gmail.com",
      "imap_server": "imap.gmail.com",
      "email": "secretary@company.com",
      "auto_reply": true
    },
    "telegram": {
      "enabled": true,
      "bot_token": "xxx",
      "webhook_url": "https://api.company.com/telegram"
    }
  }
}
```

## 🤖 2. AI Модель и инструкции

### 2.1 Системные инструкции
```
Ты - профессиональный AI секретарь компании {company_name}.

ОСНОВНАЯ ИНФОРМАЦИЯ О КОМПАНИИ:
- Название: {company_name}
- Адрес: {company_address}
- Телефон: {company_phone}
- Email: {company_email}
- Сфера деятельности: {business_area}

ТВОИ ЗАДАЧИ:
1. Отвечать на вопросы о компании
2. Записывать клиентов на встречи
3. Собирать контактную информацию
4. Проверять контрагентов в реестрах
5. Уведомлять о важных изменениях

СТИЛЬ ОБЩЕНИЯ:
- Профессиональный и дружелюбный
- Краткие и четкие ответы
- Всегда спрашивай разрешение перед записью данных

ОГРАНИЧЕНИЯ:
- Не разглашай конфиденциальную информацию
- Не принимай финансовые решения
- При сомнениях - переадресуй к человеку
```

### 2.2 Векторное хранилище знаний
- **Документы компании** (устав, политики, FAQ)
- **Продукты/услуги** (каталоги, прайсы)
- **Процедуры** (как записаться, как оплатить)
- **Специализированная литература** (отраслевые знания)

## 🔍 3. KYB (Know Your Business) система

### 3.1 Проверяемые данные
- **Налоговый номер** (VAT ID)
- **Название компании**
- **Адрес регистрации**
- **Банковские реквизиты** (IBAN)
- **Руководители** (директора, бенефициары)
- **Лицензии** (если применимо)

### 3.2 Источники данных (ЕС)

#### 3.2.1 Налоговые реестры
- **VIES** (VAT Information Exchange System)
  - API: `https://ec.europa.eu/taxation_customs/vies/`
  - Проверка VAT номеров ЕС
  - Бесплатно, без ограничений

#### 3.2.2 Бизнес-реестры по странам
- **Германия**: Handelsregister
- **Франция**: INFOGREFFE
- **Нидерланды**: KVK (Kamer van Koophandel)
- **Австрия**: Firmenbuch
- **Италия**: Registro Imprese

#### 3.2.3 Санкционные списки
- **ЕС**: EU Consolidated List
- **OFAC** (США): Specially Designated Nationals
- **UN**: Security Council Sanctions List
- **Великобритания**: UK Sanctions List

#### 3.2.4 Судебные реестры
- **Банкротства**: Insolvency registers
- **Судебные дела**: Court records (где доступно)

### 3.3 API интеграции

#### 3.3.1 VIES API
```python
# Проверка VAT номера
GET https://ec.europa.eu/taxation_customs/vies/services/checkVatService
```

#### 3.3.2 GLEIF API (LEI коды)
```python
# Legal Entity Identifier
GET https://api.gleif.org/api/v1/lei-records/{lei}
```

#### 3.3.3 OpenSanctions API
```python
# Санкционные списки
GET https://api.opensanctions.org/search/{entity}
```

## 🏗️ 4. Архитектура системы

### 4.1 Компоненты
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Interface │    │   AI Secretary  │    │   KYB Service   │
│                 │    │                 │    │                 │
│ - Setup Form    │◄──►│ - Chat Engine   │◄──►│ - Registry APIs │
│ - Dashboard     │    │ - Vector Store  │    │ - Sanctions     │
│ - Monitoring    │    │ - Instructions  │    │ - Monitoring    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Channels      │    │   Database      │    │   Notifications │
│                 │    │                 │    │                 │
│ - Phone/Voice   │    │ - Companies     │    │ - Email Alerts  │
│ - Email         │    │ - Contacts      │    │ - Dashboard     │
│ - Telegram      │    │ - KYB Results   │    │ - Webhooks      │
│ - Social Media  │    │ - Conversations │    │ - SMS           │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 4.2 База данных

#### 4.2.1 Таблицы
```sql
-- Компании пользователей
CREATE TABLE companies (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    vat_number VARCHAR(50),
    address TEXT,
    phone VARCHAR(50),
    email VARCHAR(255),
    business_area VARCHAR(255),
    ai_instructions TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Каналы коммуникации
CREATE TABLE communication_channels (
    id UUID PRIMARY KEY,
    company_id UUID REFERENCES companies(id),
    channel_type VARCHAR(50), -- phone, email, telegram, etc.
    config JSONB, -- channel-specific configuration
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Контрагенты
CREATE TABLE counterparties (
    id UUID PRIMARY KEY,
    company_id UUID REFERENCES companies(id),
    name VARCHAR(255) NOT NULL,
    vat_number VARCHAR(50),
    address TEXT,
    country_code VARCHAR(2),
    status VARCHAR(50) DEFAULT 'active',
    risk_level VARCHAR(20) DEFAULT 'low',
    last_checked TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Результаты KYB проверок
CREATE TABLE kyb_checks (
    id UUID PRIMARY KEY,
    counterparty_id UUID REFERENCES counterparties(id),
    check_type VARCHAR(50), -- vat, sanctions, registry, etc.
    source VARCHAR(100), -- VIES, OFAC, etc.
    status VARCHAR(20), -- valid, invalid, not_found, error
    result JSONB, -- detailed results
    checked_at TIMESTAMP DEFAULT NOW()
);

-- Мониторинг изменений
CREATE TABLE change_monitoring (
    id UUID PRIMARY KEY,
    counterparty_id UUID REFERENCES counterparties(id),
    field_name VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    detected_at TIMESTAMP DEFAULT NOW(),
    notified BOOLEAN DEFAULT false
);

-- Векторное хранилище документов
CREATE TABLE knowledge_documents (
    id UUID PRIMARY KEY,
    company_id UUID REFERENCES companies(id),
    filename VARCHAR(255),
    content_type VARCHAR(100),
    file_size INTEGER,
    vector_embeddings VECTOR(1536), -- OpenAI embeddings
    metadata JSONB,
    uploaded_at TIMESTAMP DEFAULT NOW()
);
```

## 🎨 5. UI/UX дизайн

### 5.1 Страница настройки секретаря
```
┌─────────────────────────────────────────────────────────────┐
│                    🤖 AI Secretary Setup                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📋 Company Information                                     │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ Company Name    │  │ VAT Number      │                  │
│  └─────────────────┘  └─────────────────┘                  │
│  ┌─────────────────────────────────────────┐                │
│  │ Business Address                        │                │
│  └─────────────────────────────────────────┘                │
│                                                             │
│  📱 Communication Channels                                  │
│  ☑️ Phone: [+49123456789] [Voice Settings]                 │
│  ☑️ Email: [secretary@company.com] [SMTP Config]           │
│  ☑️ Telegram: [@company_bot] [Bot Token]                   │
│  ☐ WhatsApp: [Business Account] [API Key]                  │
│  ☐ Facebook: [Page ID] [Access Token]                      │
│                                                             │
│  🤖 AI Instructions                                         │
│  ┌─────────────────────────────────────────┐                │
│  │ System prompt for AI model...          │                │
│  │                                         │                │
│  │ [Template] [Preview] [Test]             │                │
│  └─────────────────────────────────────────┘                │
│                                                             │
│  📚 Knowledge Base                                          │
│  [📁 Upload Documents] [📊 Vector Status]                  │
│  • company_policy.pdf (✅ Processed)                       │
│  • product_catalog.pdf (⏳ Processing)                     │
│                                                             │
│  🔍 KYB Settings                                            │
│  ☑️ Auto-check new counterparties                          │
│  ☑️ Monitor changes daily                                   │
│  ☑️ Sanctions screening                                     │
│  Notification email: [admin@company.com]                   │
│                                                             │
│  [💾 Save Configuration] [🧪 Test Setup]                   │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 KYB Dashboard
```
┌─────────────────────────────────────────────────────────────┐
│                    🔍 KYB Dashboard                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📊 Overview                                                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │   156   │ │    12   │ │    3    │ │    0    │           │
│  │ Total   │ │ Checked │ │ Pending │ │ Risks   │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
│                                                             │
│  🔍 Quick Check                                             │
│  ┌─────────────────┐ [🔍 Check Now]                        │
│  │ VAT/Company ID  │                                       │
│  └─────────────────┘                                       │
│                                                             │
│  📋 Recent Checks                                           │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Company Name        │ Status │ Risk │ Last Check       │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │ ACME GmbH          │   ✅   │ Low  │ 2 hours ago     │ │
│  │ Beta Corp          │   ⚠️   │ Med  │ 1 day ago       │ │
│  │ Gamma Ltd          │   ❌   │ High │ 3 days ago      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                             │
│  🚨 Alerts & Changes                                        │
│  • ACME GmbH: Address changed (2 hours ago)                │
│  • Beta Corp: New sanctions match found (1 day ago)        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 6. План реализации

### Phase 1: Основа (2-3 недели)
1. **Модели данных** - создать таблицы БД
2. **Базовый UI** - страница настройки секретаря
3. **VIES интеграция** - проверка VAT номеров
4. **Простой KYB dashboard**

### Phase 2: Каналы коммуникации (3-4 недели)
1. **Email интеграция** - SMTP/IMAP
2. **Telegram Bot** - базовая функциональность
3. **AI инструкции** - система промптов
4. **Векторное хранилище** - загрузка документов

### Phase 3: Расширенный KYB (4-5 недель)
1. **Множественные реестры** - интеграция с национальными API
2. **Санкционные списки** - автоматическая проверка
3. **Мониторинг изменений** - фоновые задачи
4. **Уведомления** - email/SMS алерты

### Phase 4: Голосовые вызовы (3-4 недели)
1. **LiveKit интеграция** - голосовые вызовы
2. **Speech-to-Text** - распознавание речи
3. **Text-to-Speech** - синтез речи
4. **Диалоговая система** - управление разговором

### Phase 5: Социальные сети (2-3 недели)
1. **WhatsApp Business** - интеграция
2. **Facebook Messenger** - автоответы
3. **Instagram Direct** - если доступно
4. **X (Twitter)** - мониторинг упоминаний

## 🔧 7. Технические детали

### 7.1 Стек технологий
- **Backend**: Flask, SQLAlchemy, Celery
- **Database**: PostgreSQL + pgvector
- **AI**: OpenAI GPT-4, embeddings
- **Voice**: LiveKit, Whisper, TTS
- **Queue**: Redis, Celery
- **Frontend**: React/Vue.js (позже)

### 7.2 Внешние сервисы
- **OpenAI** - AI модель и embeddings
- **LiveKit** - голосовые вызовы
- **Twilio** - SMS уведомления
- **SendGrid** - email уведомления

## 📋 8. Следующие шаги

1. **Создать модели данных** для компаний и каналов
2. **Реализовать базовую страницу настройки**
3. **Интегрировать VIES API** для проверки VAT
4. **Создать KYB dashboard**
5. **Добавить систему уведомлений**

Хотите начать с какого-то конкретного компонента?