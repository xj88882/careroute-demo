"""Authentication middleware for Admin (JWT) and Partner (API Key + HMAC)."""
import hashlib
import hmac
import time
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from config import settings

security = HTTPBearer(auto_error=False)


# ===================== ADMIN JWT AUTH =====================
def create_admin_token(admin_id: str, role: str) -> str:
    payload = {
        "sub": admin_id,
        "role": role,
        "exp": int(time.time()) + settings.JWT_EXPIRE_MINUTES * 60,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_admin_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization required")
    return decode_admin_token(credentials.credentials)


# ===================== PARTNER API KEY + HMAC AUTH =====================
async def verify_partner(request: Request) -> dict:
    """
    Validates partner requests using API Key + HMAC-SHA256 signature.
    Headers required:
      - X-API-Key: partner api key
      - X-Signature: HMAC-SHA256(secret, method+path+body_hash+timestamp)
      - X-Timestamp: unix timestamp
    """
    api_key = request.headers.get("X-API-Key")
    signature = request.headers.get("X-Signature")
    timestamp_str = request.headers.get("X-Timestamp")

    if not all([api_key, signature, timestamp_str]):
        raise HTTPException(status_code=401, detail="Missing auth headers")

    # Timestamp tolerance (anti-replay)
    try:
        ts = int(timestamp_str)
        if abs(int(time.time()) - ts) > settings.HMAC_TIMESTAMP_TOLERANCE:
            raise HTTPException(status_code=401, detail="Request expired")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp")

    # Look up secret by API key — in production, query DB
    # For now, use a mock mapping
    partner_secrets = {
        "crt_cits_key": "cits_secret_placeholder",
        "crt_pumch_key": "pumch_secret_placeholder",
    }
    secret = partner_secrets.get(api_key)
    if not secret:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Recompute signature
    body = await request.body()
    body_hash = hashlib.sha256(body).hexdigest() if body else ""
    message = f"{request.method}{request.url.path}{body_hash}{timestamp_str}"
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")

    return {"api_key": api_key}


def require_role(*roles: str):
    """RBAC dependency: require one of the specified admin roles."""
    async def checker(admin: dict = Depends(get_current_admin)):
        if admin.get("role") not in roles and "super_admin" not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return admin
    return checker
