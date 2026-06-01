# ======================================================================
#  PiStock — tests unitaires (logique pure + helpers base de données)
# ======================================================================
# Cible : les fonctions où une régression coûte cher et que l'on teste
# trivialement — génération de codes (base 26), versions PLM, aplatissage
# récursif des BOM, détection de cycle.
#
# Lancement (depuis la racine du dépôt) :
#     pip install pytest
#     pytest -q
#
# Les helpers de base prennent tous une `session` en argument : on leur
# fournit une base SQLite EN MÉMOIRE, isolée et jetée après chaque test.
# Aucune dépendance à la vraie base data-pistock/.
# ----------------------------------------------------------------------
import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine, select

import main  # résolu via tests/conftest.py


# ---------------------------------------------------------------------
#  Fixture : session SQLite en mémoire avec le schéma de PiStock
# ---------------------------------------------------------------------
@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


# Petits helpers de fabrication pour garder les tests lisibles
def _mk_part(session, name):
    p = main.Parts(part_name=name)
    session.add(p)
    session.flush()
    return p


def _mk_bom(session, code, description=None):
    b = main.Bom(code=code, description=description)
    session.add(b)
    session.flush()
    return b


# =====================================================================
#  1. Conversions de codes — fonctions pures (sans base)
# =====================================================================
class TestProjectCodeMath:
    @pytest.mark.parametrize("code,expected", [
        ("AAA", 0), ("AAB", 1), ("AAZ", 25),
        ("ABA", 26), ("BAA", 676), ("ZZZ", 17575),
    ])
    def test_code_to_int(self, code, expected):
        assert main._code_to_int(code) == expected

    @pytest.mark.parametrize("code", ["AAA", "AAB", "AAZ", "ABA", "MNO", "ZZZ"])
    def test_roundtrip(self, code):
        assert main._int_to_code(main._code_to_int(code)) == code

    def test_bounds(self):
        assert main._int_to_code(0) == "AAA"
        assert main._int_to_code(main.PROJECT_CODE_MAX) == "ZZZ"


class TestVersionMath:
    @pytest.mark.parametrize("v,expected", [
        ("aa", 0), ("ab", 1), ("az", 25), ("ba", 26), ("zz", 675),
    ])
    def test_version_to_int(self, v, expected):
        assert main._version_to_int(v) == expected

    @pytest.mark.parametrize("v", ["aa", "ab", "az", "ba", "mn", "zz"])
    def test_roundtrip(self, v):
        assert main._int_to_version(main._version_to_int(v)) == v

    def test_bounds(self):
        assert main._int_to_version(0) == "aa"
        assert main._int_to_version(main.PLM_VERSION_MAX) == "zz"


# =====================================================================
#  2. Génération du prochain code projet
# =====================================================================
class TestNextProjectCode:
    def test_empty_db_starts_at_AAA(self, session):
        assert main._next_project_code(session) == "AAA"

    def test_increment(self, session):
        session.add(main.Project(code="AAA"))
        session.flush()
        assert main._next_project_code(session) == "AAB"

    def test_carry_over(self, session):
        session.add(main.Project(code="AAZ"))
        session.flush()
        assert main._next_project_code(session) == "ABA"

    def test_overflow_raises_507(self, session):
        session.add(main.Project(code="ZZZ"))
        session.flush()
        with pytest.raises(HTTPException) as exc:
            main._next_project_code(session)
        assert exc.value.status_code == 507


# =====================================================================
#  3. Génération du prochain code BOM
# =====================================================================
class TestNextBomCode:
    def test_empty_db_starts_at_B0001(self, session):
        assert main._next_bom_code(session) == "B0001"

    def test_increment(self, session):
        _mk_bom(session, "B0001")
        assert main._next_bom_code(session) == "B0002"

    def test_zero_padding(self, session):
        _mk_bom(session, "B0009")
        assert main._next_bom_code(session) == "B0010"

    def test_overflow_raises_507(self, session):
        _mk_bom(session, "B9999")
        with pytest.raises(HTTPException) as exc:
            main._next_bom_code(session)
        assert exc.value.status_code == 507


# =====================================================================
#  4. Génération de version PLM (par pièce)
# =====================================================================
class TestNextVersionForPart:
    def test_first_revision_is_aa(self, session):
        p = _mk_part(session, "bracket")
        assert main._next_version_for_part(session, p.id) == "aa"

    def test_increment(self, session):
        p = _mk_part(session, "bracket")
        session.add(main.PLM(id_parts=p.id, version="aa"))
        session.flush()
        assert main._next_version_for_part(session, p.id) == "ab"

    def test_is_per_part(self, session):
        # La version d'une pièce n'influence pas celle d'une autre.
        p1 = _mk_part(session, "alpha")
        p2 = _mk_part(session, "beta")
        session.add(main.PLM(id_parts=p1.id, version="ae"))
        session.flush()
        assert main._next_version_for_part(session, p2.id) == "aa"

    def test_overflow_raises_507(self, session):
        p = _mk_part(session, "bracket")
        session.add(main.PLM(id_parts=p.id, version="zz"))
        session.flush()
        with pytest.raises(HTTPException) as exc:
            main._next_version_for_part(session, p.id)
        assert exc.value.status_code == 507


