# PiStock plugin — BOM dépliée (hierarchical tree view)
# Copyright (C) 2026 GA3Dtech — AGPLv3
#
# First demonstration plugin: displays any BOM as a recursive indented
# tree, with a table of totals per leaf part at the bottom. Reads the
# core via main.engine + main._flatten_bom, and writes to no table.
#
# To enable it: this folder (plugins/bom_tree/) just needs to be present
# when the server starts. The core discovers it and calls register(app).

def register(app):
    """Entry point called by the core when the server starts.
    'app' is the FastAPI instance. We also have access to nicegui.ui
    via a standard import."""
    from nicegui import ui
    from i18n import _

    @ui.page("/plugin/bom_tree")
    def bom_tree_page():
        # Late imports: we make sure main is fully loaded by the time
        # the page is rendered.
        import main
        from sqlmodel import Session, select

        # --- Simple header, visually aligned with the rest ----
        # We do not reuse render_app_header from the core, to stay
        # independent; a plugin can perfectly well have a different
        # look if its author wishes.
        with ui.header().classes("bg-stone-800 text-white shadow"):
            with ui.row().classes("w-full items-center gap-3"):
                ui.label("🌳 " + _("Expanded BOM")) \
                    .classes("text-xl font-medium")
                ui.element("div").classes("flex-grow")
                ui.button("← " + _("Plugins"),
                           on_click=lambda: ui.navigate.to("/plugins")) \
                    .props("flat color=white").classes("text-sm")
                ui.button("🏠 " + _("Catalog"),
                           on_click=lambda: ui.navigate.to("/")) \
                    .props("flat color=white").classes("text-sm")

        # --- Fetch the list of BOMs for the selector ----------
        with Session(main.engine) as session:
            boms_rows = session.exec(
                select(main.Bom).order_by(main.Bom.code)
            ).all()
            bom_items = [
                {"id": b.id, "code": b.code,
                 "description": b.description or ""}
                for b in boms_rows
            ]

        with ui.column().classes("max-w-4xl mx-auto p-4 w-full gap-4"):
            if not bom_items:
                with ui.card().classes("w-full p-8 text-center"):
                    ui.label(_("No BOM in the database.")) \
                        .classes("text-gray-500 italic")
                    ui.label(_("Create a BOM from the catalog, then "
                               "come back here.")) \
                        .classes("text-sm text-gray-400")
                return

            # BOM selector
            ui.label(_("Choose a BOM to expand:")) \
                .classes("font-medium")
            bom_options = {
                b["id"]: (f"{b['code']} — {b['description'][:50]}"
                          if b["description"] else b["code"])
                for b in bom_items
            }
            selector = ui.select(options=bom_options,
                                  label=_("BOM"), with_input=True) \
                .classes("w-full")

            # Containers for the tree and the totals (re-filled on
            # every change of the selector)
            tree_container = ui.column().classes("w-full gap-0 mt-2")
            totals_container = ui.column().classes("w-full gap-1 mt-4")

            def render():
                """Rebuild the tree + the totals table for the
                selected BOM."""
                tree_container.clear()
                totals_container.clear()
                if not selector.value:
                    return
                bom_id = int(selector.value)

                with Session(main.engine) as session:
                    # --- 1. Hierarchical tree ------------------
                    with tree_container:
                        bom = session.get(main.Bom, bom_id)
                        ui.label("📋 " + _("{code} — {description}").format(
                                  code=bom.code,
                                  description=(bom.description
                                               or _("(no description)")))) \
                            .classes("text-lg font-bold border-b "
                                      "border-gray-300 pb-2 mb-2")
                        _render_subtree(session, bom_id, level=0,
                                          visited=set())

                    # --- 2. Totals per leaf part --------------
                    try:
                        totals = main._flatten_bom(session, bom_id)
                    except Exception as e:
                        with totals_container:
                            ui.label("⚠️ " + _("Error: {error}").format(
                                error=e)) \
                                .classes("text-red-600")
                        return

                    if not totals:
                        return

                    # Preload the part names
                    parts_by_id = {
                        p.id: p.part_name for p in session.exec(
                            select(main.Parts)
                            .where(main.Parts.id.in_(totals.keys()))
                        ).all()
                    }

                    with totals_container:
                        ui.label(_("Totals per leaf part")) \
                            .classes("text-lg font-bold border-b "
                                      "border-gray-300 pb-2 mt-2")
                        ui.label(_("To assemble 1× {code}, you need in "
                                   "total:").format(code=bom.code)) \
                            .classes("text-sm text-gray-600 mb-2")
                        # Sort by part name for readability
                        sorted_totals = sorted(
                            totals.items(),
                            key=lambda x: parts_by_id.get(x[0], "?").lower()
                        )
                        for pid, qty in sorted_totals:
                            name = parts_by_id.get(pid, f"#{pid}")
                            with ui.row().classes(
                                    "items-center gap-3 py-1 "
                                    "border-b border-gray-100"):
                                ui.label("📦").classes("text-sm")
                                ui.label(name) \
                                    .classes("text-sm flex-grow")
                                ui.label(f"×{qty}") \
                                    .classes("text-sm font-mono "
                                              "font-bold text-blue-700")

            selector.on_value_change(render)


