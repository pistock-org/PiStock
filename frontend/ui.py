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
Entry point for PiStock's NiceGUI interface.

This file is intentionally THIN. The UI has been split into:
  - app_core.py          -> cross-cutting helpers (language, PWA, source link)
  - components/header.py -> common header
  - components/admin.py  -> admin session + dialogs
  - db.py                -> database access layer
  - pages/dashboard.py   -> catalog page "/"
  - pages/part.py        -> detail/viewer page "/part/{id}"
  - pages/plugins.py     -> plugin loading + page "/plugins"

Attaches to the SAME FastAPI 'app' as the REST endpoints (defined in
backend/app/main.py): the @ui.page pages are served at the root of the
same server. Database access goes directly through the SQLModel models
(no internal HTTP) — see db.py.

Pages:
  /              -> catalog (list of parts)
  /part/{id}     -> 3D viewer of a part
  /plugins       -> plugin index
"""
from nicegui import ui

# Importing the page modules is enough to register their @ui.page with
# NiceGUI. The order does not matter.
import pages.dashboard  # noqa: F401  (registers "/")
import pages.part       # noqa: F401  (registers "/part/{id}")
import pages.plugins    # noqa: F401  (registers "/plugins")
from pages.plugins import _load_plugins


# ======================================================================
#  STARTUP
# ======================================================================
# Wires NiceGUI into the FastAPI 'app' defined in main.py. Our @ui.page
# pages are then accessible at the root of the same server.
# 'storage_secret' is mandatory as soon as ui.storage.user is used; we
# provide it as a precaution even though we don't use it here.
import main as _main_module

# Load the plugins BEFORE ui.run_with: the @ui.page declared in the
# plugins are only taken into account if they are registered before the
# server starts.
_load_plugins(_main_module.app)

ui.run_with(_main_module.app,
            title="PiStock",
            favicon="📦",
            storage_secret="pistock-dev-secret-change-me")