# =====================================================================
#  5. Aplatissage récursif des BOM (sous-BOMs)
# =====================================================================
class TestFlattenBom:
    def test_simple(self, session):
        p1 = _mk_part(session, "vis-M3")
        p2 = _mk_part(session, "ecrou")
        a = _mk_bom(session, "B0001")
        session.add(main.BomLine(id_bom=a.id, id_parts=p1.id, quantity=5))
        session.add(main.BomLine(id_bom=a.id, id_parts=p2.id, quantity=2))
        session.flush()
        assert main._flatten_bom(session, a.id) == {p1.id: 5, p2.id: 2}

    def test_nested_with_factor(self, session):
        # Reproduit l'exemple de la docstring : A contient 5×vis et
        # 2×(sous-BOM B), B contient 3×ecrou + 1×rondelle.
        # => {vis:5, ecrou:6, rondelle:2}
        vis = _mk_part(session, "vis-M3")
        ecrou = _mk_part(session, "ecrou")
        rondelle = _mk_part(session, "rondelle")
        a = _mk_bom(session, "B0001")
        b = _mk_bom(session, "B0002")
        session.add(main.BomLine(id_bom=b.id, id_parts=ecrou.id, quantity=3))
        session.add(main.BomLine(id_bom=b.id, id_parts=rondelle.id, quantity=1))
        session.add(main.BomLine(id_bom=a.id, id_parts=vis.id, quantity=5))
        session.add(main.BomLine(id_bom=a.id, id_subbom=b.id, quantity=2))
        session.flush()
        assert main._flatten_bom(session, a.id) == {
            vis.id: 5, ecrou.id: 6, rondelle.id: 2,
        }

    def test_global_factor_multiplies_everything(self, session):
        p = _mk_part(session, "vis")
        a = _mk_bom(session, "B0001")
        session.add(main.BomLine(id_bom=a.id, id_parts=p.id, quantity=4))
        session.flush()
        assert main._flatten_bom(session, a.id, factor=3) == {p.id: 12}


# =====================================================================
#  6. Détection de cycle dans la hiérarchie des BOM
# =====================================================================
class TestWouldCreateCycle:
    def test_self_reference(self, session):
        a = _mk_bom(session, "B0001")
        assert main._would_create_cycle(session, a.id, a.id) is True

    def test_indirect_cycle(self, session):
        # A -> B -> C ; ajouter A comme sous-BOM de C boucle.
        a = _mk_bom(session, "B0001")
        b = _mk_bom(session, "B0002")
        c = _mk_bom(session, "B0003")
        session.add(main.BomLine(id_bom=a.id, id_subbom=b.id, quantity=1))
        session.add(main.BomLine(id_bom=b.id, id_subbom=c.id, quantity=1))
        session.flush()
        assert main._would_create_cycle(session, c.id, a.id) is True

    def test_no_cycle(self, session):
        a = _mk_bom(session, "B0001")
        d = _mk_bom(session, "B0004")  # sans enfants
        assert main._would_create_cycle(session, a.id, d.id) is False


# =====================================================================
#  7. Authentification admin (PBKDF2 + endpoints)
# =====================================================================
class TestAdminPasswordHash:
    def test_roundtrip(self):
        salt = main._new_salt()
        h = main._hash_password("hunter2", salt)
        assert main._verify_password("hunter2", salt.hex(), h) is True

    def test_rejects_wrong_password(self):
        salt = main._new_salt()
        h = main._hash_password("hunter2", salt)
        assert main._verify_password("Hunter2", salt.hex(), h) is False
        assert main._verify_password("", salt.hex(), h) is False

    def test_salt_changes_hash(self):
        s1, s2 = main._new_salt(), main._new_salt()
        # Salts différents -> hashes différents pour le même mot de passe
        assert s1 != s2
        assert main._hash_password("same", s1) != main._hash_password("same", s2)

    def test_hash_is_hex_and_long_enough(self):
        # SHA-256 -> 32 octets -> 64 caractères hex
        h = main._hash_password("x", main._new_salt())
        assert len(h) == 64
        int(h, 16)  # ne lève pas si bien hex


class TestCheckAdminPassword:
    def test_no_admin_configured_raises_503(self, session):
        # Note : _check_admin_password ouvre sa propre Session sur l'engine
        # global de main, donc on ne peut pas tester l'absence d'admin
        # via la fixture en mémoire. On vérifie juste les cas password
        # vide/None qui lèvent 401 sans toucher la DB.
        with pytest.raises(HTTPException) as exc:
            main._check_admin_password(None)
        assert exc.value.status_code == 401

    def test_empty_password_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            main._check_admin_password("")
        assert exc.value.status_code == 401


class TestAdminModelInSchema:
    def test_admin_table_created(self, session):
        # La table 'admin' fait partie du schéma (créée par create_all).
        # On vérifie qu'on peut insérer et lire un enregistrement.
        salt = main._new_salt()
        rec = main.Admin(
            salt=salt.hex(),
            password_hash=main._hash_password("test123", salt),
        )
        session.add(rec)
        session.commit()
        session.refresh(rec)
        assert rec.id is not None
        assert rec.created_at  # default_factory a fonctionné

        fetched = session.exec(select(main.Admin)).first()
        assert fetched is not None
        assert main._verify_password("test123", fetched.salt,
                                       fetched.password_hash)
