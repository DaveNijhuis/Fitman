"""Optional features: what this instance has switched on (#326)."""

from fastapi import HTTPException, status

from config import settings


def require_scale_enabled() -> None:
    """Dependency for every smart scale endpoint: 404 unless SCALE_ENABLED.

    404 rather than 403 — with the feature off there is nothing there to be
    refused. Read per request, so nothing depends on import order.
    """
    if not settings.scale_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
