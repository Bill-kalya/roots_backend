from fastapi import APIRouter, Request
import httpx

router = APIRouter()


@router.get("/v1/geo")
async def get_geo(request: Request):
    # Use the client's real IP, or X-Forwarded-For in production
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else None

    if not ip:
        return {"country_code": None}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"https://ipapi.co/{ip}/json/", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            # Fail soft if external IP geolocation is unreachable.
            return {"country_code": None, "ip": ip}

