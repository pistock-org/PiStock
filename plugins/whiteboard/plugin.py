# PiStock plugin — Whiteboard (sticky notes)
# Copyright (C) 2026 GA3Dtech — AGPLv3
#
# A central, dead-simple sticky-note whiteboard. Each note has a bold
# title, a text body, optional hashtags and an optional attached image
# (e.g. a photo of a hand sketch). Full-text search filters notes by
# their content or hashtags. Several named boards are supported.
#
# Fully independent of the core: it owns its table (prefix
# plugin_whiteboard_*) and stores images under uploads/whiteboard/. It
# only uses the public `main` facade (main.engine, main.DATA_DIR) and
# ships its own translations, so it changes nothing in the base app.

import os
import json
import datetime

from sqlmodel import SQLModel, Field, Session, select


# ----------------------------------------------------------------------
#  Own table (created on load via checkfirst — see _ensure_table)
# ----------------------------------------------------------------------
class WhiteboardPostit(SQLModel, table=True):
    __tablename__ = "plugin_whiteboard_postit"
    id: int | None = Field(default=None, primary_key=True)
    board: str = Field(default="General", index=True)
    title: str = Field(default="")
    note: str = Field(default="")
    hashtags: str = Field(default="")          # free text, e.g. "#idea #urgent"
    # One or more relative image paths. Stored as a JSON list of strings
    # (e.g. '["uploads/whiteboard/a.jpg", ...]'). For backward compat, a
    # bare path string (legacy single-image notes) is still understood.
    image_path: str | None = Field(default=None)
    created_at: str = Field(default="")
    updated_at: str = Field(default="")


def _ensure_table():
    import main
    WhiteboardPostit.__table__.create(main.engine, checkfirst=True)


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _parse_images(value):
    """Read the image_path column into a list of relative paths.
    Accepts a JSON list (new format) or a bare path (legacy single image)."""
    if not value:
        return []
    value = value.strip()
    if value.startswith("["):
        try:
            return [str(p) for p in json.loads(value) if p]
        except Exception:
            return []
    return [value]


def _serialize_images(paths):
    """Pack a list of relative paths into the image_path column (JSON, or
    None when empty)."""
    paths = [p for p in (paths or []) if p]
    return json.dumps(paths) if paths else None


# ----------------------------------------------------------------------
#  Translations (en/fr/de), self-contained
# ----------------------------------------------------------------------
T = {
    "en": {
        "title": "Whiteboard", "plugins": "Plugins", "catalog": "Catalog",
        "board": "Board", "search": "Search (text or #hashtag)",
        "new_note": "+ New note", "empty": "No note yet — click « + New note ».",
        "no_match": "No note matches the search.",
        "note_title": "Title", "note_body": "Note",
        "hashtags": "Hashtags (e.g. #idea #urgent)",
        "image": "Image", "add_image": "Add image(s)",
        "remove_image": "Remove",
        "save": "Save", "cancel": "Cancel", "delete": "Delete", "edit": "Edit",
        "confirm_delete": "Delete this note?",
        "rename_board": "Rename board", "board_name": "Board name",
        "rename": "Rename",
        "move_note_hint": "Change the board to move this note to another one.",
        "default_board": "General",
    },
    "fr": {
        "title": "Tableau blanc", "plugins": "Plugins", "catalog": "Catalogue",
        "board": "Tableau", "search": "Rechercher (texte ou #hashtag)",
        "new_note": "+ Nouvelle note", "empty": "Aucune note — cliquez « + Nouvelle note ».",
        "no_match": "Aucune note ne correspond à la recherche.",
        "note_title": "Titre", "note_body": "Note",
        "hashtags": "Hashtags (ex. #idee #urgent)",
        "image": "Image", "add_image": "Ajouter une / des image(s)",
        "remove_image": "Retirer",
        "save": "Enregistrer", "cancel": "Annuler", "delete": "Supprimer", "edit": "Éditer",
        "confirm_delete": "Supprimer cette note ?",
        "rename_board": "Renommer le tableau", "board_name": "Nom du tableau",
        "rename": "Renommer",
        "move_note_hint": "Changez le tableau pour déplacer cette note vers un autre.",
        "default_board": "Général",
    },
    "de": {
        "title": "Whiteboard", "plugins": "Plugins", "catalog": "Katalog",
        "board": "Tafel", "search": "Suchen (Text oder #Hashtag)",
        "new_note": "+ Neue Notiz", "empty": "Noch keine Notiz — « + Neue Notiz » klicken.",
        "no_match": "Keine Notiz passt zur Suche.",
        "note_title": "Titel", "note_body": "Notiz",
        "hashtags": "Hashtags (z.B. #idee #dringend)",
        "image": "Bild", "add_image": "Bild(er) hinzufügen",
        "remove_image": "Entfernen",
        "save": "Speichern", "cancel": "Abbrechen", "delete": "Löschen", "edit": "Bearbeiten",
        "confirm_delete": "Diese Notiz löschen?",
        "rename_board": "Tafel umbenennen", "board_name": "Tafelname",
        "rename": "Umbenennen",
        "move_note_hint": "Tafel ändern, um diese Notiz zu verschieben.",
        "default_board": "Allgemein",
    },
}


