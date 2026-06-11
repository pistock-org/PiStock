# PiStock — PLM/inventory tool for FreeCAD-based workshops
# Copyright (C) 2026 GA3Dtech
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Frontend extension points for plugins.

The core UI exposes a few well-defined "slots" that plugins can populate
without touching core code. Today there is one: a row of small badge
icons at the right end of every part row in the catalog. A plugin
registers a *provider* from its ``register(app)``; the catalog calls
every provider once per refresh and renders whatever they return.

This keeps the same moral contract as the rest of the plugin system:
plugins read the core DB freely and contribute UI through a narrow,
stable surface, and a misbehaving provider is logged but never breaks
the catalog.

Plugins reach this module with a plain ``import plugin_hooks`` (the
server adds ``frontend/`` to ``sys.path`` before loading plugins). They
should guard that import so an older core without this module still
loads the plugin:

    try:
        from plugin_hooks import register_part_badge_provider, PartBadge
    except ImportError:
        register_part_badge_provider = None
"""
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class PartBadge:
    """A small icon shown at the right end of a part row in the catalog.

    Attributes:
        icon: a Material icon name (e.g. ``"sticky_note_2"``). A single
            emoji glyph also works — it is rendered as a label.
        tooltip: hover text (already translated by the plugin).
        color: a Tailwind text-color class for the icon.
        on_click: optional callback invoked with the part dict when the
            badge is clicked. If ``None`` the badge is purely decorative.
    """
    icon: str
    tooltip: str = ""
    color: str = "text-gray-500"
    on_click: Optional[Callable[[dict], None]] = None


# A provider receives the FULL list of part dicts currently shown in the
# catalog (one call per refresh) and returns a mapping
# {part_id: PartBadge}. Receiving the whole list at once lets a plugin
# answer with a single bulk query instead of one query per row.
PartBadgeProvider = Callable[[list], dict]

_PART_BADGE_PROVIDERS: list = []


def register_part_badge_provider(provider: PartBadgeProvider) -> None:
    """Register a part-row badge provider. Call this from a plugin's
    ``register(app)``. Idempotent for the same callable object."""
    if provider not in _PART_BADGE_PROVIDERS:
        _PART_BADGE_PROVIDERS.append(provider)


def collect_part_badges(parts: list) -> dict:
    """Run every registered provider once over ``parts`` and merge the
    results into ``{part_id: [PartBadge, ...]}``.

    A provider that raises is logged and skipped — it never prevents the
    other providers (or the catalog itself) from rendering.
    """
    badges: dict = {}
    for provider in _PART_BADGE_PROVIDERS:
        try:
            result = provider(parts) or {}
        except Exception as e:  # noqa: BLE001 — robustness over strictness
            print(f"⚠️  part-badge provider {provider!r} failed: {e}")
            continue
        for part_id, badge in result.items():
            badges.setdefault(part_id, []).append(badge)
    return badges
