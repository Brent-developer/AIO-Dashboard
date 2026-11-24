from fastapi import APIRouter, HTTPException, status

from core.auth import decode_token, token_pair, verify_admin
from schemas import LoginRequest, RefreshRequest, TokenPair


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenPair)
async def login(credentials: LoginRequest) -> dict[str, str]:
    if not verify_admin(credentials.username, credentials.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return token_pair(credentials.username)


@router.post("/refresh", response_model=TokenPair)
async def refresh(request: RefreshRequest) -> dict[str, str]:
    subject = str(decode_token(request.refresh_token, "refresh")["sub"])
    return token_pair(subject)
