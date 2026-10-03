"""Persistent store for user-entered CFC -> Tbgs conversion factors, backed by
Supabase (PostgREST over plain HTTPS — no extra client library needed).

Table `item_master_supplement`: item_name (PK), ctn_per_cfc, tbgs_per_ctn,
total_tbgs_per_cfc. Credentials come from `.streamlit/secrets.toml` locally
(gitignored) or the app's Secrets settings on Streamlit Cloud:

    [supabase]
    url = "https://<project>.supabase.co"
    key = "<publishable key>"

Every function degrades to "not configured / unreachable" instead of raising,
so the app keeps working from the bundled Excel files when Supabase isn't
available (paused free-tier project, no secrets, network down).
"""
from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

# Makes Python trust the OS certificate store (what Chrome/Windows use), so
# networks that re-sign HTTPS traffic with their own root CA don't break the
# connection with CERTIFICATE_VERIFY_FAILED. Harmless where it isn't needed.
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass

TABLE = "item_master_supplement"
TIMEOUT_SECONDS = 10
_EMPTY_COLUMNS = ["Item_Name", "Tbgs_Per_CFC"]


def _config() -> tuple[str, str] | None:
    try:
        cfg = st.secrets["supabase"]
        url = str(cfg["url"]).strip().rstrip("/")
        key = str(cfg["key"]).strip()
    except Exception:
        return None
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    return (url, key) if url and key else None


def is_configured() -> bool:
    return _config() is not None


def _headers(key: str, extra: dict | None = None) -> dict:
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if extra:
        headers.update(extra)
    return headers


@st.cache_data(ttl=60, show_spinner=False)
def fetch_factors() -> tuple[pd.DataFrame, str | None]:
    """All saved factors as (Item_Name, Tbgs_Per_CFC) — the same shape
    loaders.load_item_master_supplement() returns — plus an error string
    (None when fine or simply not configured)."""
    cfg = _config()
    if cfg is None:
        return pd.DataFrame(columns=_EMPTY_COLUMNS), None
    url, key = cfg
    try:
        resp = requests.get(
            f"{url}/rest/v1/{TABLE}",
            params={"select": "item_name,total_tbgs_per_cfc"},
            headers=_headers(key),
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        rows = resp.json()
    except Exception as exc:
        return pd.DataFrame(columns=_EMPTY_COLUMNS), f"{type(exc).__name__}"
    if not rows:
        return pd.DataFrame(columns=_EMPTY_COLUMNS), None
    raw = pd.DataFrame(rows)
    df = pd.DataFrame({
        "Item_Name": raw["item_name"].astype(str).str.strip(),
        "Tbgs_Per_CFC": pd.to_numeric(raw["total_tbgs_per_cfc"], errors="coerce"),
    }).dropna()
    return df, None


def save_factors(entries: list[tuple[str, float, float]]) -> str | None:
    """Upsert (item_name, ctn_per_cfc, tbgs_per_ctn) rows. Returns an error
    message, or None on success."""
    cfg = _config()
    if cfg is None:
        return "Supabase isn't configured."
    url, key = cfg
    payload = [
        {
            "item_name": name,
            "ctn_per_cfc": ctn,
            "tbgs_per_ctn": tbgs,
            "total_tbgs_per_cfc": ctn * tbgs,
        }
        for name, ctn, tbgs in entries
    ]
    try:
        resp = requests.post(
            f"{url}/rest/v1/{TABLE}",
            params={"on_conflict": "item_name"},
            json=payload,
            headers=_headers(key, {"Prefer": "resolution=merge-duplicates,return=minimal"}),
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except requests.HTTPError as exc:
        return f"Supabase rejected the save (HTTP {exc.response.status_code}): {exc.response.text[:200]}"
    except Exception as exc:
        return f"Couldn't reach Supabase ({type(exc).__name__})."
    fetch_factors.clear()
    return None
