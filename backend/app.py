# plik odpowiadający za serwer aplikacji backendowej
# Na podstawie:
# https://flask.palletsprojects.com/en/stable/
# https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Content-Type-Options
# https://www.sqlite.org/
# https://www.youtube.com/watch?v=pd-0G0MigUA (sqlite3)
# https://argon2-cffi.readthedocs.io/
# https://github.com/theskumar/python-dotenv
# https://docs.python.org/3/library
# https://stackoverflow.com/questions/1309989/parameter-substitution-for-a-sqlite-in-clause

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

# Narzędzie do haszowania i sprawdzania haseł, wykorzystano algorytm Argon2
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


# Przed każdym żądaniem do API, sprawdzenie czy klient przyjmuje JSON, jak nie to zwracany jest błąd 406
@app.before_request
def check_accept_header():
    accept = request.accept_mimetypes
    if request.path.startswith("/api/") and accept.provided and not accept.accept_json:
        abort(406, "API zwraca dane jedynie w formacie JSON")

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

# Zamiana tekstu ISO 8601 ze strefą czasową na czas UTC. W razie błędu zwraca 400
# Przyjmuje się że podany czas musi zawierać strefę czasową.
def parse_time(text):
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        abort(400, "Niepoprawny czas, oczekiwano np. 2026-10-05T12:00:00Z")
    if moment.tzinfo is None:
        abort(400, "Czas musi zawierać strefę czasową")
    return moment.astimezone(timezone.utc)

# ---------------------------------------------------------------------------
# Sprawdzanie dostępu (token administratora, klucz API czujnika)
# ---------------------------------------------------------------------------

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
        abort(401, "Token jest nieprawidłowy lub skończyła mu się ważność")
    return session


# Sprawdzenie klucza API czujnika z nagłówka X-API-Key. Brak poprawnego klucza zwraca 401
def require_sensor():
    api_key = request.headers.get("X-API-Key", "")
    sensor = get_db().execute(
        "SELECT id, series_id FROM sensors WHERE api_key_hash = ?", (sha256(api_key),)
    ).fetchone()
    if sensor is None:
        abort(401, "Brak lub niepoprawny klucz API czujnika")
    return sensor

# ---------------------------------------------------------------------------
# API - stan serwera i logowanie
# ---------------------------------------------------------------------------

# GET /api/health - sprawdzenie, czy serwer odpowiada
@app.get("/api/health")
def health():
    return {"status": "ok"}

# GET /api/coffee - Bo mi się spodobał ten kod :)
@app.get("/api/coffee")
def coffee():
    abort(418, "Jestem czajnikiem, nie zrobię kawy!")

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
        abort(422, "Nowe hasło musi zawierać co najmniej 8 znaków")
    db = get_db()
    admin = db.execute(
        "SELECT password_hash FROM admins WHERE id = ?", (session["admin_id"],)
    ).fetchone()
    if not password_matches(admin["password_hash"], current_password):
        abort(403, "Aktualne hasło jest niepoprawne")
    db.execute(
        "UPDATE admins SET password_hash = ? WHERE id = ?",
        (password_hasher.hash(new_password), session["admin_id"]),
    )
    db.commit()
    return "", 204

# ---------------------------------------------------------------------------
# API - serie
# ---------------------------------------------------------------------------

# Zamiana wiersza serii z bazy na słownik z nazwami pól zgodnie z kontraktem API
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

# Sprawdzenie danych serii z żądania przy dodawaniu i edycji
# kody błędów
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
    if icon is not None and not isinstance(icon, str):
        abort(400, "Pole icon musi być tekstem albo null")
    if unit is not None and not isinstance(unit, str):
        abort(400, "Pole unit musi być tekstem albo null")
    if not 1 <= len(name) <= 100:
        abort(422, "Nazwa musi zawierać od 1 do 100 znaków")
    if min_value >= max_value:
        abort(422, "minValue musi być mniejsze od maxValue")
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        abort(422, "Kolor musi mieć format #RRGGBB")
    if unit is not None and len(unit) > 20:
        abort(422, "Jednostka nie może mieć więcej niż 20 znaków")
    return name, min_value, max_value, color, icon, unit


