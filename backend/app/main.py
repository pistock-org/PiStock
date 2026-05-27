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


@app.on_event("startup")
def on_startup():
    # Cree les tables si elles n'existent pas encore
    SQLModel.metadata.create_all(engine)
    logger.info("Base de donnees initialisee.")


@app.post("/api/v1/parts/upload")
async def upload_new_part(
    part_name: str = Form(...),
    cad_file: UploadFile = File(...),
    thumbnail_file: UploadFile = File(...),
    glb_file: UploadFile = File(...),
):
    try:
        # --- TIMESTAMP UNIQUE DE CET ENREGISTREMENT ---------------------
        # Généré ICI, côté serveur, au moment de la réception.
        # La MÊME valeur sert pour les noms de fichiers ET pour la base,
        # ce qui garantit leur cohérence parfaite.
        ts_dt = datetime.now(timezone.utc)
        # Version "compacte" pour les noms de fichiers (ex: 20260527_143052).
        # Pas de ':' ni d'espace -> noms valides sur tous les systèmes.
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
            os.makedirs(dest_dir, exist_ok=True)  # securite supplementaire

            # On insère le timestamp dans le nom du fichier :
            # "monfichier.FCStd" -> "monfichier_20260527_143052.FCStd"
            base_name, extension = os.path.splitext(upload_file.filename)
            stamped_name = f"{base_name}_{ts_tag}{extension}"

            file_path = os.path.join(dest_dir, stamped_name)
            with open(file_path, "wb") as buffer:
                copyfileobj(upload_file.file, buffer)

            # Stockage du chemin relatif pour la base de donnees
            saved_paths[file_type] = f"uploads/{sub_folder}/{stamped_name}"
            logger.info(f"Fichier sauvegarde : {file_path}")

        # 2. Insertion dans la base de donnees SQLite via SQLModel
        with Session(engine) as session:
            # Etape A : on cherche si une pièce de ce nom existe déjà.
            existing_part = session.exec(
                select(Parts).where(Parts.part_name == part_name)
            ).first()

            if existing_part:
                # La pièce existe déjà : on ne touche PAS à la table
                # 'parts', on réutilise simplement son id.
                part = existing_part
                part_created = False
                logger.info(f"Pièce '{part_name}' déjà connue "
                            f"(id={part.id}), réutilisation.")
            else:
                # Nouvelle pièce : on l'ajoute dans 'parts'.
                part = Parts(part_name=part_name)
                session.add(part)
                session.flush()  # genere l'ID sans committer definitivement
                part_created = True
                logger.info(f"Nouvelle pièce '{part_name}' "
                            f"créée (id={part.id}).")

            # Etape B : dans TOUS les cas, on ajoute une nouvelle ligne
            # dans 'plm' avec le timestamp de cet enregistrement.
            new_plm = PLM(
                id_parts=part.id,
                path_2_cadfile=saved_paths["cad"],
                path_2_thumbnail=saved_paths["img"],
                path_2_3dglb=saved_paths["glb"],
                timestamp=ts_dt,
            )
            session.add(new_plm)
            session.commit()  # commit unique

            # On capture les ID AVANT de sortir du bloc with
            # (sinon DetachedInstanceError : l'objet n'est plus lie a la session)
            part_id = part.id
            plm_id = new_plm.id

        return {
            "status": "success",
            "part_id": part_id,
            "plm_id": plm_id,
            "part_created": part_created,
            "timestamp": ts_dt.isoformat(),
            "message": (
                f"Part '{part_name}' successfully cataloged!"
                if part_created
                else f"Part '{part_name}' already existed - "
                     f"new PLM revision added."
            ),
        }

    except Exception as e:
        # On logge le traceback complet cote serveur pour le debug
        tb = traceback.format_exc()
        logger.error(f"Erreur lors de l'upload :\n{tb}")
        raise HTTPException(status_code=500, detail=str(e))


# uvicorn main:app --reload --host 0.0.0.0 --port 8000
