#!/bin/bash

# Generate secrets for production deployment
# This script generates secure random secrets for the application

set -e

echo "Generating secrets for AI Secretary production deployment..."

# Function to generate random string
generate_secret() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

# Generate secrets
SECRET_KEY=$(generate_secret)
JWT_SECRET_KEY=$(generate_secret)
POSTGRES_PASSWORD=$(generate_secret)
REDIS_PASSWORD=$(generate_secret)
GRAFANA_PASSWORD=$(generate_secret)

# Create secrets file
cat > .env.prod << EOF
# Generated secrets for production deployment
# Generated on: $(date)

# Flask Configuration
FLASK_ENV=production
SECRET_KEY=${SECRET_KEY}
JWT_SECRET_KEY=${JWT_SECRET_KEY}

# Database Configuration
DATABASE_URL=postgresql://ai_secretary_user:${POSTGRES_PASSWORD}@db:5432/ai_secretary
POSTGRES_USER=ai_secretary_user
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=ai_secretary

# Redis Configuration
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
REDIS_PASSWORD=${REDIS_PASSWORD}

# Monitoring Configuration
GRAFANA_USER=admin
GRAFANA_PASSWORD=${GRAFANA_PASSWORD}

# Rate Limiting Configuration
RATELIMIT_STORAGE_URL=redis://:${REDIS_PASSWORD}@redis:6379/1

# Session Configuration
SESSION_TYPE=redis
SESSION_REDIS=redis://:${REDIS_PASSWORD}@redis:6379/2

# Celery Configuration
CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/3
CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/4

# PLACEHOLDER VALUES - REPLACE WITH ACTUAL VALUES
OPENAI_API_KEY=your-openai-api-key
STRIPE_SECRET_KEY=sk_live_your-stripe-secret-key
STRIPE_PUBLISHABLE_KEY=pk_live_your-stripe-publishable-key
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/api/v1/channels/telegram/webhook
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
APP_NAME=AI Secretary
APP_URL=https://yourdomain.com
SUPPORT_EMAIL=support@yourdomain.com
MAX_CONTENT_LENGTH=104857600
UPLOAD_FOLDER=/app/uploads
LOG_LEVEL=INFO
LOG_FILE=/app/logs/app.log
WTF_CSRF_ENABLED=true
WTF_CSRF_TIME_LIMIT=3600
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
EOF

echo "Secrets generated and saved to .env.prod"
echo ""
echo "IMPORTANT: Please update the following placeholder values in .env.prod:"
echo "- OPENAI_API_KEY"
echo "- STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET"
echo "- GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET"
echo "- TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_URL"
echo "- MAIL_* settings"
echo "- APP_URL, SUPPORT_EMAIL"
echo "- CORS_ORIGINS"
echo ""
echo "Generated passwords:"
echo "Database password: ${POSTGRES_PASSWORD}"
echo "Redis password: ${REDIS_PASSWORD}"
echo "Grafana password: ${GRAFANA_PASSWORD}"
echo ""
echo "Keep these passwords secure!"