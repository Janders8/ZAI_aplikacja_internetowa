
-- schema.sql - struktura bazy danych aplikacji 

-- Na podstawie:
-- https://flask.palletsprojects.com/en/stable/tutorial/database/
-- https://www.sqlite.org/

-- czas jest zapisywany w polu tekstowym w formacie ISO 8601, UTC

-- admins - konto administratora
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    -- hasło w formie hasha (Argon2)
    password_hash TEXT NOT NULL
);

-- sessions - zalogowane sesje
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    -- kiedy token przestaje być ważny
    expires_at TEXT NOT NULL,
    -- klucz obcy do admina
    FOREIGN KEY (admin_id) REFERENCES admins (id) ON DELETE CASCADE
);


-- series - serie pomiarowe
CREATE TABLE IF NOT EXISTS series (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- nazwa serii
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
    -- dopuszczalny zakres wartości
    min_value REAL NOT NULL,
    max_value REAL NOT NULL,
    -- kolor linii na wykresie w formacie #RRGGBB
    color TEXT NOT NULL,
    -- kształt punktów na wykresie
    icon TEXT,
    -- jednostka, np. '°C'
    unit TEXT CHECK (length(unit) <= 20),
    -- Sprawdzenie poprawności zakresu
    CHECK (min_value < max_value)
);

-- sensors - zarejestrowane czujniki (Każdy czujnik należy do jednej serii i ma własny klucz API.)
CREATE TABLE IF NOT EXISTS sensors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
    -- Seria do której czujnik ma zapisywać wyniki
    series_id INTEGER NOT NULL,
    -- skrót SHA-256 klucza API (administrator widzi pełny tylko raz przy rejestracji czujnika)
    api_key_hash TEXT NOT NULL UNIQUE,
    -- kiedy czujnik zarejestrowano
    created_at TEXT NOT NULL,
    -- usunięcie serii usuwa też jej czujniki
    FOREIGN KEY (series_id) REFERENCES series (id) ON DELETE CASCADE
);


-- measurements - wyniki pomiarów
CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- seria do której należy wynik
    series_id INTEGER NOT NULL,
    -- który czujnik przysłał wynik
    sensor_id INTEGER,
    value REAL NOT NULL,
    -- kiedy zmierzono
    timestamp TEXT NOT NULL,
    -- usunięcie serii usuwa też jej wyniki
    FOREIGN KEY (series_id) REFERENCES series (id) ON DELETE CASCADE,
    -- usunięcie czujnika nie usuwa wyników, tylko wpisuje NULL w sensor_id
    FOREIGN KEY (sensor_id) REFERENCES sensors (id) ON DELETE SET NULL
);


-- indeks po serii i czasie, dla przyśpieszenia zapytań odczytu
CREATE INDEX IF NOT EXISTS idx_measurements_series_time
    ON measurements (series_id, timestamp);
