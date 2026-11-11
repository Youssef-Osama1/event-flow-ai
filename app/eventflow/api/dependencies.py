import secrets

from fastapi import Header, HTTPException, status

from eventflow.config import get_settings


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = get_settings().api_key
    if expected is None:
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected.get_secret_value()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
