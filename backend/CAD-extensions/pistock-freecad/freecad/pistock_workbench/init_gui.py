# PiStock — FreeCAD workbench (GUI init)
# Copyright (C) 2026 GA3Dtech — AGPLv3
#
# Namespace-package style (same layout as the FreeCAD workbench starter
# kit): FreeCAD imports freecad.pistock_workbench and runs this module,
# which registers the "PiStock" workbench, its toolbar and its menu.
#
# The three commands simply run the existing PiStock macros (which live
# next to this file). Each macro is executed with __file__ injected, so
# the macro's _macro_dir() resolves to THIS folder — where the
# deployment puts pistock_host.txt (server address) and pistock_ca.pem
# (the LAN TLS certificate). Nothing in the macros needs to change.

import os
import FreeCAD as App
import FreeCADGui as Gui

WB_DIR = os.path.dirname(os.path.abspath(__file__))
ICONPATH = os.path.join(WB_DIR, "resources", "icons")


def _run_macro(filename):
    """Execute a sibling .FCMacro as FreeCAD would, but with __file__ set
    to the macro's real path so it finds pistock_host.txt / pistock_ca.pem
    in this folder."""
    path = os.path.join(WB_DIR, filename)
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    namespace = {"__file__": path, "__name__": "__main__",
                 "__builtins__": __builtins__}
    exec(compile(source, path, "exec"), namespace)


class _PiStockCommand:
    """Generic FreeCAD command that runs one PiStock macro."""

    def __init__(self, macro, icon, menu_text, tooltip):
        self._macro = macro
        self._icon = icon
        self._menu_text = menu_text
        self._tooltip = tooltip

    def GetResources(self):
        return {
            "Pixmap": os.path.join(ICONPATH, self._icon),
            "MenuText": self._menu_text,
            "ToolTip": self._tooltip,
        }

    def Activated(self):
        try:
            _run_macro(self._macro)
        except Exception as exc:  # noqa: BLE001 — surface, never crash FreeCAD
            App.Console.PrintError("PiStock: {0}\n".format(exc))

    def IsActive(self):
        return True


Gui.addCommand("PiStock_Export", _PiStockCommand(
    "pistock_exporter.FCMacro", "pistock_exporter.svg",
    "Export part", "Export the active part (CAD + thumbnail + 3D) to PiStock"))
Gui.addCommand("PiStock_Explorer", _PiStockCommand(
    "pistock_explorer.FCMacro", "pistock_explorer.svg",
    "Browse catalog", "Browse and open parts stored in PiStock"))
Gui.addCommand("PiStock_LocalExplorer", _PiStockCommand(
    "pistock_local_explorer.FCMacro", "pistock_local_explorer.svg",
    "Browse local folder",
    "Explore a local master folder and its subfolders, with a small "
    "thumbnail per FreeCAD file"))
Gui.addCommand("PiStock_BomFromAssembly", _PiStockCommand(
    "pistock_bom_from_assembly.FCMacro", "pistock_bom_from_assembly.svg",
    "BOM from assembly", "Create a PiStock BOM from the active assembly"))
Gui.addCommand("PiStock_WrapBodies", _PiStockCommand(
    "pistock_wrap_bodies.FCMacro", "pistock_wrap_bodies.svg",
    "Wrap bodies into a Part",
    "Wrap every PartDesign Body of the active document into an App::Part "
    "named after the file"))

_COMMANDS = ["PiStock_WrapBodies", "PiStock_Export",
             "PiStock_Explorer", "PiStock_LocalExplorer",
             "PiStock_BomFromAssembly"]


class PiStockWorkbench(Gui.Workbench):
    """The PiStock workbench: a toolbar + menu for the three commands."""

    MenuText = "PiStock"
    ToolTip = "PiStock — PLM / inventory for FreeCAD workshops"
    Icon = os.path.join(ICONPATH, "pistock_explorer.svg")

    def Initialize(self):
        self.appendToolbar("PiStock", _COMMANDS)
        self.appendMenu("PiStock", _COMMANDS)

    def Activated(self):
        pass

    def Deactivated(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(PiStockWorkbench())
