# PiStock — PLM/inventory tool for FreeCAD-based workshops
# Copyright (C) 2026 GA3Dtech
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# (...) See https://www.gnu.org/licenses/agpl-3.0.html

"""
i18n module: loads translations via gettext, with a fallback on a
mini .po parser so the app can start without a compiled .mo.

Workflow:
- In dev: you edit the .po files, and the app loads them directly via
  the included fallback parser. No need to compile on every change.
- In prod: compile the .po files into .mo with
    msgfmt locales/fr/LC_MESSAGES/messages.po -o locales/fr/LC_MESSAGES/messages.mo
  (or pybabel compile -d locales). gettext then uses the .mo files,
  which are faster to load.

Usage:
    from i18n import _, set_lang, get_lang, AVAILABLE_LANGS
    label = _("Catalog")        # returns "Catalogue" if lang=fr

Convention: msgid values are IN ENGLISH. The fr.po files contain the
translations. The 'en' language needs no .po (msgid == msgstr).
"""
import os
import gettext as _gettext

# Directory where the locales live (relative to this file).
LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "locales")
DOMAIN = "messages"

# List of supported languages. The first one is used as the default
# if no preference is set elsewhere.
AVAILABLE_LANGS = [
    ("en", "English"),
    ("fr", "Français"),
    ("de", "Deutsch"),
]
DEFAULT_LANG = "en"

# Cache: one GNUTranslations per language, loaded on demand
_translations_cache: dict[str, _gettext.NullTranslations] = {}
# Globally active language (will be overwritten by set_lang)
_current_lang = DEFAULT_LANG


# ----------------------------------------------------------------------
#  MINI .po PARSER — to start up without having to compile the .mo
# ----------------------------------------------------------------------
def _parse_po_file(path: str) -> dict[str, str]:
    """Parse a basic .po file into a {msgid: msgstr} dict.
    Does not handle plurals, contexts, or structured comments — just
    simple msgid/msgstr pairs, which is more than enough for our
    use case."""
    result: dict[str, str] = {}
    if not os.path.isfile(path):
        return result

    state = None        # 'id' / 'str' / None
    cur_id_parts: list[str] = []
    cur_str_parts: list[str] = []

    def flush():
        msgid = "".join(cur_id_parts)
        msgstr = "".join(cur_str_parts)
        # Ignore the empty entry (the .po metadata header)
        if msgid and msgstr:
            result[msgid] = msgstr
        cur_id_parts.clear()
        cur_str_parts.clear()

    def unquote(s: str) -> str:
        # Strip the surrounding quotes and decode the escapes
        # \" \\ \n \t — enough for normal UI strings.
        s = s.strip()
        if s.startswith('"') and s.endswith('"'):
            s = s[1:-1]
        return (s.replace('\\n', '\n')
                .replace('\\t', '\t')
                .replace('\\"', '"')
                .replace('\\\\', '\\'))

    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.rstrip("\n")
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    # Empty line or comment: flush the current entry
                    if state is not None:
                        flush()
                        state = None
                    continue
                if stripped.startswith("msgid "):
                    if state is not None:
                        flush()
                    cur_id_parts.append(unquote(stripped[6:]))
                    state = "id"
                elif stripped.startswith("msgstr "):
                    cur_str_parts.append(unquote(stripped[7:]))
                    state = "str"
                elif stripped.startswith('"'):
                    # Multi-line continuation of a msgid or msgstr
                    chunk = unquote(stripped)
                    if state == "id":
                        cur_id_parts.append(chunk)
                    elif state == "str":
                        cur_str_parts.append(chunk)
            # Final flush
            if state is not None:
                flush()
    except OSError:
        pass
    return result


class _DictTranslations(_gettext.NullTranslations):
    """Adapter that exposes a {msgid: msgstr} dict via the gettext API."""
    def __init__(self, mapping: dict[str, str]):
        super().__init__()
        self._mapping = mapping

    def gettext(self, message: str) -> str:
        return self._mapping.get(message, message)


# ----------------------------------------------------------------------
#  LOADING TRANSLATIONS
# ----------------------------------------------------------------------
def _load_translation(lang: str) -> _gettext.NullTranslations:
    """Load a language: tries the .mo (standard gettext, fast),
    falling back to the .po parsed in Python."""
    if lang in _translations_cache:
        return _translations_cache[lang]

    # 1. Attempt the .mo via gettext.translation
    try:
        t = _gettext.translation(DOMAIN, LOCALES_DIR,
                                  languages=[lang], fallback=False)
        _translations_cache[lang] = t
        return t
    except (FileNotFoundError, OSError):
        pass

    # 2. Fallback: parse the .po directly
    po_path = os.path.join(LOCALES_DIR, lang, "LC_MESSAGES",
                            f"{DOMAIN}.po")
    mapping = _parse_po_file(po_path)
    t = _DictTranslations(mapping)
    _translations_cache[lang] = t
    return t


# ----------------------------------------------------------------------
#  PUBLIC API
# ----------------------------------------------------------------------
def set_lang(lang: str) -> None:
    """Set the active language globally for this process."""
    global _current_lang
    if lang not in {code for code, _label in AVAILABLE_LANGS}:
        lang = DEFAULT_LANG
    _current_lang = lang


def get_lang() -> str:
    """Return the active language."""
    return _current_lang


def _(message: str) -> str:
    """Translate a message into the active language. If no translation
    is available, return the original message (English by convention)."""
    return _load_translation(_current_lang).gettext(message)
