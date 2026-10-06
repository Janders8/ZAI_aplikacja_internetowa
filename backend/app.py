# plik odpowiadający za serwer aplikacji backendowej
# Na podstawie:
# https://flask.palletsprojects.com/en/stable/
# https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Content-Type-Options
# https://www.sqlite.org/
# https://www.youtube.com/watch?v=pd-0G0MigUA (sqlite3)
# https://argon2-cffi.readthedocs.io/
# https://github.com/theskumar/python-dotenv
# https://docs.python.org/3/library

import hashlib
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from dotenv import load_dotenv
from flask import Flask, abort, g, json, request
from werkzeug.exceptions import HTTPException


# ---------------------------------------------------------------------------
# Ustawienia aplikacji
# ---------------------------------------------------------------------------

# Wczytanie ustawień loginu i hasła admina z pliku .env
load_dotenv()

app = Flask(__name__)


# Ścieżka do pliku bazy danych
DATABASE = os.path.join(app.root_path, "database.db")

# Narzędzie do haszowania i sprawdzania haseł, algorytm Argon2
password_hasher = PasswordHasher()


# Ile sekund ważny jest token administratora (1h)
TOKEN_LIFETIME = 3600

# ---------------------------------------------------------------------------
# Baza danych
# ---------------------------------------------------------------------------

# Połączenie z bazą przy żądaniu
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        # SQLite domyślnie nie pilnuje kluczy obcych, ta linia włącza to sprawdzanie
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


# Zamknięcie połączenia z bazą po żądaniu
@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# Utworzenie tabel z pliku schema.sql (już istniejące tabele i dane zostają nienaruszone)
def init_db():
    db = get_db()
    with app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))
    # Jeśli nie ma jeszcze admina to jest tworzony z danych z .env
    if db.execute("SELECT id FROM admins").fetchone() is None:
        password_hash = password_hasher.hash(os.environ["ADMIN_PASSWORD"])
        db.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            (os.environ["ADMIN_USERNAME"], password_hash),
        )
        db.commit()


# Przygotowanie bazy przy starcie serwera
with app.app_context():
    init_db()

# ---------------------------------------------------------------------------
# Obsługa błędów i nagłówki
# ---------------------------------------------------------------------------

# Zwracanie błędów HTTP w formie JSON w formacie Problem Details
@app.errorhandler(HTTPException)
def handle_http_error(e):
    response = e.get_response()
    response.data = json.dumps({
        "type": "about:blank",
        "title": e.name,
        "status": e.code,
        "detail": e.description,
    })
    response.content_type = "application/problem+json"
    return response


# Przed każdym żądaniem do API, sprawdzenie czy klient przyjmuje JSON, jak nie to zwracamy 406
@app.before_request
def check_accept_header():
    accept = request.accept_mimetypes
    if request.path.startswith("/api/") and accept.provided and not accept.accept_json:
        abort(406, "API zwraca dane tylko w formacie JSON")

# Dodanie do każdej odpowiedzi nagłówka bezpieczeństwa, by przeglądarka nie zgadywała sama typu
@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


# ---------------------------------------------------------------------------
# Funkcje pomocnicze
# ---------------------------------------------------------------------------

# Sprawdzenie hasła do hashu w bazie danych
def password_matches(password_hash, password):
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


# funkcja do uzyskania skrótu SHA-256
def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


# Czas UTC jako tekst w stałym formacie (np. 2026-10-05T12:00:00.000Z)
def to_iso(moment):
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


# Sprawdzenie czy treść żądania to obiekt JSON (słownik), w przeciwnym razie zwraca błąd 400
def get_json_body():
    data = request.get_json()
    if not isinstance(data, dict):
        abort(400, "Treść żądania musi być obiektem JSON")
    return data

# Sprawdzenie, czy wartość jest liczbą
def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)

# Sprawdzenie tokenu administratora z nagłówka Authorization. Błędny token/brak tokenu zwraca kod 401
def require_admin():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        abort(401, "Brak tokenu administratora")
    token = auth.removeprefix("Bearer ")
    session = get_db().execute(
        "SELECT id, admin_id FROM sessions WHERE token_hash = ? AND expires_at > ?",
        (sha256(token), to_iso(datetime.now(timezone.utc))),
    ).fetchone()
    if session is None:
        abort(401, "Token jest nieprawidłowy lub wygasł")
    return session


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

# GET /api/health - sprawdzenie, czy serwer odpowiada
@app.get("/api/health")
def health():
    return {"status": "ok"}

# POST /api/auth/login - logowanie administratora. W odpowiedzi zwraca token
@app.post("/api/auth/login")
def login():
    data = get_json_body()
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        abort(400, "Wymagane pola username i password (tekst)")
    db = get_db()
    admin = db.execute(
        "SELECT id, password_hash FROM admins WHERE username = ?", (username,)
    ).fetchone()
    if admin is None or not password_matches(admin["password_hash"], password):
        abort(401, "Niepoprawny login lub hasło")

    # Losowy token dla klienta, w bazie zapisany jest tylko jego skrót i czas ważności
    token = secrets.token_urlsafe(32)
    expires_at = to_iso(datetime.now(timezone.utc) + timedelta(seconds=TOKEN_LIFETIME))
    db.execute(
        "INSERT INTO sessions (admin_id, token_hash, expires_at) VALUES (?, ?, ?)",
        (admin["id"], sha256(token), expires_at),
    )
    db.commit()
    return {"accessToken": token, "tokenType": "Bearer", "expiresIn": TOKEN_LIFETIME}

