#!/usr/bin/env python3
"""Generate secure keys for .env file."""
import secrets
import string

def generate_secure_key(length=32):
    """Generate a secure random key."""
    return secrets.token_urlsafe(length)

def generate_password(length=16):
    """Generate a secure password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

if __name__ == '__main__':
    print("🔐 Secure Key Generator for AI Secretary")
    print("=" * 50)
    
    print("\n📋 Copy these values to your .env file:")
    print("-" * 30)
    
    print(f"SECRET_KEY={generate_secure_key(32)}")
    print(f"JWT_SECRET_KEY={generate_secure_key(32)}")
    
    print(f"\n🔑 Database password suggestion:")
    print(f"ai_secretary_pass -> {generate_password(16)}")
    
    print(f"\n⚠️  Remember to also configure:")
    print("- OPENAI_API_KEY (get from https://platform.openai.com/)")
    print("- STRIPE_SECRET_KEY (get from https://stripe.com/)")
    print("- Database credentials")
    
    print(f"\n✅ Keys generated successfully!")
    print("Update your .env file with these secure values.")