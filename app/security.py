from fastapi import Header, HTTPException, status

from app.config import get_settings


def require_app_token(x_app_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.app_token:
        if settings.environment.lower() == "production":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="APP_TOKEN is required in production.",
            )
        return

    if x_app_token != settings.app_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-App-Token.")
