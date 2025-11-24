"""
Quick script to generate a secure JWT secret key
Run this to generate a secure secret for JWT_SECRET_KEY in your .env file
"""

import secrets

def generate_jwt_secret():
    """Generate a secure random string for JWT secret"""
    secret = secrets.token_urlsafe(32)
    print("\n" + "="*60)
    print("Generated JWT Secret Key:")
    print("="*60)
    print(secret)
    print("="*60)
    print("\nCopy this value and set it as JWT_SECRET_KEY in your .env file")
    print("Example:")
    print(f"JWT_SECRET_KEY={secret}")
    print("\n⚠️  Keep this secret secure and never commit it to version control!")
    print("="*60 + "\n")
    return secret

if __name__ == "__main__":
    generate_jwt_secret()