def _tr(key, **kw):
    try:
        from i18n import get_lang
        lang = get_lang()
    except Exception:
        lang = "en"
    text = T.get(lang, T["en"]).get(key, T["en"].get(key, key))
    return text.format(**kw) if kw else text


# ----------------------------------------------------------------------
#  Data access
# ----------------------------------------------------------------------
def _boards():
    import main
    with Session(main.engine) as s:
        rows = s.exec(select(WhiteboardPostit.board).distinct()).all()
    boards = sorted({b for b in rows if b})
    return boards or [_tr("default_board")]


def _fetch(board, query=""):
    """Notes of a board, optionally filtered by a search term (substring
    in title / note / hashtags, case-insensitive; a leading # is ignored)."""
    import main
    term = (query or "").strip().lower().lstrip("#").strip()
    with Session(main.engine) as s:
        rows = s.exec(
            select(WhiteboardPostit)
            .where(WhiteboardPostit.board == board)
            .order_by(WhiteboardPostit.updated_at.desc())
        ).all()
        out = []
        for r in rows:
            if term:
                hay = f"{r.title}\n{r.note}\n{r.hashtags}".lower()
                if term not in hay:
                    continue
            out.append({"id": r.id, "title": r.title, "note": r.note,
                        "hashtags": r.hashtags, "board": r.board,
                        "images": _parse_images(r.image_path)})
        return out


def _save(board, title, note, hashtags, images, note_id=None):
    import main
    with Session(main.engine) as s:
        if note_id is not None:
            row = s.get(WhiteboardPostit, note_id)
            if row is None:
                return
        else:
            row = WhiteboardPostit(created_at=_now())
            s.add(row)
        row.board = board or _tr("default_board")
        row.title = (title or "").strip()
        row.note = (note or "").strip()
        row.hashtags = (hashtags or "").strip()
        row.image_path = _serialize_images(images)
        row.updated_at = _now()
        s.commit()


def _delete(note_id):
    import main
    with Session(main.engine) as s:
        row = s.get(WhiteboardPostit, note_id)
        if row is not None:
            s.delete(row)
            s.commit()


def _rename_board(old, new):
    """Rename a board by moving every one of its notes to `new`. Boards
    have no table of their own — they only exist through the `board`
    column — so a rename is a bulk update of that column. If `new`
    already names another board, the two boards merge (notes are pooled).
    Returns the effective board name to select. We do NOT bump
    updated_at, to preserve each note's ordering."""
    import main
    new = (new or "").strip()
    if not new or new == old:
        return old or new
    with Session(main.engine) as s:
        rows = s.exec(
            select(WhiteboardPostit).where(WhiteboardPostit.board == old)
        ).all()
        for r in rows:
            r.board = new
        s.commit()
    return new