def _render_subtree(session, bom_id, level, visited):
    """Recursively display the lines of a BOM with indentation.
    'visited' tracks the set of BOMs already traversed to avoid loops
    (a safety net; cycles are normally rejected at insertion time by
    the core)."""
    from nicegui import ui
    from i18n import _
    import main
    from sqlmodel import Session, select

    if bom_id in visited:
        with ui.row().classes("text-xs text-red-500 py-1") \
                .style(f"padding-left:{level * 24}px"):
            ui.label("⚠️ " + _("Cycle detected — display interrupted."))
        return
    visited = visited | {bom_id}

    lines = session.exec(
        select(main.BomLine).where(main.BomLine.id_bom == bom_id)
        .order_by(main.BomLine.id)
    ).all()
    # Preload the referenced parts and sub-BOMs
    part_ids = {l.id_parts for l in lines if l.id_parts is not None}
    subbom_ids = {l.id_subbom for l in lines if l.id_subbom is not None}
    parts_by_id = {
        p.id: p for p in session.exec(
            select(main.Parts).where(main.Parts.id.in_(part_ids))
        ).all()
    } if part_ids else {}
    subboms_by_id = {
        b.id: b for b in session.exec(
            select(main.Bom).where(main.Bom.id.in_(subbom_ids))
        ).all()
    } if subbom_ids else {}

    indent_px = (level + 1) * 24

    for line in lines:
        with ui.row().classes(
                "w-full items-center gap-2 py-1 hover:bg-stone-50 "
                "border-l-2 border-gray-200") \
                .style(f"padding-left:{indent_px}px"):
            if line.id_parts is not None:
                part = parts_by_id.get(line.id_parts)
                name = part.part_name if part else f"#{line.id_parts}"
                ui.label("📦").classes("text-sm")
                ui.label(name).classes("text-sm flex-grow")
                ui.label(f"×{line.quantity}") \
                    .classes("text-sm font-mono text-gray-700 "
                              "font-bold")
            elif line.id_subbom is not None:
                sub = subboms_by_id.get(line.id_subbom)
                ui.label("📋").classes("text-sm")
                code = sub.code if sub else "?"
                desc = (sub.description if sub else "") or \
                       _("(no description)")
                ui.label(code).classes(
                    "text-xs font-mono font-bold text-blue-700 "
                    "bg-blue-100 px-2 py-0.5 rounded")
                ui.label(desc).classes("text-sm flex-grow")
                ui.label(f"×{line.quantity}").classes(
                    "text-sm font-mono text-blue-700 font-bold")

        # Recurse into the sub-BOMs
        if line.id_subbom is not None:
            _render_subtree(session, line.id_subbom,
                             level + 1, visited)