# GET /api/series - lista wszystkich serii
@app.get("/api/series")
def list_series():
    rows = get_db().execute("SELECT * FROM series ORDER BY id").fetchall()
    result = []
    for row in rows:
        result.append(series_to_json(row))
    return result


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
    # Jeśli w serii są już wyniki spoza nowego zakresu, zmiana jest odrzucana z kodem 409
    outside = db.execute(
        "SELECT COUNT(*) FROM measurements WHERE series_id = ? AND (value < ? OR value > ?)",
        (series_id, min_value, max_value),
    ).fetchone()[0]
    if outside > 0:
        abort(409, "W serii występują wyniki spoza nowego zakresu")
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


# ---------------------------------------------------------------------------
# API - czujniki
# ---------------------------------------------------------------------------

# Zamiana wiersza czujnika z bazy na słownik z nazwami pól z kontraktu
def sensor_to_json(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "seriesId": row["series_id"],
        "createdAt": row["created_at"],
    }


# Odczyt czujnika z bazy po id. Gdy go nie ma zwraca błąd 404
def find_sensor(sensor_id):
    row = get_db().execute(
        "SELECT id, name, series_id, created_at FROM sensors WHERE id = ?", (sensor_id,)
    ).fetchone()
    if row is None:
        abort(404, "Brak czujnika o danym id")
    return row


# POST /api/sensors - rejestracja nowego czujnika, klucz API widzi admin tylko raz w odpowiedzi
@app.post("/api/sensors")
def create_sensor():
    require_admin()
    data = get_json_body()
    name = data.get("name")
    series_id = data.get("seriesId")
    if not isinstance(name, str) or not is_number(series_id):
        abort(400, "Wymagane pola name (tekst) i seriesId (liczba)")
    if not 1 <= len(name) <= 100:
        abort(422, "Nazwa musi zawierać od 1 do 100 znaków")
    db = get_db()
    if db.execute("SELECT id FROM series WHERE id = ?", (series_id,)).fetchone() is None:
        abort(422, "Nie ma serii o danym seriesId")
    # Losowy klucz API dla czujnika, w bazie zapisuje się tylko jego skrót
    api_key = secrets.token_hex(32)
    cursor = db.execute(
        "INSERT INTO sensors (name, series_id, api_key_hash, created_at) VALUES (?, ?, ?, ?)",
        (name, series_id, sha256(api_key), to_iso(datetime.now(timezone.utc))),
    )
    db.commit()
    sensor_id = cursor.lastrowid
    sensor = sensor_to_json(find_sensor(sensor_id))
    sensor["apiKey"] = api_key
    return sensor, 201, {"Location": f"/api/sensors/{sensor_id}"}


# GET /api/sensors/<id> - jeden czujnik (wymaga uprawnień admina)
@app.get("/api/sensors/<int:sensor_id>")
def get_sensor(sensor_id):
    require_admin()
    return sensor_to_json(find_sensor(sensor_id))


# GET /api/sensors - lista czujników (tylko administrator)
@app.get("/api/sensors")
def list_sensors():
    require_admin()
    rows = get_db().execute(
        "SELECT id, name, series_id, created_at FROM sensors ORDER BY id"
    ).fetchall()
    result = []
    for row in rows:
        result.append(sensor_to_json(row))
    return result


# DELETE /api/sensors/<id> - wyrejestrowanie czujnika. Klucz przestaje działać, natomiast wyniki zostają w bazie
@app.delete("/api/sensors/<int:sensor_id>")
def delete_sensor(sensor_id):
    require_admin()
    find_sensor(sensor_id)
    db = get_db()
    db.execute("DELETE FROM sensors WHERE id = ?", (sensor_id,))
    db.commit()
    return "", 204


# ---------------------------------------------------------------------------
# API - Wyniki pomiaru
# ---------------------------------------------------------------------------

# Zamiana wiersza wyniku z bazy na słownik z nazwami pól zgodnie z wymaganiami kontraktu API
def measurement_to_json(row):
    return {
        "id": row["id"],
        "seriesId": row["series_id"],
        "value": row["value"],
        "timestamp": row["timestamp"],
    }


