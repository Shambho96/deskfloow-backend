import base64
import hmac
import hashlib
import os
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings

def hash_password(password: str) -> str:
    """Hashes plain text password using bcrypt."""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain text password against bcrypt hash."""
    try:
        pwd_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False

def create_jwt_token(payload: Dict[str, Any], expires_minutes: Optional[int] = None) -> str:
    """Generates a signed JWT Access token."""
    to_encode = payload.copy()
    if "sub" in to_encode and to_encode["sub"] is not None:
        to_encode["sub"] = str(to_encode["sub"])
    if "type" not in to_encode:
        to_encode["type"] = "access"
    expire_delta = timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expire_delta
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(user_id: Any) -> str:
    """Generates a signed Refresh JWT token."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates a signed JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

# PII AES-256-GCM Encryption / Decryption Helpers
def _get_aes_key() -> bytes:
    """Helper to derive 32-byte key from PII_SECRET_KEY settings."""
    raw_key = settings.PII_SECRET_KEY.encode('utf-8')
    return hashlib.sha256(raw_key).digest()

def encrypt_phone(phone: str) -> str:
    """Encrypts phone number using AES-256-GCM."""
    if not phone:
        return ""
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, phone.encode('utf-8'), None)
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode('utf-8')

def decrypt_phone(encrypted_phone: str) -> str:
    """Decrypts AES-256-GCM encrypted phone number."""
    if not encrypted_phone:
        return ""
    try:
        combined = base64.b64decode(encrypted_phone.encode('utf-8'))
        nonce = combined[:12]
        ciphertext = combined[12:]
        key = _get_aes_key()
        aesgcm = AESGCM(key)
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted.decode('utf-8')
    except Exception:
        return ""

def hash_phone_blind(phone: str) -> str:
    """Computes deterministic HMAC-SHA256 hash for fast database searching."""
    if not phone:
        return ""
    cleaned = "".join(filter(str.isdigit, phone))
    return hmac.new(settings.PII_SECRET_KEY.encode('utf-8'), cleaned.encode('utf-8'), hashlib.sha256).hexdigest()
