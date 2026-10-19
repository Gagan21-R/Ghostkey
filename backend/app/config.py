"""Central, forgiving configuration.

Values pasted into hosting dashboards (Railway, Render, …) often carry stray spaces, line breaks or quotes, or
use a slightly different variable name. Everything here is cleaned and has a safe default, so a typo produces
a clear log line instead of a crash or a confusing runtime error. Secret values are never logged."""
from __future__ import annotations

import hashlib
import os
import re

# Every spelling we accept for the DetectifAI key, in priority order.
DETECTIF_KEY_NAMES = ("DETECTIF_API_KEY", "DETECTIFAI_API_KEY", "DETECTIF_AI_API_KEY", "DETECTIFY_API_KEY", "DETECTIFY_AI_API_KEY",
                      "DETECTIFAI_KEY", "DETECTIF_KEY", "DETECTIFY_KEY")


def clean(raw: str | None) -> str:
    """Strip whitespace, line breaks and surrounding quotes."""
    return (raw or "").strip().strip("'\"").strip()


def env(name: str, default: str = "") -> str:
    v = clean(os.getenv(name))
    return v if v else default


def env_bool(name: str, default: bool) -> bool:
    v = env(name).lower()
    if not v:
        return default
    if v in ("1", "true", "yes", "on", "y"):
        return True
    if v in ("0", "false", "no", "off", "n"):
        return False
    print(f"[ghostkey] WARNING: {name}={v!r} is not a yes/no value; using {default}", flush=True)
    return default


def env_float(name: str, default: float) -> float:
    v = env(name)
    if not v:
        return default
    m = re.match(r"^\s*([0-9]*\.?[0-9]+)", v)  # tolerate "25MB", "7 days"
    if m:
        return float(m.group(1))
    print(f"[ghostkey] WARNING: {name}={v!r} is not a number; using {default}", flush=True)
    return default


def detectif_key() -> tuple[str, str | None]:
    """(key, variable name it came from). Also accepts any variable containing both DETECTIF and KEY."""
    for name in DETECTIF_KEY_NAMES:
        v = env(name)
        if v:
            return v, name
    for name, raw in sorted(os.environ.items()):
        if "DETECTIF" in name.upper() and "KEY" in name.upper() and clean(raw):
            return clean(raw), name
    return "", None


def detectif_base_url() -> str:
    url = env("DETECTIFAI_BASE_URL", "https://platform.detectif.ai") or env("DETECTIF_BASE_URL", "https://platform.detectif.ai")
    if not re.match(r"^https?://", url):
        url = "https://" + url
    url = url.rstrip("/")
    return url[:-3] if url.endswith("/v1") else url


def secret_values() -> list[str]:
    """Every configured secret, for redaction in reports."""
    vals = [detectif_key()[0], env("GHOSTKEY_API_TOKEN")]
    vals += [clean(os.getenv(n)) for n in DETECTIF_KEY_NAMES]
    return [v for v in dict.fromkeys(vals) if v and len(v) >= 8]


def fingerprint(v: str) -> str:
    return hashlib.sha256((v or "").encode()).hexdigest()[:8]


def startup_summary() -> None:
    key, src = detectif_key()
    print("[ghostkey] config:"
          f" DetectifAI key={'found in ' + src if key else 'MISSING (set DETECTIF_API_KEY)'}"
          f" | base_url={detectif_base_url()}"
          f" | public_mode={env_bool('GHOSTKEY_PUBLIC', False)}"
          f" | downloads_picker={env_bool('GHOSTKEY_LOCAL_DOWNLOADS', True)}"
          f" | env={env('GHOSTKEY_ENV', 'local')}", flush=True)
    if not key:
        near = [n for n in os.environ if "DETECT" in n.upper() or "API_KEY" in n.upper()]
        if near:
            print(f"[ghostkey] hint: found these similar variable names but no usable key: {sorted(near)}", flush=True)
