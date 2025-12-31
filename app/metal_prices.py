import time
import httpx
from .settings import settings

_CACHE = {"ts": 0.0, "data": None}

async def fetch_metals_per_gram(currency: str = "USD") -> dict:
    if not settings.METALS_DEV_API_KEY:
        raise RuntimeError("Missing METALS_DEV_API_KEY in .env")

    # Metals.dev latest endpoint, request grams
    url = "https://api.metals.dev/v1/latest"
    params = {
        "api_key": settings.METALS_DEV_API_KEY,
        "currency": currency,
        "unit": "g",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def get_metals_per_gram(currency: str = "USD", cache_seconds: int = 60) -> dict:
    now = time.time()
    if _CACHE["data"] is not None and (now - _CACHE["ts"]) < cache_seconds:
        return _CACHE["data"]

    data = await fetch_metals_per_gram(currency)
    _CACHE["ts"] = now
    _CACHE["data"] = data
    return data

def alloy_factor(metal: str, alloy: str) -> float:
    metal = (metal or "").upper()
    alloy = (alloy or "").upper()

    if metal == "GOLD":
        k = float(alloy.replace("K", ""))
        return k / 24.0

    if metal == "SILVER":
        return 0.925 if alloy in ("925", "STERLING") else 1.0

    if metal == "PLATINUM":
        return 0.95 if alloy in ("PT950", "950") else 1.0

    return 1.0

