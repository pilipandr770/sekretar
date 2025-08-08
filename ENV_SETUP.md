# 🚀 Quick Environment Setup

## ✅ .env File Created!

Your `.env` file has been created with secure keys. Here's what you need to do next:

### 1. 🗄️ Setup PostgreSQL Database

```sql
-- Run these commands in PostgreSQL:
CREATE USER ai_secretary_user WITH PASSWORD 'p*A2ZF$sJavyCGMR';
CREATE DATABASE ai_secretary OWNER ai_secretary_user;
CREATE DATABASE ai_secretary_test OWNER ai_secretary_user;
GRANT ALL PRIVILEGES ON DATABASE ai_secretary TO ai_secretary_user;
GRANT ALL PRIVILEGES ON DATABASE ai_secretary_test TO ai_secretary_user;
```

### 2. 🔴 Setup Redis

**Option A - Install Redis:**
```powershell
# Using Chocolatey
choco install redis-64
redis-server
```

**Option B - Use Docker:**
```powershell
docker run -d -p 6379:6379 redis:alpine
```

### 3. 🤖 Get OpenAI API Key (Required for AI features)

1. Go to https://platform.openai.com/
2. Create account and get API key
3. Replace in `.env`:
```env
OPENAI_API_KEY=sk-your-actual-openai-api-key-here
```

### 4. 💳 Setup Stripe (Optional - for billing)

1. Create account at https://stripe.com/
2. Get test API keys
3. Update in `.env`:
```env
STRIPE_SECRET_KEY=sk_test_your-actual-secret-key
STRIPE_PUBLISHABLE_KEY=pk_test_your-actual-publishable-key
```

## 🏃‍♂️ Quick Start

After setting up the services above:

```powershell
# 1. Install dependencies
.\scripts\setup.ps1

# 2. Initialize database
.\scripts\init-db.ps1

# 3. Start the application
.\scripts\run-dev.ps1

# 4. In another terminal, start Celery worker
.\scripts\run-celery.ps1
```

## 🔍 Validate Configuration

```powershell
# Check if everything is configured correctly
.\scripts\validate-env.ps1
```

## 📚 Need Help?

- **Full setup guide**: `docs/environment-setup.md`
- **Generate new keys**: `python scripts/generate-keys.py`
- **Translation status**: `.\scripts\check-translations.ps1`

## 🌍 Multi-language Support

The application supports:
- 🇺🇸 English (default)
- 🇩🇪 German (Deutsch)
- 🇺🇦 Ukrainian (Українська)

## ⚡ Current Status

✅ Environment file created with secure keys  
✅ Translation system ready (3 languages)  
✅ Multi-tenant architecture configured  
✅ PostgreSQL schema isolation ready  
⚠️ Need to configure external services (OpenAI, Stripe, etc.)  

---

**Next Step**: Configure PostgreSQL and Redis, then run `.\scripts\setup.ps1`