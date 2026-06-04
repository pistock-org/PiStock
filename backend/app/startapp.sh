#!/usr/bin/env bash
# Lance PiStock en HTTPS avec un certificat DEJA genere (key.pem/cert.pem).
# Toute la config (chemin du depot, port) vient de pistock.conf.
set -euo pipefail

# --- Localiser et charger la configuration ----------------------------
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
CONF="$SCRIPT_DIR/../../pistock.conf"   # pistock.conf est a la racine du depot
if [ ! -f "$CONF" ]; then
  echo "ERREUR : configuration introuvable : $CONF" >&2
  echo "Copiez pistock.conf.example -> pistock.conf et renseignez vos valeurs." >&2
  exit 1
fi
# shellcheck source=/dev/null
. "$CONF"
: "${PISTOCK_DIR:?definir PISTOCK_DIR dans pistock.conf}"
PISTOCK_PORT="${PISTOCK_PORT:-8000}"

# --- Lancer uvicorn en HTTPS ------------------------------------------
cd "$PISTOCK_DIR"

# Garder le certificat embarque dans le workbench FreeCAD synchronise
# avec celui qu'on sert, pour que la copie USB fasse toujours confiance
# a CE serveur. Non bloquant.
bash "$PISTOCK_DIR/deploy/sync_workbench_cert.sh" "$PISTOCK_DIR" || true

cd backend/app
uvicorn main:app --host 0.0.0.0 --port "$PISTOCK_PORT" \
  --ssl-keyfile ../../key.pem \
  --ssl-certfile ../../cert.pem
