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
BOM endpoints (Bill of Materials) + hierarchy logic (sub-BOMs):
recursive flattening and cycle detection.

The `_flatten_bom` and `_would_create_cycle` helpers are also used by
the plugins (see plugins/bom_tree) through the main facade.
"""
from fastapi import APIRouter, Form, HTTPException, Depends
from sqlmodel import Session, select
from pydantic import BaseModel

from config import engine, logger
from model import Parts, Project, Bom, BomLine, Stock
from services.codes import _next_bom_code
from services.stock import _get_or_create_stock
from services.admin import _require_admin

router = APIRouter()


# ----------------------------------------------------------------------
#  BOM HELPERS: HIERARCHY (sub-BOMs)
# ----------------------------------------------------------------------
def _flatten_bom(session: Session, bom_id: int, factor: int = 1,
                  visited: set | None = None) -> dict[int, int]:
    """Recursively walks the BOM and returns a dict
    {part_id: total_quantity}, accumulating the requirements of sub-BOMs.

    'factor' multiplies everything (useful for stock-add/sub computations
    with a global factor). 'visited' keeps the set of BOM_IDs already
    traversed to avoid infinite loops (a safety net, even though
    _would_create_cycle normally prevents their creation).

    Example: if BOM A contains:
       - 5 vis-M3
       - 2x sub-BOM B (which contains 3 ecrou + 1 rondelle)
    then _flatten_bom(A, factor=1) returns:
       {vis-M3: 5, ecrou: 6, rondelle: 2}
    """
    if visited is None:
        visited = set()
    if bom_id in visited:
        # Cycle: should not happen, but we guard against it anyway.
        raise HTTPException(
            status_code=500,
            detail=f"Cycle detecte lors du parcours de la BOM "
                   f"(id={bom_id})."
        )
    visited = visited | {bom_id}

    totals: dict[int, int] = {}
    lines = session.exec(
        select(BomLine).where(BomLine.id_bom == bom_id)
    ).all()
    for line in lines:
        if line.id_parts is not None:
            delta = line.quantity * factor
            totals[line.id_parts] = totals.get(line.id_parts, 0) + delta
        elif line.id_subbom is not None:
            # Recursion: accumulate the requirements of the sub-BOM,
            # multiplied by the quantity on this line.
            sub_totals = _flatten_bom(
                session, line.id_subbom,
                factor=line.quantity * factor,
                visited=visited,
            )
            for pid, qty in sub_totals.items():
                totals[pid] = totals.get(pid, 0) + qty
        # Lines with NEITHER part NOR subbom are ignored (corrupt
        # data, but no reason to crash)
    return totals


def _would_create_cycle(session: Session, parent_bom_id: int,
                          candidate_subbom_id: int) -> bool:
    """Checks whether adding candidate_subbom_id as a sub-BOM of
    parent_bom_id would create a cycle. True = cycle detected (reject).

    Two cases:
    1. Self-reference: parent == candidate
    2. Parent is a direct or indirect ancestor of candidate
       (which would create a loop if the link is added)
    """
    if parent_bom_id == candidate_subbom_id:
        return True
    # DFS over candidate's descendants. If we reach parent, there is
    # already a path candidate -> ... -> parent, so adding
    # parent -> candidate would create a loop.
    stack = [candidate_subbom_id]
    visited = set()
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        sub_lines = session.exec(
            select(BomLine)
            .where(BomLine.id_bom == current)
            .where(BomLine.id_subbom.is_not(None))
        ).all()
        for line in sub_lines:
            if line.id_subbom == parent_bom_id:
                return True
            stack.append(line.id_subbom)
    return False


# ======================================================================
#  BOM ENDPOINTS
# ======================================================================
@router.get("/api/v1/boms")
def list_boms(project_code: str | None = None):
    """Lists the BOMs. Each entry includes the code, the description,
    the associated project (if linked), and the line count."""
    with Session(engine) as session:
        query = select(Bom).order_by(Bom.code)
        if project_code:
            project = session.exec(
                select(Project).where(Project.code == project_code)
            ).first()
            if project is None:
                return []
            query = query.where(Bom.id_project == project.id)
        boms = session.exec(query).all()
        # Preload project codes to avoid one query per BOM
        projects_by_id = {
            p.id: p.code
            for p in session.exec(select(Project)).all()
        }
        result = []
        for b in boms:
            # Count the lines (without loading the objects) to keep
            # the listing lightweight.
            n_lines = session.exec(
                select(BomLine).where(BomLine.id_bom == b.id)
            ).all()
            result.append({
                "id": b.id,
                "code": b.code,
                "description": b.description,
                "id_project": b.id_project,
                "project_code": projects_by_id.get(b.id_project),
                "line_count": len(n_lines),
            })
        return result


@router.get("/api/v1/boms/{bom_id}")
def get_bom(bom_id: int):
    """Detail of a BOM with all its lines. Each line is either a part
    (id_parts + part_name) or a sub-BOM (id_subbom + subbom_code +
    subbom_description). The 'line_type' field is 'part' or 'subbom'
    depending on the case."""
    with Session(engine) as session:
        bom = session.get(Bom, bom_id)
        if bom is None:
            raise HTTPException(status_code=404,
                                detail=f"BOM id={bom_id} introuvable.")
        project = None
        if bom.id_project is not None:
            project = session.get(Project, bom.id_project)

        lines = session.exec(
            select(BomLine).where(BomLine.id_bom == bom_id)
            .order_by(BomLine.id)
        ).all()
        # Preload the referenced parts AND sub-BOMs to avoid one query
        # per line.
        part_ids = {l.id_parts for l in lines if l.id_parts is not None}
        subbom_ids = {l.id_subbom for l in lines if l.id_subbom is not None}
        parts_by_id = {
            p.id: p for p in session.exec(
                select(Parts).where(Parts.id.in_(part_ids))
            ).all()
        } if part_ids else {}
        subboms_by_id = {
            b.id: b for b in session.exec(
                select(Bom).where(Bom.id.in_(subbom_ids))
            ).all()
        } if subbom_ids else {}

        result_lines = []
        for l in lines:
            entry = {"id": l.id, "quantity": l.quantity}
            if l.id_parts is not None:
                entry["line_type"] = "part"
                entry["id_parts"] = l.id_parts
                entry["part_name"] = (parts_by_id[l.id_parts].part_name
                                       if l.id_parts in parts_by_id else "?")
                entry["id_subbom"] = None
                entry["subbom_code"] = None
                entry["subbom_description"] = None
            elif l.id_subbom is not None:
                sub = subboms_by_id.get(l.id_subbom)
                entry["line_type"] = "subbom"
                entry["id_parts"] = None
                entry["part_name"] = None
                entry["id_subbom"] = l.id_subbom
                entry["subbom_code"] = sub.code if sub else "?"
                entry["subbom_description"] = sub.description if sub else None
            else:
                # Corrupt line (neither part nor subbom) - rare, log and skip
                logger.warning(f"BomLine id={l.id} sans part ni subbom.")
                continue
            result_lines.append(entry)

        return {
            "id": bom.id,
            "code": bom.code,
            "description": bom.description,
            "id_project": bom.id_project,
            "project_code": project.code if project else None,
            "lines": result_lines,
        }


@router.post("/api/v1/boms")
def create_bom(description: str = Form(default=""),
                id_project: int | None = Form(default=None)):
    """Creates a BOM with an auto-generated code (B0001, B0002...)."""
    description = (description or "").strip() or None
    with Session(engine) as session:
        if id_project is not None:
            if session.get(Project, id_project) is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Collection id={id_project} introuvable."
                )
        code = _next_bom_code(session)
        bom = Bom(code=code, description=description, id_project=id_project)
        session.add(bom)
        session.commit()
        session.refresh(bom)
        logger.info(f"BOM '{code}' creee (id={bom.id}).")
        return {
            "status": "success",
            "id": bom.id,
            "code": bom.code,
            "description": bom.description,
            "id_project": bom.id_project,
        }


@router.delete("/api/v1/boms/{bom_id}")
def delete_bom(bom_id: int,
               _admin: None = Depends(_require_admin)):
    """Deletes a BOM AND all its lines (cascade deletion handled
    manually since SQLite does not enforce FKs by default)."""
    with Session(engine) as session:
        bom = session.get(Bom, bom_id)
        if bom is None:
            raise HTTPException(status_code=404,
                                detail=f"BOM id={bom_id} introuvable.")
        # Manual cascade
        lines = session.exec(
            select(BomLine).where(BomLine.id_bom == bom_id)
        ).all()
        for line in lines:
            session.delete(line)
        session.delete(bom)
        session.commit()
        logger.info(f"BOM '{bom.code}' supprimee ({len(lines)} lignes).")
        return {"status": "success", "deleted_id": bom_id,
                "lines_removed": len(lines)}


@router.post("/api/v1/boms/{bom_id}/lines")
def add_bom_line(bom_id: int,
                  part_id: int | None = Form(default=None),
                  subbom_id: int | None = Form(default=None),
                  quantity: int = Form(default=1)):
    """Adds a line to a BOM: either a part (part_id) or a sub-BOM
    (subbom_id). EXACTLY ONE of the two must be provided.

    If an identical line (same type AND same target) already exists,
    the quantity is ACCUMULATED rather than creating a new line.

    For subbom_id: rejected if the addition would create a cycle in the
    hierarchy (self-reference or indirect loop)."""
    # Validation: exactly one of the two non-null
    if (part_id is None) == (subbom_id is None):
        raise HTTPException(
            status_code=400,
            detail="Fournir exactement un de part_id ou subbom_id."
        )
    if quantity <= 0:
        raise HTTPException(status_code=400,
                            detail="La quantité doit être > 0.")
    with Session(engine) as session:
        bom = session.get(Bom, bom_id)
        if bom is None:
            raise HTTPException(status_code=404,
                                detail=f"BOM id={bom_id} introuvable.")

        if part_id is not None:
            # --- "part" type line ---
            part = session.get(Parts, part_id)
            if part is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Pièce id={part_id} introuvable."
                )
            existing = session.exec(
                select(BomLine)
                .where(BomLine.id_bom == bom_id)
                .where(BomLine.id_parts == part_id)
            ).first()
            new_line = BomLine(id_bom=bom_id, id_parts=part_id,
                                 quantity=quantity)
        else:
            # --- "sub-BOM" type line ---
            sub = session.get(Bom, subbom_id)
            if sub is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"BOM id={subbom_id} introuvable."
                )
            # Cycle detection BEFORE any modification of the database
            if _would_create_cycle(session, bom_id, subbom_id):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cycle détecté : la BOM '{sub.code}' ne peut "
                           f"pas être incluse dans '{bom.code}' "
                           f"(elle la contient déjà directement ou "
                           f"indirectement)."
                )
            existing = session.exec(
                select(BomLine)
                .where(BomLine.id_bom == bom_id)
                .where(BomLine.id_subbom == subbom_id)
            ).first()
            new_line = BomLine(id_bom=bom_id, id_subbom=subbom_id,
                                 quantity=quantity)

        if existing:
            existing.quantity += quantity
            session.add(existing)
            session.commit()
            return {"status": "success", "id": existing.id,
                    "quantity": existing.quantity, "merged": True}
        session.add(new_line)
        session.commit()
        session.refresh(new_line)
        return {"status": "success", "id": new_line.id,
                "quantity": new_line.quantity, "merged": False}


@router.put("/api/v1/boms/{bom_id}/lines/{line_id}")
def update_bom_line(bom_id: int, line_id: int,
                     quantity: int = Form(...)):
    """Updates the quantity of a BOM line."""
    if quantity <= 0:
        raise HTTPException(status_code=400,
                            detail="La quantité doit être > 0.")
    with Session(engine) as session:
        line = session.get(BomLine, line_id)
        if line is None or line.id_bom != bom_id:
            raise HTTPException(status_code=404,
                                detail="Ligne BOM introuvable.")
        line.quantity = quantity
        session.add(line)
        session.commit()
        return {"status": "success", "id": line.id, "quantity": quantity}


@router.delete("/api/v1/boms/{bom_id}/lines/{line_id}")
def delete_bom_line(bom_id: int, line_id: int):
    """Deletes a line from a BOM."""
    with Session(engine) as session:
        line = session.get(BomLine, line_id)
        if line is None or line.id_bom != bom_id:
            raise HTTPException(status_code=404,
                                detail="Ligne BOM introuvable.")
        session.delete(line)
        session.commit()
        return {"status": "success", "deleted_id": line_id}


@router.post("/api/v1/boms/{bom_id}/stock-add")
def bom_stock_add(bom_id: int, factor: int = Form(default=1)):
    """Adds the BOM to stock 'factor' times. Traverses sub-BOMs
    RECURSIVELY: if BOM A contains 2x a sub-BOM B, and B contains
    3 vis, then stock-add(A, factor=1) adds 6 vis to stock.

    Creates the missing Stock lines. Atomic: all or nothing."""
    if factor <= 0:
        raise HTTPException(status_code=400,
                            detail="Le facteur doit être > 0.")
    with Session(engine) as session:
        bom = session.get(Bom, bom_id)
        if bom is None:
            raise HTTPException(status_code=404,
                                detail=f"BOM id={bom_id} introuvable.")
        # Check that there is at least one line
        any_line = session.exec(
            select(BomLine).where(BomLine.id_bom == bom_id).limit(1)
        ).first()
        if any_line is None:
            raise HTTPException(status_code=400,
                                detail="La BOM est vide.")

        # Hierarchical flatten -> {part_id: total_qty}
        totals = _flatten_bom(session, bom_id, factor=factor)

        # Apply the increments to the leaf parts
        changes = []
        for part_id, delta in totals.items():
            stock = _get_or_create_stock(session, part_id)
            stock.quantity += delta
            session.add(stock)
            changes.append({
                "id_parts": part_id,
                "delta": delta,
                "new_quantity": stock.quantity,
            })
        session.commit()
        logger.info(f"BOM '{bom.code}' ajoutee x{factor} au stock "
                    f"({len(changes)} pieces feuilles affectees).")
        return {"status": "success", "factor": factor, "changes": changes}


@router.post("/api/v1/boms/{bom_id}/stock-sub")
def bom_stock_sub(bom_id: int, factor: int = Form(default=1)):
    """Removes the BOM from stock 'factor' times. Traverses sub-BOMs
    RECURSIVELY. ATOMIC: if even a single part is short, EVERYTHING is
    rejected and the exhaustive list of shortages is returned
    (status 409 Conflict)."""
    if factor <= 0:
        raise HTTPException(status_code=400,
                            detail="Le facteur doit être > 0.")
    with Session(engine) as session:
        bom = session.get(Bom, bom_id)
        if bom is None:
            raise HTTPException(status_code=404,
                                detail=f"BOM id={bom_id} introuvable.")
        any_line = session.exec(
            select(BomLine).where(BomLine.id_bom == bom_id).limit(1)
        ).first()
        if any_line is None:
            raise HTTPException(status_code=400,
                                detail="La BOM est vide.")

        # Hierarchical flatten -> {part_id: total_qty_needed}
        totals = _flatten_bom(session, bom_id, factor=factor)

        # Phase 1: atomic availability check
        shortages = []
        for part_id, needed in totals.items():
            stock = session.exec(
                select(Stock).where(Stock.id_parts == part_id)
            ).first()
            current = stock.quantity if stock else 0
            if current < needed:
                part = session.get(Parts, part_id)
                shortages.append({
                    "id_parts": part_id,
                    "part_name": part.part_name if part else "?",
                    "needed": needed,
                    "available": current,
                    "missing": needed - current,
                })
        if shortages:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Stock insuffisant pour cette BOM.",
                    "shortages": shortages,
                }
            )

        # Phase 2: apply the decrements
        changes = []
        for part_id, needed in totals.items():
            stock = _get_or_create_stock(session, part_id)
            stock.quantity -= needed
            session.add(stock)
            changes.append({
                "id_parts": part_id,
                "delta": -needed,
                "new_quantity": stock.quantity,
            })
        session.commit()
        logger.info(f"BOM '{bom.code}' retiree x{factor} du stock "
                    f"({len(changes)} pieces feuilles affectees).")
        return {"status": "success", "factor": factor, "changes": changes}


# ----------------------------------------------------------------------
#  ENDPOINT: atomic creation of a BOM from an assembly
# ----------------------------------------------------------------------
# Receives a JSON containing: description, optional id_project, and a
# list of lines {name, quantity, use_existing_id?}. For each line:
#   - if use_existing_id is provided: use it directly
#   - otherwise, look for an existing part with that name: if found,
#     use it; otherwise, create a new part.
# Everything is done in ONE transaction: if anything fails
# (invalid name, non-existent ID), NOTHING is created.

class BomFromAssemblyLine(BaseModel):
    name: str
    quantity: int
    use_existing_id: int | None = None


class BomFromAssemblyRequest(BaseModel):
    description: str = ""
    id_project: int | None = None
    lines: list[BomFromAssemblyLine]


@router.post("/api/v1/boms/from-assembly")
def create_bom_from_assembly(req: BomFromAssemblyRequest):
    """Creates a BOM with its lines from an assembly scan. Also creates
    the parts that do not yet exist. Atomic: all or nothing."""
    if not req.lines:
        raise HTTPException(status_code=400,
                            detail="La liste des lignes est vide.")
    description = (req.description or "").strip() or None

    # Server-side pre-merge: if several lines share the same name
    # (a possible case if the macro sends both duplicates and separate
    # Links), accumulate the quantities. The merge is keyed by
    # use_existing_id if provided, otherwise by name.
    merged: dict[tuple, int] = {}
    for line in req.lines:
        if line.quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Quantité invalide pour '{line.name}' : "
                       f"{line.quantity}"
            )
        key = ("id", line.use_existing_id) if line.use_existing_id \
              else ("name", line.name)
        merged[key] = merged.get(key, 0) + line.quantity

    with Session(engine) as session:
        # Check the project if specified
        if req.id_project is not None:
            if session.get(Project, req.id_project) is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Collection id={req.id_project} introuvable."
                )

        # Phase 1: resolve all lines into (part_id, qty), creating the
        # missing parts along the way. Accumulate into a list for
        # phase 2.
        resolved: list[tuple[int, int]] = []  # [(part_id, qty), ...]
        created_parts: list[dict] = []        # for the final report

        for key, qty in merged.items():
            if key[0] == "id":
                part_id = key[1]
                part = session.get(Parts, part_id)
                if part is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Pièce id={part_id} introuvable "
                               f"(mapping explicite)."
                    )
                resolved.append((part.id, qty))
            else:
                name = key[1].strip()
                if not name:
                    raise HTTPException(
                        status_code=400,
                        detail="Nom de pièce vide dans la liste."
                    )
                # Look up by exact name
                existing = session.exec(
                    select(Parts).where(Parts.part_name == name)
                ).first()
                if existing is not None:
                    resolved.append((existing.id, qty))
                else:
                    # Create the part (empty Parts, no CAD, no project)
                    new_part = Parts(part_name=name)
                    session.add(new_part)
                    session.flush()  # to obtain new_part.id
                    resolved.append((new_part.id, qty))
                    created_parts.append({
                        "id": new_part.id,
                        "part_name": new_part.part_name,
                    })

        # Phase 2: create the BOM and its lines
        try:
            code = _next_bom_code(session)
        except HTTPException:
            raise  # 507 on BOM_CODE_MAX overflow

        bom = Bom(code=code, description=description,
                   id_project=req.id_project)
        session.add(bom)
        session.flush()

        for part_id, qty in resolved:
            session.add(BomLine(id_bom=bom.id, id_parts=part_id,
                                 quantity=qty))

        session.commit()
        session.refresh(bom)
        logger.info(f"BOM '{code}' creee depuis assemblage "
                    f"({len(resolved)} lignes, "
                    f"{len(created_parts)} pieces creees).")
        return {
            "status": "success",
            "id": bom.id,
            "code": bom.code,
            "lines_created": len(resolved),
            "parts_created": created_parts,
        }
