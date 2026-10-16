"""FastAPI dependencies — reusable checks injected into routes."""

from fastapi import Header, HTTPException


async def verify_api_key(x_api_key: str = Header(...)) -> str:
    """Reject requests that don't send a valid API key.

    Usage in a route:
        @router.get("/something")
        async def my_route(_key: str = Depends(verify_api_key)):
            ...
    """
    from app.config import settings          # late import avoids circular

    if x_api_key != settings.t1_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key
