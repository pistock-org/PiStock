# PiStock plugin — Stock search
# Copyright (C) 2026 GA3Dtech — AGPLv3
#
# A standalone catalog view focused on STOCK. It mirrors the look of the
# main dashboard but shows every stock field (quantity, location, supply,
# datasheet, stock photo) plus the CAD thumbnail, and lets you search by:
#   - name fragment (case-insensitive substring),
#   - location fragment,
#   - quantity range (min .. max; empty min = 0, empty max = infinity).
# Quantities can be edited (add/remove) through a stock dialog identical
# in spirit to the one on the main view.
#
# IMPORTANT: this plugin changes NOTHING in the base app. It only reads
# and writes the database through the public `main` facade (main.engine,
# main.Parts/Stock, main._get_current_plm, main._get_or_create_stock) —
# exactly the surface a plugin is meant to use — and ships its OWN
# translations so it never touches the core's locale files.

# ----------------------------------------------------------------------
#  Self-contained translations (en/fr/de). We read the active language
#  from the core's i18n module but keep our own catalog so we don't have
#  to modify frontend/locales/*.po.
# ----------------------------------------------------------------------
T = {
    "en": {
        "title": "Stock search",
        "plugins": "Plugins", "catalog": "Catalog",
        "search_name": "Search by name",
        "search_loc": "Search by location",
        "search_supply": "Search by supplier",
        "qty_min": "Qty min", "qty_max": "Qty max",
        "qty_hint": "empty min = 0, empty max = ∞",
        "reset": "Reset",
        "count": "{n} part(s)",
        "none": "No part in the database yet.",
        "none_match": "No matching part.",
        "quantity": "Quantity", "location": "Location", "supply": "Supply",
        "datasheet": "Datasheet", "no_datasheet": "(no datasheet)",
        "no_thumb": "no CAD", "no_photo": "no photo",
        "edit_stock": "Stock", "open_3d": "Open in 3D",
        "dlg_title": "Stock — « {name} »",
        "loc_ph": "e.g.: Drawer A3, shelf 2",
        "supply_ph": "Supply URL, supplier, notes...",
        "save": "Save", "cancel": "Cancel",
        "saved": "Stock updated.", "notfound": "Part not found.",
        "neg": "Quantity cannot be negative.",
    },
    "fr": {
        "title": "Recherche stock",
        "plugins": "Plugins", "catalog": "Catalogue",
        "search_name": "Rechercher par nom",
        "search_loc": "Rechercher par emplacement",
        "search_supply": "Rechercher par fournisseur",
        "qty_min": "Qté min", "qty_max": "Qté max",
        "qty_hint": "min vide = 0, max vide = ∞",
        "reset": "Réinitialiser",
        "count": "{n} pièce(s)",
        "none": "Aucune pièce dans la base.",
        "none_match": "Aucune pièce ne correspond.",
        "quantity": "Quantité", "location": "Emplacement", "supply": "Approvisionnement",
        "datasheet": "Fiche technique", "no_datasheet": "(aucune fiche)",
        "no_thumb": "pas de CAO", "no_photo": "pas de photo",
        "edit_stock": "Stock", "open_3d": "Voir en 3D",
        "dlg_title": "Stock — « {name} »",
        "loc_ph": "ex : Tiroir A3, étagère 2",
        "supply_ph": "URL d'approvisionnement, fournisseur, notes...",
        "save": "Enregistrer", "cancel": "Annuler",
        "saved": "Stock mis à jour.", "notfound": "Pièce introuvable.",
        "neg": "La quantité ne peut pas être négative.",
    },
    "de": {
        "title": "Bestandssuche",
        "plugins": "Plugins", "catalog": "Katalog",
        "search_name": "Nach Name suchen",
        "search_loc": "Nach Lagerort suchen",
        "search_supply": "Nach Lieferant suchen",
        "qty_min": "Menge min", "qty_max": "Menge max",
        "qty_hint": "Min leer = 0, Max leer = ∞",
        "reset": "Zurücksetzen",
        "count": "{n} Teil(e)",
        "none": "Keine Teile in der Datenbank.",
        "none_match": "Kein passendes Teil.",
        "quantity": "Menge", "location": "Lagerort", "supply": "Beschaffung",
        "datasheet": "Datenblatt", "no_datasheet": "(kein Datenblatt)",
        "no_thumb": "kein CAD", "no_photo": "kein Foto",
        "edit_stock": "Bestand", "open_3d": "In 3D öffnen",
        "dlg_title": "Bestand — « {name} »",
        "loc_ph": "z.B.: Schublade A3, Regal 2",
        "supply_ph": "Bezugs-URL, Lieferant, Notizen...",
        "save": "Speichern", "cancel": "Abbrechen",
        "saved": "Bestand aktualisiert.", "notfound": "Teil nicht gefunden.",
        "neg": "Die Menge darf nicht negativ sein.",
    },
}


def _tr(key, **kw):
    """Translate a plugin string into the active UI language."""
    try:
        from i18n import get_lang
        lang = get_lang()
    except Exception:
        lang = "en"
    table = T.get(lang, T["en"])
    text = table.get(key, T["en"].get(key, key))
    return text.format(**kw) if kw else text


