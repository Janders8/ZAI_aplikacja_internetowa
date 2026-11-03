# Projekt "Zaawansowane Aplikacje Internetowe 2026Z" - Jan Żmuda 311640

Aplikacja internetowa do zbierania i prezentacji wyników pomiarów z czujników IoT.

## Struktura repozytorium

- `backend/app.py` - serwer aplikacji (przy pomocy Flask) z zaimplementowanym API obsługującym logowanie, serie, czujniki i wyniki
- `backend/schema.sql` - skrypt SQL tworzący tabele bazy danych
- `backend/requirements.txt` - wymagane biblioteki w Pythonie do działania aplikacji
- `backend/.env.example` - wzór pliku `.env` z loginem i hasłem administratora aplikacji
- `generator/generator.py` - generator danych, odczytuje wartości z czujników poziomu morza NOAA w USA (albo generuje je losowo) i wysyła je do api aplikacji
- `generator/requirements.txt` - wymagane biblioteki w Pythonie do działania generatora
- `docs/diagram_erd_drawdb.png` - diagram ERD bazy danych przechowującej wyniki z sensorów

Przed uruchomieniem aplikacji trzeba utworzyć plik `.env` na wzór `.env.example` (z loginem i hasłem admina)i uzupełnić go o własny login i hasło. Przy pierwszym uruchomieniu aplikacji samoczynnie powstaje plik `database.db`, który przechowuje dane z czujników.
