"""Lightweight JSON-based translation engine.

Usage
-----
from app.i18n.translator import t

# Simple key
t("errors.not_found", locale="uk")
# → "Ресурс не знайдено"

# Template with variables (uses str.format_map)
t("recommendations.PREVENTIVE_OVERSPEND.action", locale="uk",
  category="Food & Dining", daily_reduction="120.00", remaining_days=8)
# → "Скоротіть щоденні витрати у «Food & Dining» на 120.00 ..."

Resolution order
----------------
1. Exact locale catalog.
2. English ("en") catalog as fallback.
3. The raw key itself if not found in either catalog.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TRANSLATIONS_DIR = Path(__file__).parent / "translations"
_SUPPORTED_LOCALES = ("uk", "en")

# Loaded once at import time; shallow copy is fine — never mutated after load.
_catalogs: dict[str, dict] = {}


def _load() -> None:
    for locale in _SUPPORTED_LOCALES:
        path = _TRANSLATIONS_DIR / f"{locale}.json"
        try:
            with open(path, encoding="utf-8") as fh:
                _catalogs[locale] = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.error("Failed to load translation catalog %s: %s", path, exc)
            _catalogs[locale] = {}


_load()


def _resolve(catalog: dict, key: str) -> str | None:
    """Walk a dot-separated key through a nested dict."""
    parts = key.split(".")
    node: Any = catalog
    for part in parts:
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node if isinstance(node, str) else None


def t(key: str, locale: str = "uk", **vars: Any) -> str:
    """Translate *key* to *locale*, interpolating *vars* via str.format_map.

    Parameters
    ----------
    key:
        Dot-separated translation key, e.g. ``"errors.not_found"`` or
        ``"recommendations.PREVENTIVE_OVERSPEND.action"``.
    locale:
        Two-letter locale code.  Unsupported locales fall back to ``"en"``.
    **vars:
        Named variables substituted into the template string.

    Returns
    -------
    str
        Translated (and interpolated) string.  Falls back to the raw *key*
        if no translation is found, so the API never returns an empty string.
    """
    effective_locale = locale if locale in _catalogs else "en"

    raw = _resolve(_catalogs.get(effective_locale, {}), key)
    if raw is None:
        raw = _resolve(_catalogs.get("en", {}), key)
    if raw is None:
        logger.debug("Missing translation key '%s' for locale '%s'.", key, locale)
        return key

    if not vars:
        return raw

    try:
        return raw.format_map(_FormatMap(vars))
    except (KeyError, ValueError) as exc:
        logger.warning("Translation format error for key '%s': %s", key, exc)
        return raw


def translate_category(slug: str | None, locale: str = "uk") -> str | None:
    """Return the localized category name for a given *slug*.

    Returns ``None`` when *slug* is ``None`` (user-created category with no slug).
    """
    if slug is None:
        return None
    return t(f"categories.{slug}", locale=locale)


class _FormatMap(dict):
    """dict subclass that returns the placeholder unchanged for missing keys."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"
