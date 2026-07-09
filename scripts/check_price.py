#!/usr/bin/env python3
"""
Bot de surveillance de prix de vol.
Compare le prix actuel au dernier prix connu et notifie via ntfy.sh
si le prix a baissé ou passe sous un seuil défini.
"""

import json
import os
import sys
from pathlib import Path

import requests
from fast_flights import FlightData, Passengers, Result, get_flights

# ---------- CONFIGURATION (à adapter) ----------
ORIGIN = os.environ.get("FLIGHT_ORIGIN", "CDG")
DESTINATION = os.environ.get("FLIGHT_DESTINATION", "GRU")
DEPARTURE_DATE = os.environ.get("FLIGHT_DATE", "2026-12-20")
RETURN_DATE = os.environ.get("FLIGHT_RETURN_DATE")  # None = aller simple
MAX_PRICE_EUR = float(os.environ.get("FLIGHT_MAX_PRICE", "700"))
SEAT_CLASS = os.environ.get("FLIGHT_SEAT_CLASS", "economy")

NTFY_TOPIC = os.environ["NTFY_TOPIC"]  # obligatoire, via secret GitHub
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

STATE_FILE = Path(__file__).parent.parent / "state" / "last_price.json"
# ------------------------------------------------


def get_current_price() -> float | None:
    """Interroge Google Flights via fast-flights et renvoie le prix le plus bas trouvé."""
    flight_data = [FlightData(date=DEPARTURE_DATE, from_airport=ORIGIN, to_airport=DESTINATION)]
    if RETURN_DATE:
        flight_data.append(FlightData(date=RETURN_DATE, from_airport=DESTINATION, to_airport=ORIGIN))

    result: Result = get_flights(
        flight_data=flight_data,
        trip="round-trip" if RETURN_DATE else "one-way",
        seat=SEAT_CLASS,
        passengers=Passengers(adults=1, children=0, infants_in_seat=0, infants_on_lap=0),
        fetch_mode="fallback",
    )

    prices = []
    for flight in result.flights:
        try:
            price_str = flight.price.replace("€", "").replace(",", "").strip()
            prices.append(float(price_str))
        except (ValueError, AttributeError):
            continue

    return min(prices) if prices else None


def load_last_price() -> float | None:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text()).get("price")
    return None


def save_price(price: float) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"price": price}))


def notify(title: str, message: str, priority: str = "default") -> None:
    requests.post(
        NTFY_URL,
        data=message.encode("utf-8"),
        headers={
            "Title": title.encode("utf-8"),
            "Priority": priority,
            "Tags": "airplane",
        },
        timeout=10,
    )


def main() -> None:
    current_price = get_current_price()

    if current_price is None:
        print("Impossible de récupérer un prix, on ne notifie rien.")
        sys.exit(0)

    last_price = load_last_price()
    print(f"Prix actuel: {current_price}€ | Dernier prix connu: {last_price}€")

    should_notify = False
    title = ""
    message = ""
    priority = "default"

    if current_price <= MAX_PRICE_EUR:
        should_notify = True
        title = "✈️ Prix sous ton seuil !"
        message = f"{ORIGIN} → {DESTINATION} le {DEPARTURE_DATE} : {current_price}€ (seuil: {MAX_PRICE_EUR}€)"
        priority = "high"
    elif last_price is not None and current_price < last_price:
        should_notify = True
        title = "📉 Le prix a baissé"
        message = f"{ORIGIN} → {DESTINATION} le {DEPARTURE_DATE} : {current_price}€ (contre {last_price}€ avant)"

    if should_notify:
        notify(title, message, priority)
        print("Notification envoyée.")
    else:
        print("Pas de notification (prix stable ou en hausse).")

    save_price(current_price)


if __name__ == "__main__":
    main()
