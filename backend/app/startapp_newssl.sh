cd ~/Perso/pistock

# 1. Générer un certificat valide pour ton IP locale
#    Adapte le CN selon ton cas (IP ou nom de machine)
openssl req -x509 -newkey rsa:4096 \
  -keyout key.pem -out cert.pem \
  -days 365 -nodes \
  -subj "/CN=10.0.0.27" \
  -addext "subjectAltName=IP:10.0.0.27,DNS:pistock.local"

# 2. Lancer uvicorn avec HTTPS (à adapter à ta commande de démarrage)
cd backend/app
uvicorn main:app --host 0.0.0.0 --port 8000 \
  --ssl-keyfile ../../key.pem \
  --ssl-certfile ../../cert.pem
