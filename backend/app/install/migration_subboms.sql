-- PiStock — Migration vers BOMs hiérarchiques (sous-BOMs)
-- À exécuter UNE FOIS sur votre base existante (pistockdatabase.sqlite3)
--
-- Ajoute la colonne id_subbom à bom_line. SQLite ne nécessite pas
-- de modifier id_parts (qui devient nullable au niveau ORM seulement).
--
-- Usage :
--   cd ~/Perso/pistock/data-pistock     # ajuster le chemin
--   sqlite3 pistockdatabase.sqlite3 < migration_subboms.sql

ALTER TABLE bom_line ADD COLUMN id_subbom INTEGER REFERENCES bom(id);

-- Vérification : la nouvelle colonne doit apparaître
.schema bom_line
