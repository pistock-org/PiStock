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
Shared infrastructure: paths, SQL engine, logger.

Centralizes what used to be at the top of main.py so that all the
services (services/*.py) share the SAME engine and the SAME paths
without a circular import back to main.
"""
import os
import logging

from sqlmodel import create_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pistock")

# Path configuration (adapt to your directory layout).
# BASE_DIR points to backend/app/ (the directory of this file).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "../../../data-pistock"))
CAD_DIR = os.path.join(DATA_DIR, "uploads", "cad")
IMG_DIR = os.path.join(DATA_DIR, "uploads", "img")
DB_PATH = os.path.join(DATA_DIR, "pistockdatabase.sqlite3")

# Make sure all the required directories exist
os.makedirs(CAD_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}")


def _delete_file_if_exists(rel_path: str | None):
    """Delete a file on disk from a path relative to DATA_DIR. Silent
    if the file does not exist or on an I/O error (we prefer not to
    crash over that)."""
    if not rel_path:
        return
    abs_path = os.path.join(DATA_DIR, rel_path)
    try:
        if os.path.isfile(abs_path):
            os.remove(abs_path)
            logger.info(f"Fichier supprime : {abs_path}")
    except OSError as e:
        logger.warning(f"Impossible de supprimer {abs_path} : {e}")
