# Generator - wysyła wyniki pomiarów do API aplikacji internetowej

# Na podstawie:
# https://docs.python.org/3/howto/argparse.html
# https://requests.readthedocs.io/en/latest/user/quickstart/
# https://api.tidesandcurrents.noaa.gov/api/prod/

import argparse
import random
import time
from datetime import datetime, timedelta, timezone
import requests
import sys



# Adres API NOAA udostępniający poziom wody na brzegu
NOAA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

# -----------------------------
# Parametry generatora
# -----------------------------

# Odczytanie parametrów
def read_args():
    parser = argparse.ArgumentParser(description="Generator pomiarów")
    parser.add_argument("--api", required=True, help="adres aplikacji, np. http://127.0.0.1:5000")
    parser.add_argument("--key", required=True, help="klucz API czujnika")
    parser.add_argument("--mode", choices=["random", "noaa"], default="random", help="sposób generowania wartości:" \
    " random - losowe z zakresu --min/--max," \
    " noaa - rzeczywisty poziom wody ze stacji pomiarowej NOAA")
    parser.add_argument("--min", type=float, default=0, help="najmniejsza losowana wartość (dla trybu losowego)")
    parser.add_argument("--max", type=float, default=3, help="największa losowana wartość (dla trybu losowego)")
    parser.add_argument("--station", default="9414290", help="numer stacji NOAA (dla trybu rzeczywistego)")
    parser.add_argument("--count", type=int, default=20, help="liczba wyników")
    parser.add_argument("--interval", type=float, default=5, help="odstęp między odczytami w sekundach")
    parser.add_argument("--past", action="store_true", help="wysyła od razu wyniki z czasami z przeszłości (np. jako dane przykładowe)")
    args = parser.parse_args()
    # liczba wyników musi być dodatnia (bo NOAA 0 zwracałoby wszystkie wyniki)
    if args.count < 1:
        parser.error("--count musi być większe od 0")
    return args



# -----------------------------
# Wysyłanie wyników do API aplikacji
# -----------------------------

# Wysłanie jednego wyniku z kluczem czujnika i wypisanie, czy serwer go zapisał do bazy danych
def send(args, value, timestamp):
    body = {"value": value}
    # czas jest przypisywany tylko kiedy jest znany (tryb --past i odczyt NOAA),
    # bez niego serwer zapisze swój aktualny czas
    if timestamp is not None:
        body["timestamp"] = timestamp
    response = requests.post(
        args.api + "/api/measurements",
        json=body,
        headers={"X-API-Key": args.key},
        timeout=10,
    )
    if response.status_code == 201:
        result = response.json()
        print(f"Zapisano: {result['value']} ({result['timestamp']})")
    else:
        # obsługa błędu w formacie Problem Details
        problem = response.json()
        print(f"Odrzucono ({response.status_code}): {problem['detail']} (wartość {value})")


# -----------------------------
# Tryb random - wartości losowe z zakresu od --min do --max, do pokazania odrzucenia błędnych wartości przez serwer
# -----------------------------

# Losowa wartość z podanego zakresu
def random_value(args):
    return round(random.uniform(args.min, args.max), 2)

# Losowo na żywo, wysyła wynik co --interval sekund
def random_live(args):
    for i in range(args.count):
        send(args, random_value(args), None)
        time.sleep(args.interval)


# Losowe z przeszłości, od razu wysyła --count wyników z czasami co --interval sekund.
def random_past(args):
    start = datetime.now(timezone.utc) - timedelta(seconds=args.interval * (args.count - 1))
    for i in range(args.count):
        # Dodanie czasu od momentu pierwszego wyniku
        moment = start + timedelta(seconds=args.interval * i)
        # wysłanie z zamianą czasu w standardzie ISO 8601
        send(args, random_value(args), moment.isoformat())


# -----------------------------
# Tryb noaa - rzeczywiste dane o poziomie wody ze stacji pomiarowej NOAA w USA
# -----------------------------

# Pobranie odczytów ze stacji NOAA w formie par czas i wartość, od najstarszego pomiaru 
def noaa_readings(args):
    # parametry zapytania, ustawione tak by pobierały dane o poziomie wody na wybrzeżu
    params = {
        "product": "water_level",
        "datum": "MLLW",
        "time_zone": "gmt",
        "units": "metric",
        "format": "json",
        "application": "ZAI_generator",
        "station": args.station,
    }
    # z przeszłości, pobiera ostatnie 72 godziny
    if args.past:
        params["range"] = 72
    # na żywo, pobiera ostatnią godzinę
    else:
        params["range"] = 1
    data = requests.get(NOAA_URL, params=params, timeout=30).json()
    if "error" in data:
        sys.exit(f"Błąd NOAA: {data['error']['message']}")
    readings = []
    for item in data["data"]:
        # Czasem zdarza się problem z odczytem, wtedy wynik jest pomijany
        if item["v"] != "":
            # zamiana czasu NOAA (UTC) na format ISO 8601
            timestamp = item["t"].replace(" ", "T") + ":00Z"
            readings.append((timestamp, float(item["v"])))
    return readings



# Na żywo, co --interval sekund sprawdza najnowszy odczyt i wysyła go
# stacja wykonuje pomiar co 6 minut
def noaa_live(args):
    last_sent = None
    for i in range(args.count):
        readings = noaa_readings(args)

        # Jeśli stacja nie ma odczytu z ostatniej godziny (np. awaraia), zakończ komunikatem
        if len(readings) == 0:
            sys.exit("Stacja NOAA nie zwraca odczytów z ostatniej godziny, spróbuj ponownie później")
        

        # najnowszy odczyt
        timestamp, value = readings[-1]
        # Zabezpieczenie na wypadek gdyby czujnik zwrócił ten sam wynik co poprzednio
        if timestamp == last_sent:
            print("Brak nowego odczytu")
        else:
            send(args, value, timestamp)
            last_sent = timestamp
        time.sleep(args.interval)

# Z przeszłości,  wysyła od razu --count najnowszych odczytów
def noaa_past(args):
    readings = noaa_readings(args)

    # Zabezpieczenie na wypadek zwrócenia zbyt małej liczby wyników, wtedy nic nie jest wysyłane,
    # bo niepełnych danych nie da się usunąć, zgodnie z wymaganiami wymaga to usunięcia całej serii
    if len(readings) < args.count:
        sys.exit(f"Zbyt mała liczba wyników z czujnika NOAA ({len(readings)} z {args.count}), spróbuj ponownie")


    # Wysłanie najnowszych --count wyników z odczytu
    for timestamp, value in readings[-args.count:]:
        send(args, value, timestamp)



# -----------------------------
# Uruchomienie generatora
# -----------------------------

args = read_args()
if args.mode == "random":
    if args.past:
        random_past(args)
    else:
        random_live(args)
else:
    if args.past:
        noaa_past(args)
    else:
        noaa_live(args)