def _img_dir():
    import main
    d = os.path.join(main.DATA_DIR, "uploads", "whiteboard")
    os.makedirs(d, exist_ok=True)
    return d


def _save_image(filename, content_bytes):
    base, ext = os.path.splitext(filename or "image.jpg")
    if not ext:
        ext = ".jpg"
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in base) or "image"
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = f"{safe}_{stamp}{ext}"
    with open(os.path.join(_img_dir(), name), "wb") as f:
        f.write(content_bytes)
    return f"uploads/whiteboard/{name}"


def _hashtag_chips(text):
    """Split a hashtags string into clean tokens (with a leading #)."""
    raw = (text or "").replace(",", " ").split()
    out = []
    for t in raw:
        t = t.strip().lstrip("#")
        if t:
            out.append("#" + t)
    return out


# ======================================================================
#  PAGE
# ======================================================================
def register(app):
    from nicegui import ui

    _ensure_table()

    @ui.page("/plugin/whiteboard")
    def whiteboard_page():
        with ui.header().classes("bg-stone-800 text-white shadow"):
            with ui.row().classes("w-full items-center gap-3"):
                ui.label("📌 " + _tr("title")).classes("text-xl font-medium")
                ui.element("div").classes("flex-grow")
                ui.button("← " + _tr("plugins"),
                          on_click=lambda: ui.navigate.to("/plugins")) \
                    .props("flat color=white").classes("text-sm")
                ui.button("🏠 " + _tr("catalog"),
                          on_click=lambda: ui.navigate.to("/catalog")) \
                    .props("flat color=white").classes("text-sm")

        # 'extra' tracks boards created in this session that have no note
        # yet — boards live only through the notes' `board` column, so an
        # empty board is invisible to _boards() (which reads the DB) until
        # its first note. We keep it here so it stays selectable and a
        # valid move target meanwhile.
        state = {"board": _boards()[0], "extra": set()}

        with ui.column().classes("max-w-6xl mx-auto p-4 w-full gap-3"):
            with ui.row().classes("w-full items-end gap-2 flex-wrap"):
                board_sel = ui.select(
                    options=_boards(), value=state["board"],
                    label=_tr("board"), with_input=True,
                    new_value_mode="add-unique").classes("min-w-[160px]")
                ui.button(icon="drive_file_rename_outline",
                          on_click=lambda: _open_rename_board()) \
                    .props("flat round dense").tooltip(_tr("rename_board"))
                search_in = ui.input(label=_tr("search")) \
                    .props("clearable dense").classes("min-w-[220px] flex-grow")
                ui.element("div").classes("flex-grow")
                ui.button(_tr("new_note"),
                          on_click=lambda: _open_editor()) \
                    .props("color=primary")

            grid = ui.column().classes("w-full")

            def board_options():
                """All selectable boards: those in the DB + session-created
                empty ones. Used by both the board selector and the note
                editor's move-to-board field."""
                return sorted(set(_boards()) | state["extra"])

            def _on_board_change():
                # A value typed into the selector (new_value_mode) creates a
                # board with no note yet: remember it so it stays listed and
                # can host the first note / receive moved notes.
                v = board_sel.value
                if v and v not in _boards():
                    state["extra"].add(v)
                board_sel.options = board_options()
                board_sel.update()
                render()

            def render():
                board = board_sel.value or state["board"]
                state["board"] = board
                notes = _fetch(board, search_in.value or "")
                grid.clear()
                with grid:
                    if not notes:
                        msg = _tr("no_match") if (search_in.value or "").strip() \
                            else _tr("empty")
                        ui.label(msg).classes("text-gray-500 italic p-6")
                        return
                    with ui.row().classes("w-full gap-3 items-start flex-wrap"):
                        for n in notes:
                            _render_note(n)

            def _render_note(n):
                with ui.card().classes(
                        "w-64 p-3 gap-1 bg-yellow-50 border border-yellow-200 "
                        "shadow-sm"):
                    with ui.row().classes("w-full items-start no-wrap gap-1"):
                        ui.label(n["title"] or "—") \
                            .classes("font-bold text-base flex-grow break-words")
                        ui.button(icon="edit",
                                  on_click=lambda nn=n: _open_editor(nn)) \
                            .props("flat round dense size=sm")
                        ui.button(icon="delete",
                                  on_click=lambda nn=n: _confirm_delete(nn)) \
                            .props("flat round dense size=sm color=negative")
                    imgs = n["images"]
                    if len(imgs) == 1:
                        ui.image("/" + imgs[0]) \
                            .classes("w-full rounded max-h-48 object-contain "
                                     "bg-white cursor-pointer") \
                            .on("click", lambda p=imgs[0]: _open_image(p))
                    elif imgs:
                        with ui.row().classes("w-full gap-1 flex-wrap"):
                            for p in imgs:
                                ui.image("/" + p) \
                                    .classes("w-[72px] h-[72px] object-cover rounded "
                                             "bg-white cursor-pointer") \
                                    .on("click", lambda pp=p: _open_image(pp))
                    if n["note"]:
                        ui.label(n["note"]) \
                            .classes("text-sm whitespace-pre-wrap break-words")
                    chips = _hashtag_chips(n["hashtags"])
                    if chips:
                        with ui.row().classes("gap-1 flex-wrap"):
                            for c in chips:
                                ui.label(c).classes(
                                    "text-xs bg-yellow-200 text-yellow-900 "
                                    "px-1.5 rounded cursor-pointer") \
                                    .on("click",
                                        lambda t=c: (search_in.set_value(t), render()))

            def _open_image(rel):
                zoom = {"k": 1.0}
                with ui.dialog().props("maximized") as dlg, \
                        ui.card().classes("p-0 bg-black w-screen h-screen"):
                    with ui.row().classes("w-full items-center gap-1 p-2 "
                                          "bg-stone-800 text-white"):
                        ui.button(icon="zoom_out",
                                  on_click=lambda: _apply(zoom["k"] - 0.25)) \
                            .props("flat round color=white")
                        pct = ui.label("100%").classes("w-14 text-center")
                        ui.button(icon="zoom_in",
                                  on_click=lambda: _apply(zoom["k"] + 0.25)) \
                            .props("flat round color=white")
                        ui.button(icon="fit_screen",
                                  on_click=lambda: _apply(1.0)) \
                            .props("flat round color=white")
                        ui.element("div").classes("flex-grow")
                        ui.button(icon="close", on_click=dlg.close) \
                            .props("flat round color=white")
                    pan = ui.element("div").classes(
                        "w-full overflow-auto flex items-center justify-center") \
                        .style("height: calc(100vh - 64px)")
                    with pan:
                        img = ui.image("/" + rel).classes("max-w-none") \
                            .style("transition: transform .05s linear;")

                    def _apply(k):
                        k = max(0.25, min(k, 8.0))
                        zoom["k"] = k
                        img.style(f"transform: scale({k}); "
                                  "transform-origin: center center;")
                        pct.set_text(f"{int(round(k * 100))}%")

                    def _wheel(e):
                        dy = (e.args or {}).get("deltaY", 0)
                        _apply(zoom["k"] * (0.9 if dy > 0 else 1.1))
                    pan.on("wheel.prevent", _wheel, ["deltaY"])
                    _apply(1.0)
                dlg.open()

            def _confirm_delete(n):
                with ui.dialog() as dlg, ui.card():
                    ui.label(_tr("confirm_delete")).classes("font-medium")
                    if n["title"]:
                        ui.label(n["title"]).classes("text-sm text-gray-600")
                    with ui.row().classes("w-full justify-end gap-2 mt-2"):
                        ui.button(_tr("cancel"), on_click=dlg.close).props("flat")

                        def do():
                            _delete(n["id"]); dlg.close(); render()
                        ui.button(_tr("delete"), on_click=do).props("color=negative")
                dlg.open()

            def _open_editor(existing=None):
                pending = {"images": list(existing["images"]) if existing else []}
                with ui.dialog() as dlg, ui.card().classes("min-w-[420px] gap-2"):
                    ui.label(_tr("edit") if existing else _tr("new_note")) \
                        .classes("text-lg font-medium")
                    title_in = ui.input(_tr("note_title"),
                                        value=existing["title"] if existing else "") \
                        .classes("w-full")
                    note_in = ui.textarea(_tr("note_body"),
                                          value=existing["note"] if existing else "") \
                        .classes("w-full").props("autogrow rows=4")
                    tags_in = ui.input(_tr("hashtags"),
                                       value=existing["hashtags"] if existing else "") \
                        .classes("w-full")

                    # Board selector: changing it MOVES the note to another
                    # board (or to a brand-new one via add-unique).
                    board_in = ui.select(
                        options=board_options(),
                        value=(existing["board"] if existing
                               else (board_sel.value or state["board"])),
                        label=_tr("board"), with_input=True,
                        new_value_mode="add-unique").classes("w-full")
                    ui.label(_tr("move_note_hint")) \
                        .classes("text-xs text-gray-500")

                    img_box = ui.row().classes("items-start gap-2 flex-wrap")

                    def render_img():
                        img_box.clear()
                        with img_box:
                            for p in pending["images"]:
                                with ui.column().classes("items-center gap-0"):
                                    ui.image("/" + p).classes(
                                        "w-24 h-24 object-cover rounded bg-white")

                                    def remove(pp=p):
                                        pending["images"] = [
                                            x for x in pending["images"] if x != pp]
                                        render_img()
                                    ui.button(_tr("remove_image"), on_click=remove) \
                                        .props("flat dense size=sm color=negative")
                    render_img()

                    async def on_upload(e):
                        # NiceGUI >= 3.x: the event carries a single FileUpload
                        # in e.file, and read() is async. With `multiple`, this
                        # fires once per selected file.
                        data = await e.file.read()
                        pending["images"].append(_save_image(e.file.name, data))
                        render_img()
                    ui.upload(label=_tr("add_image"), auto_upload=True,
                              multiple=True, on_upload=on_upload) \
                        .props('accept="image/*"').classes("w-full")

                    with ui.row().classes("w-full justify-end gap-2 mt-2"):
                        ui.button(_tr("cancel"), on_click=dlg.close).props("flat")

                        def save():
                            _save(board_in.value or board_sel.value
                                  or state["board"],
                                  title_in.value, note_in.value, tags_in.value,
                                  pending["images"],
                                  note_id=existing["id"] if existing else None)
                            # the chosen board now has a note: keep it in
                            # the session set too (harmless once in the DB).
                            chosen = (board_in.value or board_sel.value
                                      or state["board"])
                            if chosen:
                                state["extra"].add(chosen)
                            dlg.close()
                            board_sel.options = board_options()
                            board_sel.update()
                            render()
                        ui.button(_tr("save"), on_click=save).props("color=primary")
                dlg.open()

            def _open_rename_board():
                old = board_sel.value or state["board"]
                with ui.dialog() as dlg, ui.card().classes("min-w-[360px] gap-2"):
                    ui.label(_tr("rename_board")).classes("text-lg font-medium")
                    name_in = ui.input(_tr("board_name"), value=old) \
                        .classes("w-full")

                    def do():
                        new = _rename_board(old, name_in.value)
                        state["extra"].discard(old)
                        if new:
                            state["extra"].add(new)
                        dlg.close()
                        board_sel.value = new
                        board_sel.options = board_options()
                        board_sel.update()
                        state["board"] = new
                        render()
                    name_in.on("keydown.enter", lambda: do())
                    with ui.row().classes("w-full justify-end gap-2 mt-2"):
                        ui.button(_tr("cancel"), on_click=dlg.close).props("flat")
                        ui.button(_tr("rename"), on_click=do) \
                            .props("color=primary")
                dlg.open()

            board_sel.on_value_change(lambda: _on_board_change())
            search_in.on_value_change(lambda: render())
            render()
