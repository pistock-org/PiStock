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
Generation of readable, incremental identifiers:
  - project code (AAA..ZZZ, base 26 over 3 letters);
  - BOM code (B0001..B9999);
  - PLM version per part (aa..zz, base 26 over 2 letters).

Plus the `_get_current_plm` helper, which centralizes the "which
revision to display" rule (is_main, otherwise the most recent).
"""
from fastapi import HTTPException
from sqlmodel import Session, select

from model import Project, Bom, PLM


# ----------------------------------------------------------------------
#  PROJECT CODE GENERATION HELPERS
# ----------------------------------------------------------------------
# The project code is a "number" in base 26 over 3 positions:
#   AAA = 0, AAB = 1, ..., AAZ = 25, ABA = 26, ..., ZZZ = 17575.
# We manipulate it as an integer to increment it, then convert it back
# to a string. This approach is more robust than a character-by-character
# manipulation with carry handling.
PROJECT_CODE_MAX = 26 ** 3 - 1  # = 17575 -> "ZZZ"


def _code_to_int(code: str) -> int:
    """Convert 'AAA'->0, 'AAB'->1, ..., 'ZZZ'->17575."""
    return ((ord(code[0]) - ord("A")) * 676
            + (ord(code[1]) - ord("A")) * 26
            + (ord(code[2]) - ord("A")))


def _int_to_code(n: int) -> str:
    """Inverse of _code_to_int. n must be in [0, 17575]."""
    return (chr(ord("A") + n // 676)
            + chr(ord("A") + (n // 26) % 26)
            + chr(ord("A") + n % 26))


def _next_project_code(session: Session) -> str:
    """Compute the next available code. If no project exists yet:
    'AAA'. Otherwise: (existing max) + 1. Raises HTTPException if we go
    past 'ZZZ' (a very high limit in practice: 17576 projects)."""
    # Since all codes are 3 characters A-Z, the alphabetical order
    # coincides with the numerical order: a simple MAX(code) suffices.
    last = session.exec(
        select(Project.code).order_by(Project.code.desc()).limit(1)
    ).first()
    if last is None:
        return "AAA"
    next_n = _code_to_int(last) + 1
    if next_n > PROJECT_CODE_MAX:
        raise HTTPException(
            status_code=507,  # 507 Insufficient Storage
            detail="Limite de codes de collection atteinte (ZZZ)."
        )
    return _int_to_code(next_n)


# ----------------------------------------------------------------------
#  BOM CODE GENERATION HELPER
# ----------------------------------------------------------------------
# Format: 'B' + 4 zero-padded digits (B0001..B9999). The alphabetical
# order coincides with the numerical order thanks to zero-padding, so we
# can do a MAX(code) in SQL.
BOM_CODE_MAX = 9999


def _next_bom_code(session: Session) -> str:
    last = session.exec(
        select(Bom.code).order_by(Bom.code.desc()).limit(1)
    ).first()
    if last is None:
        return "B0001"
    # Extract the numeric part (after the 'B')
    try:
        n = int(last[1:])
    except (ValueError, IndexError):
        n = 0
    n += 1
    if n > BOM_CODE_MAX:
        raise HTTPException(
            status_code=507,
            detail="Limite de codes BOM atteinte (B9999)."
        )
    return f"B{n:04d}"


# ----------------------------------------------------------------------
#  PLM VERSION GENERATION HELPER
# ----------------------------------------------------------------------
# Same logic as the project codes, but over 2 lowercase letters
# (aa..zz, i.e. 676 versions max per part). Computed PER PART.
PLM_VERSION_MAX = 26 * 26 - 1  # = 675 -> "zz"


def _version_to_int(v: str) -> int:
    return (ord(v[0]) - ord("a")) * 26 + (ord(v[1]) - ord("a"))


def _int_to_version(n: int) -> str:
    return chr(ord("a") + n // 26) + chr(ord("a") + n % 26)


def _next_version_for_part(session: Session, part_id: int) -> str:
    """Return the next PLM version for a given part.
    First revision -> 'aa'. Otherwise: (existing max for this part) + 1."""
    last = session.exec(
        select(PLM.version)
        .where(PLM.id_parts == part_id)
        .order_by(PLM.version.desc())
        .limit(1)
    ).first()
    if last is None:
        return "aa"
    next_n = _version_to_int(last) + 1
    if next_n > PLM_VERSION_MAX:
        raise HTTPException(
            status_code=507,
            detail=f"Limite de versions PLM atteinte (zz) pour cette piece."
        )
    return _int_to_version(next_n)


def _get_current_plm(session: Session, part_id: int):
    """Return the "current" PLM revision of a part:
    - the one marked is_main=True if it exists
    - otherwise, the most recent by timestamp
    - None if the part has no PLM revision
    Centralizes the "which revision to display" logic to stay consistent
    across /parts/full, /parts/{id} and the dashboard."""
    main = session.exec(
        select(PLM)
        .where(PLM.id_parts == part_id)
        .where(PLM.is_main == True)  # noqa: E712 (SQLAlchemy needs ==)
    ).first()
    if main is not None:
        return main
    return session.exec(
        select(PLM)
        .where(PLM.id_parts == part_id)
        .order_by(PLM.timestamp.desc())
    ).first()
