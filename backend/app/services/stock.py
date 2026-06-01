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
STOCK endpoints (quantity, location, supply, photo, component datasheet).

Note: we do NOT check the lock here. The lock protects the design
(project, status); stock is operational info that must remain updatable
even on a locked "Asset" part.

The `_get_or_create_stock` helper is also reused by the stock operations
of the BOMs (services/boms.py).
"""
import os
from datetime import datetime, timezone
from shutil import copyfileobj

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from sqlmodel import Session, select

from config import engine, logger, DATA_DIR
from model import Parts, Stock

router = APIRouter()


def _get_or_create_stock(session: Session, part_id: int) -> Stock:
    """Return the stock row for this part, creating it if absent."""
    stock_row = session.exec(
        select(Stock).where(Stock.id_parts == part_id)
    ).first()
    if stock_row is None:
        stock_row = Stock(id_parts=part_id)
        session.add(stock_row)
        session.flush()
    return stock_row


@router.get("/api/v1/parts/{part_id}/stock")
def get_part_stock(part_id: int):
    """Return the stock info of a part. If the row does not exist yet,
    we return default values (quantity=0, the rest None) rather than a
    404: from the UI's point of view, every part has stock (possibly
    empty)."""
    with Session(engine) as session:
        part = session.get(Parts, part_id)
        if part is None:
            raise HTTPException(status_code=404,
                                detail=f"Pièce id={part_id} introuvable.")
        stock_row = session.exec(
            select(Stock).where(Stock.id_parts == part_id)
        ).first()
        if stock_row is None:
            return {
                "part_id": part_id,
                "quantity": 0,
                "location": None,
                "supply": None,
                "stock_img_url": None,
                "doc_url": None,
            }
        return {
            "part_id": part_id,
            "quantity": stock_row.quantity,
            "location": stock_row.location,
            "supply": stock_row.supply,
            "stock_img_url": (f"/{stock_row.path_2_img}"
                               if stock_row.path_2_img else None),
            "doc_url": (f"/{stock_row.path_2_doc}"
                         if stock_row.path_2_doc else None),
        }


@router.post("/api/v1/parts/{part_id}/stock")
def update_part_stock(
    part_id: int,
    quantity: int = Form(default=0),
    location: str | None = Form(default=None),
    supply: str | None = Form(default=None),
):
    """Update the stock info (quantity, location, supply). Create the
    stock row if it does not exist. Empty strings are converted to NULL
    for database consistency."""
    if quantity < 0:
        raise HTTPException(status_code=400,
                            detail="La quantité ne peut pas être négative.")

    # Normalize: "" -> None
    location = (location or "").strip() or None
    supply = (supply or "").strip() or None

    with Session(engine) as session:
        part = session.get(Parts, part_id)
        if part is None:
            raise HTTPException(status_code=404,
                                detail=f"Pièce id={part_id} introuvable.")
        stock_row = _get_or_create_stock(session, part_id)
        stock_row.quantity = quantity
        stock_row.location = location
        stock_row.supply = supply
        session.add(stock_row)
        session.commit()
        logger.info(f"Stock piece {part_id} : qty={quantity} "
                    f"loc={location} supply={supply}")
        return {
            "status": "success",
            "quantity": stock_row.quantity,
            "location": stock_row.location,
            "supply": stock_row.supply,
        }


@router.post("/api/v1/parts/{part_id}/stock-doc")
async def upload_stock_doc(part_id: int, doc: UploadFile = File(...)):
    """Upload (or replace) the component datasheet of a part. The file
    goes into data-pistock/uploads/doc/ with a timestamp suffix to
    avoid collisions while keeping the original name readable."""
    with Session(engine) as session:
        part = session.get(Parts, part_id)
        if part is None:
            raise HTTPException(status_code=404,
                                detail=f"Pièce id={part_id} introuvable.")

        # Final name: "<basename>_<timestamp>.<ext>".
        # We keep the original name for visual identification.
        ts_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        original = doc.filename or "fiche.pdf"
        base, ext = os.path.splitext(original)
        if not ext:
            ext = ".pdf"
        # Light sanitization of the basename to avoid characters that
        # are problematic on disk.
        safe_base = "".join(c if c.isalnum() or c in "-_." else "_"
                             for c in base) or "fiche"
        stamped_name = f"{safe_base}_{ts_tag}{ext}"

        dest_dir = os.path.join(DATA_DIR, "uploads", "doc")
        os.makedirs(dest_dir, exist_ok=True)
        file_path = os.path.join(dest_dir, stamped_name)
        with open(file_path, "wb") as buffer:
            copyfileobj(doc.file, buffer)
        rel_path = f"uploads/doc/{stamped_name}"
        logger.info(f"Fiche composant sauvegardee : {file_path}")

        stock_row = _get_or_create_stock(session, part_id)
        stock_row.path_2_doc = rel_path
        session.add(stock_row)
        session.commit()

        return {
            "status": "success",
            "part_id": part_id,
            "doc_url": f"/{rel_path}",
            "filename": stamped_name,
        }


@router.post("/api/v1/parts/{part_id}/stock-photo")
async def upload_stock_photo(part_id: int, photo: UploadFile = File(...)):
    """Add (or replace) the stock photo of a part.
    The file is saved under data-pistock/uploads/img/stock_<id>_<ts>.<ext>
    and the path is stored in the 'stock' table. If no stock row exists
    yet for this part, one is created."""
    with Session(engine) as session:
        part = session.get(Parts, part_id)
        if part is None:
            raise HTTPException(status_code=404,
                                detail=f"Aucune pièce avec l'id {part_id}.")

        # Save the file on disk in uploads/stkimg/.
        # This directory is dedicated to photos of parts "in stock"
        # (taken with a phone, scanned, etc.), distinct from uploads/img/
        # which holds the CAD thumbnails generated by FreeCAD.
        ts_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        _, ext = os.path.splitext(photo.filename or "")
        if not ext:
            ext = ".jpg"  # reasonable fallback
        stamped_name = f"stock_{part_id}_{ts_tag}{ext}"
        dest_dir = os.path.join(DATA_DIR, "uploads", "stkimg")
        os.makedirs(dest_dir, exist_ok=True)
        file_path = os.path.join(dest_dir, stamped_name)
        with open(file_path, "wb") as buffer:
            copyfileobj(photo.file, buffer)
        rel_path = f"uploads/stkimg/{stamped_name}"
        logger.info(f"Photo stock sauvegardée : {file_path}")

        # Update (or create) the stock row
        stock_row = session.exec(
            select(Stock).where(Stock.id_parts == part_id)
        ).first()
        if stock_row is None:
            stock_row = Stock(id_parts=part_id, path_2_img=rel_path)
            session.add(stock_row)
        else:
            stock_row.path_2_img = rel_path
            session.add(stock_row)
        session.commit()

        return {
            "status": "success",
            "part_id": part_id,
            "stock_img_url": f"/{rel_path}",
        }
