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
FastAPI entry point for PiStock.

This file is intentionally THIN: it merely assembles the application
from the domain modules.

  - The database schema lives in model.py (single source of truth,
    shared with init_db.py).
  - Paths, the SQL engine and the logger live in config.py.
  - The business logic and REST endpoints are split by domain in
    services/*.py (admin, projects, boms, parts, stock), each one
    exposing an APIRouter.
  - The NiceGUI interface is defined in frontend/ui.py and attaches to
    the SAME FastAPI 'app'.

COMPATIBILITY FACADE: below we re-export the models and the public
helpers (`main.Parts`, `main.engine`, `main._flatten_bom`...) because
the UI, the plugins (see plugins/bom_tree) and the test suite access
them via `import main`. Keeping these names avoids breaking those
consumers.

    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
import os
import sys

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel

# --- Shared infrastructure (paths, engine, logger, file utils) ---
from config import (  # noqa: F401  (re-export for main.X)
    engine, logger, BASE_DIR, DATA_DIR, CAD_DIR, IMG_DIR, DB_PATH,
    _delete_file_if_exists,
)

# --- Models (single source: model.py), re-exported for main.X ---
from model import (  # noqa: F401
    Parts, PLM, Stock, Project, Bom, BomLine, Admin,
)

# --- Business helpers re-exported (UI / plugins / tests facade) ---
from services.codes import (  # noqa: F401
    PROJECT_CODE_MAX, _code_to_int, _int_to_code, _next_project_code,
    BOM_CODE_MAX, _next_bom_code,
    PLM_VERSION_MAX, _version_to_int, _int_to_version, _next_version_for_part,
    _get_current_plm,
)
from services.admin import (  # noqa: F401
    PBKDF2_ITER, _new_salt, _hash_password, _verify_password,
    _get_admin, _check_admin_password, _require_admin,
)
from services.stock import _get_or_create_stock  # noqa: F401
from services.boms import _flatten_bom, _would_create_cycle  # noqa: F401
from services.parts import VALID_STATUSES, _check_not_locked  # noqa: F401

# --- Domain routers ---
from services import admin, projects, boms, stock, parts


app = FastAPI(title="PiStock PLM Receiver")

# The inclusion order does not affect routing: no static route is
# shadowed by a parameterized route across domains (and within
# parts.py, '/parts/full' is indeed declared before '/parts/{part_id}').
for _module in (admin, projects, boms, stock, parts):
    app.include_router(_module.router)


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)
    logger.info("Base de donnees initialisee.")


# ----------------------------------------------------------------------
#  STATIC FILES + NiceGUI INTERFACE
# ----------------------------------------------------------------------
# 1. Uploaded files (.png thumbnails, .glb models...) are served under
#    /uploads/. This is used both by the NiceGUI interface (to display
#    images) and by the 3D viewer (which loads the .glb via an HTTP URL,
#    not a disk path).
uploads_root = os.path.join(DATA_DIR, "uploads")
app.mount("/uploads", StaticFiles(directory=uploads_root), name="uploads")

# 2. Frontend static assets (model-viewer.min.js, etc.)
#    Allows serving JS libs locally rather than via a CDN
#    -> full autonomy without internet, and better control.
FRONTEND_STATIC = os.path.abspath(
    os.path.join(BASE_DIR, "../../frontend/static")
)
if os.path.isdir(FRONTEND_STATIC):
    app.mount("/static", StaticFiles(directory=FRONTEND_STATIC),
              name="frontend_static")
    logger.info(f"Static frontend assets servis depuis {FRONTEND_STATIC}")
else:
    logger.warning(f"Dossier static frontend introuvable : {FRONTEND_STATIC}. "
                    f"Le viewer 3D essaiera de charger depuis CDN.")

# 3. The NiceGUI interface is defined in frontend/ui.py and attaches to
#    the SAME FastAPI 'app'. So everything runs on the same port:
#    - http://127.0.0.1:8000/       -> NiceGUI dashboard
#    - http://127.0.0.1:8000/api/v1 -> REST endpoints (used by the macro)
#    - http://127.0.0.1:8000/uploads/... -> static files
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "../../frontend"))
if FRONTEND_DIR not in sys.path:
    sys.path.insert(0, FRONTEND_DIR)

try:
    # ui_module registers its pages on 'app' via @ui.page(...) and
    # calls ui.run_with(app) to wire NiceGUI into FastAPI.
    import ui as ui_module  # noqa: F401  (the import alone registers everything)
    logger.info("Interface NiceGUI chargee.")
except ImportError as e:
    logger.warning(f"Impossible de charger l'UI NiceGUI : {e}")
