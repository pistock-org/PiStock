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

"""Header common to all pages: title, home/refresh button, admin
indicator, language selector and AGPLv3 source link.
"""
from nicegui import ui, app
from i18n import _, get_lang, AVAILABLE_LANGS
from app_core import SOURCE_CODE_URL
from components.admin import (_admin_configured, _session_admin_active, _clear_session_admin, _open_admin_login_dialog, _open_admin_change_password_dialog)


def render_app_header(title_key: str, show_home: bool = False):
    """Header common to all pages: title on the left, language selector
    and link to the source code on the right (AGPLv3 obligation).

    'title_key' is a msgid that will be translated via _().
    'show_home' shows a 🏠 button to the catalog (defaults to False:
    the catalog page itself must not display it)."""
    with ui.header().classes("bg-stone-800 text-white shadow"):
        with ui.row().classes("w-full items-center no-wrap gap-3"):
            ui.label(_(title_key)).classes("text-xl font-medium")
            ui.element("div").classes("flex-grow")  # spacer

            # --- Back-to-catalog button (secondary pages only)
            if show_home:
                ui.button(icon="home",
                           on_click=lambda: ui.navigate.to("/")) \
                    .props("flat round dense color=white") \
                    .tooltip(_("Back to catalog"))

            # --- Refresh button (all pages) ---------------------------
            # Reloads the current page. Simpler for the end user than F5
            # and does not lose the navigation (URL unchanged).
            ui.button(icon="refresh",
                       on_click=lambda: ui.navigate.reload()) \
                .props("flat round dense color=white") \
                .tooltip(_("Refresh the page"))

            # --- Admin indicator ---------------------------------
            # 3 visual states:
            #   - admin active            -> green icon + menu (change pwd, logout)
            #   - admin configured, inactive -> grey icon, opens the login
            #   - no admin configured     -> nothing (the setup opens by itself)
            if _admin_configured():
                if _session_admin_active():
                    with ui.button(icon="admin_panel_settings") \
                            .props("flat round dense color=green-3") \
                            .tooltip(_("Admin session active")):
                        with ui.menu():
                            ui.menu_item(
                                _("Change password"),
                                on_click=_open_admin_change_password_dialog)
                            ui.menu_item(
                                _("Log out admin"),
                                on_click=lambda: (
                                    _clear_session_admin(),
                                    ui.notify(_("Admin session ended."),
                                               type="info"),
                                    ui.navigate.reload(),
                                ))
                else:
                    ui.button(
                        icon="admin_panel_settings",
                        on_click=lambda: _open_admin_login_dialog(
                            on_success=lambda: ui.navigate.reload()),
                    ).props("flat round dense color=grey-5") \
                     .tooltip(_("Log in as admin"))

            # --- Language selector --------------------------------
            # EN/FR toggle. On change: store the preference on the
            # browser side and reload the page to apply it.
            current = get_lang()
            lang_options = {code: code.upper()
                             for code, _label in AVAILABLE_LANGS}

            def on_lang_change(e):
                new_lang = e.value
                # app.storage.user (server side) instead of
                # app.storage.browser (signed cookie, read-only outside
                # HTTP response construction).
                app.storage.user["lang"] = new_lang
                # Reload to rebuild the whole page in the new language.
                # Simpler and more reliable than an incremental rebuild
                # that would require tracking every widget containing
                # text.
                ui.navigate.reload()

            ui.toggle(lang_options, value=current,
                       on_change=on_lang_change) \
                .props("color=white dense").classes("text-sm")

            ui.link(_("Source code (AGPLv3)"),
                    SOURCE_CODE_URL,
                    new_tab=True) \
                .classes("text-stone-300 hover:text-white "
                          "text-sm no-underline")