# ----------------------------------------------------------------------
#  Database access — only through the public `main` facade.
# ----------------------------------------------------------------------
def _fetch_rows():
    """Return one dict per part with all stock + CAD-thumbnail fields.
    Mirrors the enriched listing of the main view, but read directly via
    the core facade so the plugin stays decoupled from frontend/db.py."""
    import main
    from sqlmodel import Session, select
    with Session(main.engine) as session:
        parts = session.exec(
            select(main.Parts).order_by(main.Parts.part_name)
        ).all()
        rows = []
        for p in parts:
            plm = main._get_current_plm(session, p.id)
            stock = session.exec(
                select(main.Stock).where(main.Stock.id_parts == p.id)
            ).first()
            rows.append({
                "id": p.id,
                "name": p.part_name,
                "version": plm.version if plm else None,
                "thumb_url": (f"/{plm.path_2_thumbnail}"
                              if plm and plm.path_2_thumbnail else None),
                "quantity": stock.quantity if stock else 0,
                "location": (stock.location if stock else None) or "",
                "supply": (stock.supply if stock else None) or "",
                "doc_url": (f"/{stock.path_2_doc}"
                            if stock and stock.path_2_doc else None),
                "img_url": (f"/{stock.path_2_img}"
                            if stock and stock.path_2_img else None),
            })
        return rows


def _save_stock(part_id, quantity, location, supply):
    """Set the stock quantity/location/supply (absolute). Same semantics
    as the core: empty strings become NULL. Returns (ok, message)."""
    if quantity is None or quantity < 0:
        return False, _tr("neg")
    import main
    from sqlmodel import Session
    with Session(main.engine) as session:
        if session.get(main.Parts, part_id) is None:
            return False, _tr("notfound")
        row = main._get_or_create_stock(session, part_id)
        row.quantity = int(quantity)
        row.location = (location or "").strip() or None
        row.supply = (supply or "").strip() or None
        session.add(row)
        session.commit()
    return True, _tr("saved")


