import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from .settings import settings

logger = logging.getLogger(__name__)

_DC_HOSTS = {
    "us": "com",
    "eu": "eu",
    "in": "in",
    "au": "com.au",
    "ca": "ca",
}

_token_cache: Dict[str, Any] = {"access_token": None, "expires_at": 0.0}


class ZohoNotConfigured(Exception):
    pass


class ZohoRequestError(Exception):
    pass


def zoho_is_configured() -> bool:
    return all([
        settings.ZOHO_CLIENT_ID,
        settings.ZOHO_CLIENT_SECRET,
        settings.ZOHO_REFRESH_TOKEN,
        settings.ZOHO_ORG_ID,
    ])


def _host(dc: str) -> str:
    return _DC_HOSTS.get(dc.lower(), "com")


def _accounts_base() -> str:
    return f"https://accounts.zoho.{_host(settings.ZOHO_DC)}"


def _books_base() -> str:
    return f"https://books.zoho.{_host(settings.ZOHO_DC)}"


def _require_config():
    if not zoho_is_configured():
        raise ZohoNotConfigured("Zoho Books credentials are not configured")


def _get_access_token() -> str:
    _require_config()
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 30:
        return _token_cache["access_token"]

    url = f"{_accounts_base()}/oauth/v2/token"
    data = {
        "refresh_token": settings.ZOHO_REFRESH_TOKEN,
        "client_id": settings.ZOHO_CLIENT_ID,
        "client_secret": settings.ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token",
    }
    resp = httpx.post(url, data=data, timeout=20)
    if resp.status_code != 200:
        raise ZohoRequestError(f"Zoho token refresh failed: {resp.status_code} {resp.text}")
    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise ZohoRequestError(f"Zoho token missing in response: {payload}")
    expires_in = int(payload.get("expires_in", 3600))
    _token_cache["access_token"] = token
    _token_cache["expires_at"] = now + expires_in
    return token


def _request(method: str, path: str, *, params: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _require_config()
    token = _get_access_token()
    params = params or {}
    params.setdefault("organization_id", settings.ZOHO_ORG_ID)

    url = f"{_books_base()}{path}"
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    resp = httpx.request(method, url, params=params, json=json, timeout=30)
    if resp.status_code >= 400:
        raise ZohoRequestError(f"Zoho request failed {resp.status_code}: {resp.text}")
    payload = resp.json()
    # Zoho Books returns code==0 on success
    code = payload.get("code")
    if code not in (0, None):
        raise ZohoRequestError(f"Zoho API error code {code}: {payload}")
    return payload


def find_contact_by_name(client_name: str) -> Optional[str]:
    params = {"contact_name": client_name}
    data = _request("GET", "/books/v3/contacts", params=params)
    contacts = data.get("contacts") or []
    if contacts:
        return contacts[0].get("contact_id")
    return None


def ensure_contact(client_name: str) -> Optional[str]:
    contact_id = find_contact_by_name(client_name)
    if contact_id:
        return contact_id

    payload = {
        "contact_name": client_name,
        "company_name": client_name,
    }
    data = _request("POST", "/books/v3/contacts", json=payload)
    contact = data.get("contact") or {}
    return contact.get("contact_id")


def create_invoice(contact_id: str, line_items: List[Dict[str, Any]], reference_number: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
    if not line_items:
        raise ZohoRequestError("Invoice requires at least one line item")

    payload: Dict[str, Any] = {
        "contact_id": contact_id,
        "line_items": line_items,
    }
    if reference_number:
        payload["reference_number"] = reference_number
    if notes:
        payload["notes"] = notes

    data = _request("POST", "/books/v3/invoices", json=payload)
    return data.get("invoice") or {}