# POST /api/auth/logout - wylogowanie admina
@app.post("/api/auth/logout")
def logout():
    session = require_admin()
    db = get_db()
    db.execute("DELETE FROM sessions WHERE id = ?", (session["id"],))
    db.commit()
    return "", 204


# PUT /api/auth/password - zmiana hasła zalogowanego administratora
@app.put("/api/auth/password")
def change_password():
    session = require_admin()
    data = get_json_body()
    current_password = data.get("currentPassword")
    new_password = data.get("newPassword")
    if not isinstance(current_password, str) or not isinstance(new_password, str):
        abort(400, "Wymagane pola currentPassword i newPassword (tekst)")

    # wymaganie, by hasło miało co najmniej 8 znaków
    if len(new_password) < 8:
        abort(422, "Nowe hasło musi mieć co najmniej 8 znaków")
    db = get_db()
    admin = db.execute(
        "SELECT password_hash FROM admins WHERE id = ?", (session["admin_id"],)
    ).fetchone()
    if not password_matches(admin["password_hash"], current_password):
        abort(403, "Bieżące hasło jest niepoprawne")
    db.execute(
        "UPDATE admins SET password_hash = ? WHERE id = ?",
        (password_hasher.hash(new_password), session["admin_id"]),
    )
    db.commit()
    return "", 204

# Zamiana wiersza serii z bazy na słownik z nazwami pól zgodnie z kontraktem
def series_to_json(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "minValue": row["min_value"],
        "maxValue": row["max_value"],
        "color": row["color"],
        "icon": row["icon"],
        "unit": row["unit"],
    }


# Odczyt serii z bazy po id. Gdy jej nie ma zwraca błąd 404
def find_series(series_id):
    row = get_db().execute("SELECT * FROM series WHERE id = ?", (series_id,)).fetchone()
    if row is None:
        abort(404, "Nie ma serii o podanym id")
    return row

# Sprawdzenie danych serii z żądania przy dodawaniu i edycji:
# 400 - zły typ lub brak pola
# 422 - złamana reguła
def validate_series(data):
    name = data.get("name")
    min_value = data.get("minValue")
    max_value = data.get("maxValue")
    color = data.get("color")
    icon = data.get("icon")
    unit = data.get("unit")
    if not isinstance(name, str) or not isinstance(color, str):
        abort(400, "Wymagane pola name i color (tekst)")
    if not is_number(min_value) or not is_number(max_value):
        abort(400, "Wymagane pola minValue i maxValue (liczby)")
    if (icon is not None and not isinstance(icon, str)) or (unit is not None and not isinstance(unit, str)):
        abort(400, "Pola icon i unit muszą być tekstem albo null")
    if not 1 <= len(name) <= 100:
        abort(422, "Nazwa musi mieć od 1 do 100 znaków")
    if min_value >= max_value:
        abort(422, "minValue musi być mniejsze od maxValue")
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        abort(422, "Kolor musi mieć format #RRGGBB")
    if unit is not None and len(unit) > 20:
        abort(422, "Jednostka może mieć najwyżej 20 znaków")
    return name, min_value, max_value, color, icon, unit


# GET /api/series - lista wszystkich serii
@app.get("/api/series")
def list_series():
    rows = get_db().execute("SELECT * FROM series ORDER BY id").fetchall()
    return [series_to_json(row) for row in rows]


# GET /api/series/<id> - jedna seria
@app.get("/api/series/<int:series_id>")
def get_series(series_id):
    return series_to_json(find_series(series_id))

# POST /api/series - dodanie nowej serii (tylko zalogowany administrator)
@app.post("/api/series")
def create_series():
    require_admin()
    values = validate_series(get_json_body())
    db = get_db()
    cursor = db.execute(
        "INSERT INTO series (name, min_value, max_value, color, icon, unit) VALUES (?, ?, ?, ?, ?, ?)",
        values,
    )
    db.commit()
    series_id = cursor.lastrowid
    return series_to_json(find_series(series_id)), 201, {"Location": f"/api/series/{series_id}"}


# PUT /api/series/<id> - edycja serii (tylko zalogowany administrator)
@app.put("/api/series/<int:series_id>")
def update_series(series_id):
    require_admin()
    find_series(series_id)
    name, min_value, max_value, color, icon, unit = validate_series(get_json_body())
    db = get_db()
    # # Jeśli w serii są już wyniki spoza nowego zakresu, zmiana jest odrzucana z kodem 409
    outside = db.execute(
        "SELECT COUNT(*) FROM measurements WHERE series_id = ? AND (value < ? OR value > ?)",
        (series_id, min_value, max_value),
    ).fetchone()[0]
    if outside > 0:
        abort(409, "W serii są wyniki spoza nowego zakresu")
    db.execute(
        "UPDATE series SET name = ?, min_value = ?, max_value = ?, color = ?, icon = ?, unit = ? WHERE id = ?",
        (name, min_value, max_value, color, icon, unit, series_id),
    )
    db.commit()
    return series_to_json(find_series(series_id))


# DELETE /api/series/<id> - usunięcie serii razem z jej czujnikami i wynikami (tylko administrator)
@app.delete("/api/series/<int:series_id>")
def delete_series(series_id):
    require_admin()
    find_series(series_id)
    db = get_db()
    db.execute("DELETE FROM series WHERE id = ?", (series_id,))
    db.commit()
    return "", 204