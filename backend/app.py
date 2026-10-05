# plik odpowiadający za serwer aplikacji backendowej
# Na podstawie: https://flask.palletsprojects.com/en/stable/quickstart/

from flask import Flask

app = Flask(__name__)


# GET /api/health - sprawdzenie, czy serwer odpowiada
@app.get("/api/health")
def health():
    return {"status": "ok"}
