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

"""Dynamic plugin loading (scan of plugins/) and index page
(/plugins) displaying the grid of loaded plugins.
"""
import json
import importlib.util as _importlib_util
from pathlib import Path
from nicegui import ui, app
from i18n import _, set_lang, get_lang, AVAILABLE_LANGS
from app_core import (_apply_user_lang, _register_pwa)
from components.header import render_app_header


# 'plugins/' folder at the root of the project (at the same level as
# frontend/ and backend/). Resolved from this file to be agnostic of
# the cwd. This module lives in frontend/pages/, hence the three
# '.parent' (pages -> frontend -> repo root).
PLUGINS_DIR = Path(__file__).resolve().parent.parent.parent / "plugins"

# Global list of the manifests of successfully loaded plugins. Used
# by the /plugins page to display the grid of cards.
PLUGINS_LIST: list[dict] = []


def _load_plugins(fastapi_app):
    """Scans PLUGINS_DIR and loads each valid plugin. Individual errors
    are logged but non-blocking (a broken plugin must not prevent the
    rest of the system from starting)."""
    global PLUGINS_LIST
    PLUGINS_LIST = []
    if not PLUGINS_DIR.is_dir():
        print(f"ℹ️  No plugins/ folder at {PLUGINS_DIR}, no "
              f"plugin loaded.")
        return
    for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        # We ignore files, hidden folders (_*, .*), and Python
        # __pycache__ directories.
        if not plugin_dir.is_dir():
            continue
        if plugin_dir.name.startswith(("_", ".")):
            continue
        manifest_path = plugin_dir / "manifest.json"
        plugin_py = plugin_dir / "plugin.py"
        if not manifest_path.is_file() or not plugin_py.is_file():
            print(f"⚠️  {plugin_dir.name} : manifest.json or plugin.py "
                  f"missing, plugin ignored.")
            continue
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            # Minimal validation: id, name, version required
            for key in ("id", "name", "version"):
                if not manifest.get(key):
                    raise ValueError(f"champ '{key}' manquant dans manifest")
            # Load plugin.py under a unique name to avoid collisions
            # with any other modules.
            mod_name = f"pistock_plugin_{manifest['id']}"
            spec = _importlib_util.spec_from_file_location(
                mod_name, plugin_py)
            module = _importlib_util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # The plugin must expose register(app). That is where it
            # registers its routes and pages.
            if not hasattr(module, "register"):
                raise ValueError("plugin.py doit definir register(app)")
            module.register(fastapi_app)
            PLUGINS_LIST.append(manifest)
            print(f"✔️  Plugin charge : {manifest['name']} "
                  f"(v{manifest['version']}) [{manifest['id']}]")
        except Exception as e:
            print(f"⚠️  Plugin '{plugin_dir.name}' non charge : {e}")
            import traceback
            traceback.print_exc()


@ui.page("/plugins")
def plugins_index_page():
    """Plugin index page: a grid of clickable cards. Each card links
    to /plugin/<id>. If no plugin is installed, a help message is
    displayed."""
    _apply_user_lang()
    _register_pwa()
    ui.page_title(_("PiStock — Plugins"))
    render_app_header(_("Plugins"), show_home=True)

    with ui.column().classes("max-w-5xl mx-auto p-4 w-full gap-4"):
        if not PLUGINS_LIST:
            with ui.card().classes("w-full p-8 text-center"):
                ui.label("🧩").classes("text-5xl mb-2")
                ui.label(_("No plugin installed")) \
                    .classes("text-lg font-medium")
                ui.label(_("Drop a plugin into the 'plugins/' folder "
                         "at the project root, then restart the "
                         "server.")).classes("text-sm text-gray-500 max-w-md mx-auto")
            return

        ui.label(_("{count} plugin(s) installed").format(count=len(PLUGINS_LIST))) \
            .classes("text-sm text-gray-500")

        with ui.row().classes("gap-4 flex-wrap justify-start"):
            for plugin in PLUGINS_LIST:
                # Clickable card: navigate to the plugin page
                pid = plugin["id"]
                def make_navigator(target=pid):
                    return lambda: ui.navigate.to(f"/plugin/{target}")
                with ui.card().classes(
                        "w-56 p-4 cursor-pointer hover:shadow-lg "
                        "transition") \
                        .on("click", make_navigator()):
                    ui.label(plugin.get("icon", "🧩")) \
                        .classes("text-5xl text-center w-full")
                    ui.label(plugin["name"]) \
                        .classes("text-base font-bold text-center w-full mt-2")
                    desc = plugin.get("description", "")
                    if desc:
                        ui.label(desc) \
                            .classes("text-xs text-gray-600 text-center")
                    with ui.row().classes(
                            "w-full justify-between mt-2 text-xs "
                            "text-gray-400"):
                        ui.label(f"v{plugin['version']}")
                        if plugin.get("author"):
                            ui.label(_("by {author}").format(author=plugin['author']))