def register(app):
    """Entry point called by the core at startup. 'app' is the FastAPI
    instance; we only register a NiceGUI page on it."""
    from nicegui import ui

    @ui.page("/plugin/stock_search")
    def stock_search_page():
        # --- Header (own, visually aligned with the rest) -------------
        with ui.header().classes("bg-stone-800 text-white shadow"):
            with ui.row().classes("w-full items-center gap-3"):
                ui.label("🔎 " + _tr("title")).classes("text-xl font-medium")
                ui.element("div").classes("flex-grow")
                ui.button("← " + _tr("plugins"),
                          on_click=lambda: ui.navigate.to("/plugins")) \
                    .props("flat color=white").classes("text-sm")
                ui.button("🏠 " + _tr("catalog"),
                          on_click=lambda: ui.navigate.to("/catalog")) \
                    .props("flat color=white").classes("text-sm")

        rows = _fetch_rows()

        with ui.column().classes("max-w-5xl mx-auto p-4 w-full gap-3"):
            # --- Filter bar -------------------------------------------
            with ui.row().classes("w-full items-end gap-2 flex-wrap"):
                name_in = ui.input(label=_tr("search_name")) \
                    .props("clearable dense").classes("min-w-[200px] flex-grow")
                loc_in = ui.input(label=_tr("search_loc")) \
                    .props("clearable dense").classes("min-w-[180px]")
                supply_in = ui.input(label=_tr("search_supply")) \
                    .props("clearable dense").classes("min-w-[180px]")
                qmin_in = ui.number(label=_tr("qty_min"), min=0, step=1,
                                    format="%d") \
                    .props("clearable dense").classes("w-28")
                qmax_in = ui.number(label=_tr("qty_max"), min=0, step=1,
                                    format="%d") \
                    .props("clearable dense").classes("w-28")

                def reset_filters():
                    name_in.value = None
                    loc_in.value = None
                    supply_in.value = None
                    qmin_in.value = None
                    qmax_in.value = None
                    refresh()
                ui.button(icon="filter_alt_off", on_click=reset_filters) \
                    .props("flat dense").tooltip(_tr("reset"))

            ui.label(_tr("qty_hint")).classes("text-xs text-gray-400 -mt-2")

            count_label = ui.label("").classes("text-sm text-gray-600")
            list_container = ui.column().classes("w-full gap-2")

            # --- Filtering --------------------------------------------
            def filtered():
                name = (name_in.value or "").strip().lower()
                loc = (loc_in.value or "").strip().lower()
                sup = (supply_in.value or "").strip().lower()
                qmin = qmin_in.value
                qmax = qmax_in.value
                out = []
                for r in rows:
                    if name and name not in r["name"].lower():
                        continue
                    if loc and loc not in r["location"].lower():
                        continue
                    if sup and sup not in r["supply"].lower():
                        continue
                    q = r["quantity"] or 0
                    if qmin is not None and q < qmin:
                        continue
                    if qmax is not None and q > qmax:
                        continue
                    out.append(r)
                return out

            def refresh():
                items = filtered()
                count_label.text = _tr("count", n=len(items))
                list_container.clear()
                if not rows:
                    with list_container:
                        ui.label(_tr("none")) \
                            .classes("text-gray-500 text-center p-8")
                    return
                if not items:
                    with list_container:
                        ui.label(_tr("none_match")) \
                            .classes("text-gray-500 text-center p-8")
                    return
                for r in items:
                    with list_container:
                        _render_row(r, refresh)

            for w in (name_in, loc_in, supply_in, qmin_in, qmax_in):
                w.on_value_change(lambda: refresh())

            refresh()

    # ------------------------------------------------------------------
    #  Row + stock dialog (defined inside register so `ui` is in scope)
    # ------------------------------------------------------------------
    def _render_row(r, on_change):
        from nicegui import ui
        with ui.card().classes("w-full p-3"):
            with ui.row().classes("w-full items-center gap-3 no-wrap"):
                # CAD thumbnail (clickable -> 3D viewer)
                if r["thumb_url"]:
                    ui.image(r["thumb_url"]) \
                        .classes("w-20 h-20 object-contain bg-stone-100 "
                                 "rounded cursor-pointer flex-shrink-0") \
                        .on("click",
                            lambda rid=r["id"]: ui.navigate.to(f"/part/{rid}")) \
                        .tooltip(_tr("open_3d"))
                else:
                    ui.label(_tr("no_thumb")).classes(
                        "w-20 h-20 flex items-center justify-center "
                        "bg-stone-100 rounded text-xs text-gray-400 "
                        "flex-shrink-0 text-center")

                # Stock photo, right next to the CAD thumbnail
                if r["img_url"]:
                    ui.image(r["img_url"]) \
                        .classes("w-20 h-20 object-cover bg-stone-100 "
                                 "rounded flex-shrink-0")
                else:
                    ui.label(_tr("no_photo")).classes(
                        "w-20 h-20 flex items-center justify-center "
                        "bg-stone-50 rounded text-xs text-gray-300 "
                        "flex-shrink-0 text-center")

                # Name + version + location + supply
                with ui.column().classes("gap-0 flex-grow min-w-0"):
                    with ui.row().classes("items-baseline gap-2 no-wrap"):
                        ui.label(r["name"]).classes("text-base font-medium")
                        if r["version"]:
                            ui.label(r["version"]) \
                                .classes("text-xs font-mono text-gray-500")
                    if r["location"]:
                        ui.label("📍 " + r["location"]) \
                            .classes("text-xs text-gray-600 truncate")
                    if r["supply"]:
                        ui.label(r["supply"]) \
                            .classes("text-xs text-gray-400 truncate")
                    if r["doc_url"]:
                        ui.html(
                            f'<a href="{r["doc_url"]}" target="_blank" '
                            f'class="text-blue-600 hover:underline text-xs">'
                            f'📄 {_tr("datasheet")}</a>')
                    else:
                        ui.label(_tr("no_datasheet")) \
                            .classes("text-xs text-gray-300 italic")

                # Quantity badge (red when 0)
                qty = r["quantity"] or 0
                color = "bg-red-100 text-red-700" if qty == 0 \
                    else "bg-green-100 text-green-700"
                ui.label(str(qty)).classes(
                    f"{color} font-mono text-lg font-bold px-3 py-1 "
                    f"rounded flex-shrink-0 min-w-[3rem] text-center")

                # Stock button -> edit dialog (add/remove quantity)
                ui.button(icon="inventory_2",
                          on_click=lambda rr=r: _open_stock_dialog(rr, on_change)) \
                    .props("flat round dense color=primary") \
                    .classes("flex-shrink-0").tooltip(_tr("edit_stock"))

    def _open_stock_dialog(r, on_change):
        from nicegui import ui
        with ui.dialog() as dialog, ui.card().classes("min-w-[440px]"):
            ui.label(_tr("dlg_title", name=r["name"])) \
                .classes("text-lg font-medium")
            qty_input = ui.number(label=_tr("quantity"),
                                  value=r["quantity"] or 0,
                                  min=0, step=1, format="%d").classes("w-full")
            loc_input = ui.input(label=_tr("location"),
                                 value=r["location"] or "",
                                 placeholder=_tr("loc_ph")).classes("w-full")
            supply_input = ui.textarea(label=_tr("supply"),
                                       value=r["supply"] or "",
                                       placeholder=_tr("supply_ph")) \
                .classes("w-full").props("autogrow rows=3")

            def confirm():
                ok, msg = _save_stock(r["id"], int(qty_input.value or 0),
                                      loc_input.value, supply_input.value)
                ui.notify(msg, type="positive" if ok else "negative")
                if ok:
                    dialog.close()
                    on_change()

            with ui.row().classes("w-full justify-end gap-2 mt-3"):
                ui.button(_tr("cancel"), on_click=dialog.close).props("flat")
                ui.button(_tr("save"), on_click=confirm).props("color=primary")
        dialog.open()
