# Environment Setup Guide

## .env File Configuration

The `.env` file contains all environment variables needed for development. Follow this guide to set up your local environment.

## Required Services

### 1. PostgreSQL Database

Install PostgreSQL and create the database:

```sql
-- Connect as postgres user
CREATE USER ai_secretary_user WITH PASSWORD 'ai_secretary_pass';
CREATE DATABASE ai_secretary OWNER ai_secretary_user;
CREATE DATABASE ai_secretary_test OWNER ai_secretary_user;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE ai_secretary TO ai_secretary_user;
GRANT ALL PRIVILEGES ON DATABASE ai_secretary_test TO ai_secretary_user;
```

Update in `.env`:
```env
DATABASE_URL=postgresql://ai_secretary_user:ai_secretary_pass@localhost:5432/ai_secretary
TEST_DATABASE_URL=postgresql://ai_secretary_user:ai_secretary_pass@localhost:5432/ai_secretary_test
```

### 2. Redis Server

Install and start Redis:

**Windows (using Chocolatey):**
```powershell
choco install redis-64
redis-server
```

**Or use Docker:**
```powershell
docker run -d -p 6379:6379 redis:alpine
```

Redis URLs in `.env` should work with default installation.

### 3. OpenAI API Key

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Create an account and get API key
3. Update in `.env`:
```env
OPENAI_API_KEY=sk-your-actual-openai-api-key-here
```

### 4. Stripe (for billing)

1. Create account at [Stripe](https://stripe.com/)
2. Get test API keys from dashboard
3. Update in `.env`:
```env
STRIPE_PUBLISHABLE_KEY=pk_test_your-actual-publishable-key
STRIPE_SECRET_KEY=sk_test_your-actual-secret-key
STRIPE_WEBHOOK_SECRET=whsec_your-actual-webhook-secret
```

## Optional Services

### Google Calendar Integration

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Calendar API
4. Create OAuth 2.0 credentials
5. Update in `.env`:
```env
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

### Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Create new bot with `/newbot`
3. Get bot token
4. Update in `.env`:
```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

### Signal Integration

1. Install signal-cli:
```powershell
# Download from https://github.com/AsamK/signal-cli/releases
# Extract and add to PATH
```

2. Register phone number:
```powershell
signal-cli -u +1234567890 register
signal-cli -u +1234567890 verify CODE
```

3. Update in `.env`:
```env
SIGNAL_PHONE_NUMBER=+1234567890
```

### Email Configuration

For Gmail with App Password:

1. Enable 2FA on Gmail
2. Generate App Password
3. Update in `.env`:
```env
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-16-character-app-password
```

## Security Keys

Generate secure keys for production:

```powershell
# Generate random keys
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

## Environment Variables Reference

### Required for Basic Functionality
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `SECRET_KEY` - Flask secret key
- `JWT_SECRET_KEY` - JWT signing key

### Required for AI Features
- `OPENAI_API_KEY` - OpenAI API key

### Required for Billing
- `STRIPE_SECRET_KEY` - Stripe secret key
- `STRIPE_PUBLISHABLE_KEY` - Stripe publishable key

### Optional Integrations
- `GOOGLE_CLIENT_ID` - Google OAuth client ID
- `GOOGLE_CLIENT_SECRET` - Google OAuth client secret
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `SIGNAL_PHONE_NUMBER` - Signal phone number
- `SMTP_USERNAME` - Email username
- `SMTP_PASSWORD` - Email password

## Validation

Test your configuration:

```powershell
# Test database connection
python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app import db
    print('Database connection: OK')
"

# Test Redis connection
python -c "
import redis
r = redis.from_url('redis://localhost:6379/0')
r.ping()
print('Redis connection: OK')
"

# Test OpenAI API
python -c "
import openai
import os
openai.api_key = os.getenv('OPENAI_API_KEY')
# This will fail if key is invalid
print('OpenAI API key: OK')
"
```

## Development vs Production

### Development (.env)
- Use `FLASK_ENV=development`
- Use `LOG_LEVEL=DEBUG`
- Use `LOG_FORMAT=text` for readable logs
- Use test API keys

### Production
- Use `FLASK_ENV=production`
- Use `LOG_LEVEL=INFO`
- Use `LOG_FORMAT=json` for structured logs
- Use production API keys
- Use strong secret keys
- Use SSL/TLS connections

## Troubleshooting

### Database Connection Issues
```powershell
# Test PostgreSQL connection
psql -h localhost -U ai_secretary_user -d ai_secretary
```

### Redis Connection Issues
```powershell
# Test Redis connection
redis-cli ping
```

### Permission Issues
Make sure the database user has proper permissions:
```sql
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ai_secretary TO ai_secretary_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA ai_secretary TO ai_secretary_user;
```

## Next Steps

After setting up `.env`:

1. Run setup script: `.\scripts\setup.ps1`
2. Initialize database: `.\scripts\init-db.ps1`
3. Start development server: `.\scripts\run-dev.ps1`
4. Start Celery worker: `.\scripts\run-celery.ps1`

## Security Notes

- Never commit `.env` file to version control
- Use different keys for development and production
- Rotate keys regularly in production
- Use environment-specific configurations
- Enable SSL/TLS in production