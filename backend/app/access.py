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

"""
Whole-UI "access" password — the front door of the web interface.

This is a SEPARATE, lower tier than the admin password:
  - the ACCESS password (here) is required to reach ANY page;
  - the ADMIN password (services/admin.py) is still required, on top,
    for destructive actions (deletes, unlock, db_admin plugin).

To avoid a database schema change, the access credential is stored in a
small JSON file inside DATA_DIR (alongside the database), not in a table.
It reuses the same PBKDF2 hashing as the admin password.
"""
import os
import json
import secrets
from datetime import datetime, timezone

from itsdangerous import URLSafeSerializer, BadSignature

from config import DATA_DIR
from services.admin import _hash_password, _new_salt, _verify_password

ACCESS_FILE = os.path.join(DATA_DIR, "access_password.json")
SECRET_FILE = os.path.join(DATA_DIR, ".access_secret")
COOKIE_NAME = "pistock_access"
MIN_LEN = 6


def is_configured() -> bool:
    """True once an access password has been set."""
    return os.path.isfile(ACCESS_FILE)


def setup(password: str):
    """Create the access password (first run only). Returns (ok, msg)."""
    if len(password) < MIN_LEN:
        return False, f"Le mot de passe doit faire au moins {MIN_LEN} caractères."
    if is_configured():
        return False, "Un mot de passe d'accès existe déjà."
    salt = _new_salt()
    payload = {
        "salt": salt.hex(),
        "hash": _hash_password(password, salt),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ACCESS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return True, "ok"


def verify(password: str) -> bool:
    """Constant-time check of an access password attempt."""
    if not password or not is_configured():
        return False
    try:
        with open(ACCESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _verify_password(password, data["salt"], data["hash"])
    except (OSError, KeyError, ValueError):
        return False


# ----------------------------------------------------------------------
#  Signed session cookie (proves the visitor entered the access password)
# ----------------------------------------------------------------------
# A per-instance random secret, persisted next to the database, signs the
# cookie. We never rely on NiceGUI's session storage for the gate (it is
# not reliably readable from a Starlette middleware under run_with).
def _get_secret() -> str:
    try:
        if os.path.isfile(SECRET_FILE):
            with open(SECRET_FILE, "r", encoding="utf-8") as f:
                s = f.read().strip()
            if s:
                return s
    except OSError:
        pass
    s = secrets.token_hex(32)
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SECRET_FILE, "w", encoding="utf-8") as f:
            f.write(s)
        os.chmod(SECRET_FILE, 0o600)
    except OSError:
        pass
    return s


def _serializer():
    return URLSafeSerializer(_get_secret(), salt="pistock-access")


def make_token() -> str:
    """Token to store in the access cookie after a successful login."""
    return _serializer().dumps("ok")


def check_token(token) -> bool:
    """Validate the access cookie token."""
    if not token:
        return False
    try:
        return _serializer().loads(token) == "ok"
    except (BadSignature, ValueError, TypeError):
        return False
