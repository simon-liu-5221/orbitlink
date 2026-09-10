"""Auth endpoints (specs GU-01 registration, PR-02 sign in).

The access token goes back in the JSON body — the frontend keeps it in memory
only. The refresh token goes back in an httpOnly cookie the frontend cannot
read (decision B1), scoped to this router's path so it is not attached to every
other API call.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import (
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_PATH,
    AppSettings,
    CurrentUser,
    DbSession,
    Email,
    RefreshCookie,
    rate_limit_login,
    rate_limit_register,
)
from app.api.schemas import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResendVerificationRequest,
    TokenResponse,
    UserOut,
)
from app.core.config import Settings
from app.db.models import User
from app.services import auth_service
from app.services.auth_service import IssuedTokens

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_INVALID_CREDENTIALS = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    detail={"error_code": "INVALID_CREDENTIALS", "message": "email or password is wrong"},
)
_INVALID_REFRESH = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    detail={
        "error_code": "INVALID_REFRESH_TOKEN",
        "message": "your session has expired, sign in again",
    },
)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageResponse,
    dependencies=[Depends(rate_limit_register)],
)
def register(
    body: RegisterRequest,
    db: DbSession,
    settings: AppSettings,
    email_backend: Email,
) -> MessageResponse:
    try:
        auth_service.register(
            db,
            email=str(body.email),
            username=body.username,
            password=body.password,
            settings=settings,
            email_backend=email_backend,
        )
    except auth_service.WeakPasswordError as exc:
        db.rollback()
        raise HTTPException(
            422,  # renamed in newer starlette; the number is the stable name
            detail={
                "error_code": "WEAK_PASSWORD",
                "message": str(exc),
                # every unmet requirement, not just the first (GU-01 AC-4)
                "problems": exc.problems,
            },
        ) from exc
    except auth_service.UsernameTakenError as exc:
        db.rollback()
        raise HTTPException(
            422,  # renamed in newer starlette; the number is the stable name
            detail={
                "error_code": "USERNAME_TAKEN",
                "message": "that username is taken, pick another",
            },
        ) from exc

    db.commit()
    # Identical body whether or not the email already had an account (GU-01 AC-3).
    return MessageResponse(message="check your inbox to confirm your email address")


@router.get("/verify", response_model=MessageResponse)
def verify_email(token: str, db: DbSession) -> MessageResponse:
    try:
        auth_service.verify_email(db, token=token)
    except auth_service.ExpiredTokenError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_410_GONE,
            detail={
                "error_code": "TOKEN_EXPIRED",
                "message": "this link has expired, request a new one",
            },
        ) from exc
    except auth_service.InvalidTokenError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "TOKEN_INVALID", "message": "this link is not valid"},
        ) from exc

    db.commit()
    return MessageResponse(message="email confirmed, you can sign in now")


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    body: ResendVerificationRequest,
    db: DbSession,
    settings: AppSettings,
    email_backend: Email,
) -> MessageResponse:
    auth_service.resend_verification(
        db, email=str(body.email), settings=settings, email_backend=email_backend
    )
    db.commit()
    # Same answer whether the address exists, is unknown, or is already verified.
    return MessageResponse(message="if that address needs confirming, a new link is on its way")


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit_login)])
def login(body: LoginRequest, db: DbSession, settings: AppSettings) -> JSONResponse:
    try:
        user, tokens = auth_service.login(
            db,
            email=str(body.email),
            password=body.password,
            remember=body.remember_me,
            settings=settings,
        )
    except auth_service.EmailNotVerifiedError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"error_code": "EMAIL_NOT_VERIFIED", "message": str(exc)},
        ) from exc
    except auth_service.InvalidCredentialsError as exc:
        db.rollback()
        raise _INVALID_CREDENTIALS from exc

    db.commit()
    return _session_response(user, tokens, settings)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    db: DbSession,
    settings: AppSettings,
    refresh_token: RefreshCookie = None,
) -> JSONResponse:
    if not refresh_token:
        raise _INVALID_REFRESH
    try:
        user, tokens = auth_service.refresh_session(
            db, refresh_token=refresh_token, settings=settings
        )
    except (auth_service.InvalidTokenError, auth_service.ExpiredTokenError) as exc:
        db.rollback()
        raise _INVALID_REFRESH from exc

    db.commit()
    return _session_response(user, tokens, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    db: DbSession,
    response: Response,
    refresh_token: RefreshCookie = None,
) -> None:
    auth_service.logout(db, refresh_token=refresh_token)
    db.commit()
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


# --- helpers ----------------------------------------------------------


def _session_response(user: User, tokens: IssuedTokens, settings: Settings) -> JSONResponse:
    payload = TokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        user=UserOut.model_validate(user),
    )
    response = JSONResponse(content=payload.model_dump(mode="json"))
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        tokens.refresh_token,
        max_age=tokens.refresh_expires_in,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path=REFRESH_COOKIE_PATH,
    )
    return response