# Odczytanie wyniku z bazy danych po id. Gdy go nie ma, zwracany jest błąd 404
def find_measurement(measurement_id):
    row = get_db().execute("SELECT * FROM measurements WHERE id = ?", (measurement_id,)).fetchone()
    if row is None:
        abort(404, "Brak wyniku o danym id")
    return row


# POST /api/measurements - zapis wyniku przesłanego przez czujnik (wymagany jest klucz API czujnika)
@app.post("/api/measurements")
def create_measurement():
    sensor = require_sensor()
    data = get_json_body()
    value = data.get("value")
    if not is_number(value):
        abort(400, "Wymagane pole value (liczba)")
    # Przy braku czasu w żądaniu przyjmuje się czas serwera
    now = datetime.now(timezone.utc)
    timestamp = data.get("timestamp")
    if timestamp is None:
        moment = now
    else:
        moment = parse_time(timestamp)

    # Sprawdzenie czy czas nie jest późniejszy niż 5 minut na wypadek błędów czujnika
    if moment > now + timedelta(minutes=5):
        abort(422, "Czas pomiaru nie może być późniejszy niż 5 minut od chwili obecnej")
    series = find_series(sensor["series_id"])
    if value < series["min_value"] or value > series["max_value"]:
        # Odrzucenie pomiaru spoza przyjętego zakresy. Jest to loggowane
        app.logger.warning("Odrzucono wynik %s z czujnika %s: spoza przyjętego zakresu serii", value, sensor["id"])
        abort(422, "Wartość nie jest w dopuszczalnym zakresie serii")
    db = get_db()
    cursor = db.execute(
        "INSERT INTO measurements (series_id, sensor_id, value, timestamp) VALUES (?, ?, ?, ?)",
        (sensor["series_id"], sensor["id"], value, to_iso(moment)),
    )
    db.commit()
    measurement_id = cursor.lastrowid
    return measurement_to_json(find_measurement(measurement_id)), 201, {"Location": f"/api/measurements/{measurement_id}"}


# GET /api/measurements/<id> - jeden wynik (dostępny bez logowania)
@app.get("/api/measurements/<int:measurement_id>")
def get_measurement(measurement_id):
    return measurement_to_json(find_measurement(measurement_id))

# GET /api/measurements - lista wyników z filtrami (dostępna bez potrzeby logowania)
@app.get("/api/measurements")
def list_measurements():
    # Początek zapytania, do niego doklejane są kolejne podane parametry wyszukiwania
    # dzieki WHERE 1 = 1 wystarczy tylko doklejać kolejne filtry za pomocą "AND"
    sql = "SELECT * FROM measurements WHERE 1 = 1"
    params = []

    # Wybrane serie
    series = request.args.get("series")
    if series is not None:
        placeholders = []
        for part in series.split(","):
            if not part.isdecimal():
                abort(400, "Parametr series musi być listą liczb. Np. '1,3'")
            placeholders.append("?")
            params.append(int(part))
        sql += " AND series_id IN (" + ", ".join(placeholders) + ")"

    # Przedziały czasu, wartości graniczne się wliczają
    time_from = request.args.get("from")
    if time_from is not None:
        sql += " AND timestamp >= ?"
        params.append(to_iso(parse_time(time_from)))
    time_to = request.args.get("to")
    if time_to is not None:
        sql += " AND timestamp <= ?"
        params.append(to_iso(parse_time(time_to)))

    # sortowanie po czasie (sort=timestamp). Można też sortować malejąco za pomocą sort=-timestamp
    sort = request.args.get("sort", "timestamp")
    if sort == "timestamp":
        sql += " ORDER BY timestamp"
    elif sort == "-timestamp":
        sql += " ORDER BY timestamp DESC"
    else:
        abort(400, "Parametr sort może mieć tylko wartość timestamp albo -timestamp")

    # limit wyników, domyślnie 1000, maksymalnie 10000
    limit = request.args.get("limit", "1000")
    if not limit.isdecimal():
        abort(400, "Parametr limit musi być liczbą")
    limit = int(limit)
    if limit < 1 or limit > 10000:
        abort(400, "Parametr limit musi być od 1 do 10000")
    sql += " LIMIT ?"
    params.append(limit)

    # wykonanie złożonego zapytania
    rows = get_db().execute(sql, params).fetchall()
    result = []
    for row in rows:
        result.append(measurement_to_json(row))
    return result