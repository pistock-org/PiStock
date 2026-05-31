cd ~/Perso/pistock


# 2. Lancer uvicorn avec HTTPS (à adapter à ta commande de démarrage)
cd backend/app
uvicorn main:app --host 0.0.0.0 --port 8000 \
  --ssl-keyfile ../../key.pem \
  --ssl-certfile ../../cert.pem
