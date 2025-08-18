#!/bin/bash

# SSL certificate setup script for AI Secretary
# This script sets up SSL certificates using Let's Encrypt

set -e

# Configuration
DOMAIN="${1:-yourdomain.com}"
EMAIL="${2:-admin@yourdomain.com}"
SSL_DIR="./deployment/nginx/ssl"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if domain and email are provided
if [ $# -lt 2 ]; then
    log_error "Usage: $0 <domain> <email>"
    log_error "Example: $0 yourdomain.com admin@yourdomain.com"
    exit 1
fi

# Create SSL directory
mkdir -p "${SSL_DIR}"

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    log_info "Installing certbot..."
    
    # Install certbot based on OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Ubuntu/Debian
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y certbot
        # CentOS/RHEL
        elif command -v yum &> /dev/null; then
            sudo yum install -y certbot
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install certbot
        fi
    fi
fi

# Generate SSL certificate
log_info "Generating SSL certificate for ${DOMAIN}..."

# Use standalone mode for initial certificate generation
certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "${EMAIL}" \
    -d "${DOMAIN}" \
    --cert-path "${SSL_DIR}/cert.pem" \
    --key-path "${SSL_DIR}/key.pem" \
    --fullchain-path "${SSL_DIR}/fullchain.pem" \
    --chain-path "${SSL_DIR}/chain.pem"

# Copy certificates to nginx directory
log_info "Copying certificates to nginx directory..."
sudo cp "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" "${SSL_DIR}/cert.pem"
sudo cp "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" "${SSL_DIR}/key.pem"

# Set proper permissions
sudo chown $(whoami):$(whoami) "${SSL_DIR}"/*.pem
chmod 644 "${SSL_DIR}/cert.pem"
chmod 600 "${SSL_DIR}/key.pem"

# Create certificate renewal script
log_info "Creating certificate renewal script..."
cat > "${SSL_DIR}/renew-cert.sh" << EOF
#!/bin/bash

# Certificate renewal script
certbot renew --quiet

# Copy renewed certificates
cp "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" "${SSL_DIR}/cert.pem"
cp "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" "${SSL_DIR}/key.pem"

# Reload nginx
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload

echo "Certificate renewed successfully!"
EOF

chmod +x "${SSL_DIR}/renew-cert.sh"

# Add cron job for automatic renewal
log_info "Setting up automatic certificate renewal..."
(crontab -l 2>/dev/null; echo "0 3 * * * ${PWD}/${SSL_DIR}/renew-cert.sh") | crontab -

log_info "SSL certificate setup completed!"
log_info "Certificate files:"
log_info "  - Certificate: ${SSL_DIR}/cert.pem"
log_info "  - Private key: ${SSL_DIR}/key.pem"
log_info "  - Renewal script: ${SSL_DIR}/renew-cert.sh"
log_info ""
log_info "Automatic renewal is set up via cron job."
log_info "Certificates will be renewed automatically every day at 3 AM."