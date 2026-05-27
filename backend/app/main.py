import os
import logging
import traceback
from datetime import datetime, timezone
from shutil import copyfileobj
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from sqlmodel import SQLModel, Field, Session, create_engine, select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pistock")

# Configuration des chemins (à adapter selon votre arborescence)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "../../../data-pistock"))
CAD_DIR = os.path.join(DATA_DIR, "uploads", "cad")
IMG_DIR = os.path.join(DATA_DIR, "uploads", "img")
DB_PATH = os.path.join(DATA_DIR, "pistockdatabase.sqlite3")

# S'assurer que tous les dossiers nécessaires existent
os.makedirs(CAD_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}")

app = FastAPI(title="PiStock PLM Receiver")


# Définition minimale des modèles pour l'insertion.
# IMPORTANT : ces modèles doivent rester cohérents avec init_db.py.
class Parts(SQLModel, table=True):
    __tablename__ = "parts"
    id: int | None = Field(default=None, primary_key=True)
    # Nom de la pièce, unique : sert de clé pour savoir si la pièce
    # a déjà été cataloguée lors d'un précédent export.
    part_name: str = Field(index=True, unique=True)


class PLM(SQLModel, table=True):
    __tablename__ = "plm"
    id: int | None = Field(default=None, primary_key=True)
    id_parts: int = Field(foreign_key="parts.id")
    path_2_cadfile: str | None = None
    path_2_thumbnail: str | None = None
    path_2_3dglb: str | None = None
    # Horodatage de cet enregistrement précis (= cette révision).
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    # Auteur de cette révision (renseigné par le GUI de la macro).
    author: str | None = None


@app.on_event("startup")
def on_startup():
    # Cree les tables si elles n'existent pas encore
    SQLModel.metadata.create_all(engine)
    logger.info("Base de donnees initialisee.")


@app.get("/api/v1/parts")
def list_parts():
    """
    Renvoie la liste de toutes les pièces existantes.
    Utilisé par le GUI de la macro FreeCAD pour peupler le menu
    déroulant "associer à une pièce existante".
    """
    with Session(engine) as session:
        parts = session.exec(select(Parts).order_by(Parts.part_name)).all()
        return [
            {"id": p.id, "part_name": p.part_name}
            for p in parts
        ]


@app.post("/api/v1/parts/upload")
async def upload_new_part(
    # L'utilisateur choisit dans le GUI :
    #  - soit une pièce EXISTANTE  -> il envoie 'part_id'
    #  - soit une NOUVELLE pièce   -> il envoie 'part_name'
    # Les deux champs sont optionnels ; le serveur tranche selon
    # ce qu'il reçoit. Au moins l'un des deux est obligatoire.
    part_id: int | None = Form(default=None),
    part_name: str | None = Form(default=None),
    # Auteur de cet export (saisi dans le GUI).
    author: str = Form(...),
    cad_file: UploadFile = File(...),
    thumbnail_file: UploadFile = File(...),
    glb_file: UploadFile = File(...),
):
    try:
        # Validation : il faut au moins un identifiant de pièce.
        if part_id is None and not part_name:
            raise HTTPException(
                status_code=400,
                detail="Il faut fournir soit 'part_id' (pièce "
                       "existante), soit 'part_name' (nouvelle pièce).",
            )

        # --- TIMESTAMP UNIQUE DE CET ENREGISTREMENT ---------------------
        # Généré ICI, côté serveur, au moment de la réception.
        # La MÊME valeur sert pour les noms de fichiers ET pour la base.
        ts_dt = datetime.now(timezone.utc)
        ts_tag = ts_dt.strftime("%Y%m%d_%H%M%S")
        logger.info(f"Timestamp de l'enregistrement : {ts_tag}")
        # ----------------------------------------------------------------

        # 1. Sauvegarde des fichiers physiques sur le disque
        saved_paths = {}
        for file_type, upload_file, sub_folder in [
            ("cad", cad_file, "cad"),
            ("img", thumbnail_file, "img"),
            ("glb", glb_file, "cad"),
        ]:
            dest_dir = os.path.join(DATA_DIR, "uploads", sub_folder)
            os.makedirs(dest_dir, exist_ok=True)

            # "monfichier.FCStd" -> "monfichier_20260527_143052.FCStd"
            base_name, extension = os.path.splitext(upload_file.filename)
            stamped_name = f"{base_name}_{ts_tag}{extension}"

            file_path = os.path.join(dest_dir, stamped_name)
            with open(file_path, "wb") as buffer:
                copyfileobj(upload_file.file, buffer)

            saved_paths[file_type] = f"uploads/{sub_folder}/{stamped_name}"
            logger.info(f"Fichier sauvegarde : {file_path}")

        # 2. Insertion dans la base de donnees SQLite via SQLModel
        with Session(engine) as session:
            # Etape A : déterminer la pièce concernée.
            if part_id is not None:
                # CAS 1 : l'utilisateur a choisi une pièce existante.
                # On l'identifie par son id (fiable, pas par le nom).
                part = session.get(Parts, part_id)
                if part is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Aucune pièce avec l'id {part_id}.",
                    )
                part_created = False
                logger.info(f"Pièce existante sélectionnée : "
                            f"'{part.part_name}' (id={part.id}).")
            else:
                # CAS 2 : nouvelle pièce. On vérifie quand même que le
                # nom n'existe pas déjà (sécurité : contrainte unique).
                existing = session.exec(
                    select(Parts).where(Parts.part_name == part_name)
                ).first()
                if existing:
                    # Le nom existe déjà : on réutilise plutôt que
                    # de planter sur la contrainte d'unicité.
                    part = existing
                    part_created = False
                    logger.info(f"Pièce '{part_name}' déjà connue "
                                f"(id={part.id}), réutilisation.")
                else:
                    part = Parts(part_name=part_name)
                    session.add(part)
                    session.flush()
                    part_created = True
                    logger.info(f"Nouvelle pièce '{part_name}' "
                                f"créée (id={part.id}).")

            # Etape B : dans TOUS les cas, nouvelle ligne dans 'plm'.
            new_plm = PLM(
                id_parts=part.id,
                path_2_cadfile=saved_paths["cad"],
                path_2_thumbnail=saved_paths["img"],
                path_2_3dglb=saved_paths["glb"],
                timestamp=ts_dt,
                author=author,
            )
            session.add(new_plm)
            session.commit()

            part_id_final = part.id
            part_name_final = part.part_name
            plm_id = new_plm.id

        return {
            "status": "success",
            "part_id": part_id_final,
            "part_name": part_name_final,
            "plm_id": plm_id,
            "part_created": part_created,
            "author": author,
            "timestamp": ts_dt.isoformat(),
            "message": (
                f"Part '{part_name_final}' successfully cataloged!"
                if part_created
                else f"New PLM revision added to part "
                     f"'{part_name_final}'."
            ),
        }

    except HTTPException:
        # On laisse passer les erreurs HTTP explicites (400, 404...)
        raise
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Erreur lors de l'upload :\n{tb}")
        raise HTTPException(status_code=500, detail=str(e))


# uvicorn main:app --reload --host 0.0.0.0 --port 8000
