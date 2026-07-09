#!/usr/bin/env python3
"""
Bot de surveillance de prix de vol, basé sur l'API Google Flights de SerpApi.
Compare le prix actuel au dernier prix connu et notifie via ntfy.sh
si le prix a baissé ou passe sous un seuil défini.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------- CONFIGURATION (à adapter) ----------
ORIGIN = os.environ.get("FLIGHT_ORIGIN", "CDG")
DESTINATION = os.environ.get("FLIGHT_DESTINATION", "GRU")
DEPARTURE_DATE = os.environ.get("FLIGHT_DATE", "2026-12-20")
RETURN_DATE = os.environ.get("FLIGHT_RETURN_DATE")  # vide/absent = aller simple
MAX_PRICE_EUR = float(os.environ.get("FLIGHT_MAX_PRICE", "700"))
CURRENCY = os.environ.get("FLIGHT_CURRENCY", "EUR")

SERPAPI_KEY = os.environ["SERPAPI_KEY"]  # obligatoire, via secret GitHub
NTFY_TOPIC = os.environ["NTFY_TOPIC"]  # obligatoire, via secret GitHub
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

STATE_FILE = Path(__file__).parent.parent / "state" / "last_price.json"
PAGE_FILE = Path(__file__).parent.parent / "docs" / "index.html"
# ------------------------------------------------


def write_status_page(current_price: float | None, last_price: float | None) -> None:
    """Génère une page HTML statique affichant le dernier prix connu."""
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    if current_price is not None:
        price_display = f"{current_price:.0f} {CURRENCY}"
        under_threshold = current_price <= MAX_PRICE_EUR
        status_color = "#16a34a" if under_threshold else "#374151"
        status_text = "Sous ton seuil !" if under_threshold else "Au-dessus du seuil"
    else:
        price_display = "N/A"
        status_color = "#dc2626"
        status_text = "Dernière vérification en échec"

    trend = ""
    if current_price is not None and last_price is not None:
        if current_price < last_price:
            trend = f"↓ en baisse (était {last_price:.0f} {CURRENCY})"
        elif current_price > last_price:
            trend = f"↑ en hausse (était {last_price:.0f} {CURRENCY})"
        else:
            trend = "→ stable"

    route = f"{ORIGIN} → {DESTINATION}"
    if RETURN_DATE:
        route += f" (A/R {DEPARTURE_DATE} → {RETURN_DATE})"
    else:
        route += f" ({DEPARTURE_DATE})"

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Suivi vol {ORIGIN}-{DESTINATION}</title>
<style>
  body {{
    font-family: -apple-system, system-ui, sans-serif;
    background: #f3f4f6;
    margin: 0;
    padding: 2rem 1rem;
    display: flex;
    justify-content: center;
  }}
  .card {{
    background: white;
    border-radius: 16px;
    padding: 2rem;
    max-width: 360px;
    width: 100%;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    text-align: center;
  }}
  .route {{ color: #6b7280; font-size: 0.9rem; margin-bottom: 0.5rem; }}
  .price {{ font-size: 3rem; font-weight: 700; color: {status_color}; margin: 0.5rem 0; }}
  .status {{ color: {status_color}; font-weight: 600; margin-bottom: 1rem; }}
  .trend {{ color: #6b7280; font-size: 0.9rem; margin-bottom: 1rem; }}
  .updated {{ color: #9ca3af; font-size: 0.8rem; }}
</style>
</head>
<body>
  <div class="card">
    <div class="route">{route}</div>
    <div class="price">{price_display}</div>
    <div class="status">{status_text}</div>
    <div class="trend">{trend}</div>
    <div class="updated">Dernière vérification : {now}</div>
  </div>
</body>
</html>"""

    PAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PAGE_FILE.write_text(html, encoding="utf-8")


def get_current_price() -> float | None:
    """Interroge l'API Google Flights de SerpApi et renvoie le prix le plus bas trouvé."""
    params = {
        "engine": "google_flights",
        "departure_id": ORIGIN,
        "arrival_id": DESTINATION,
        "outbound_date": DEPARTURE_DATE,
        "currency": CURRENCY,
        "hl": "fr",
        "type": "1" if RETURN_DATE else "2",  # 1 = aller-retour, 2 = aller simple
        "api_key": SERPAPI_KEY,
    }
    if RETURN_DATE:
        params["return_date"] = RETURN_DATE

    try:
        response = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"Erreur réseau lors de l'appel à SerpApi: {e}")
        return None

    if data.get("search_metadata", {}).get("status") != "Success":
        print(f"SerpApi n'a pas retourné un statut Success: {data.get('search_metadata')}")
        if "error" in data:
            print(f"Erreur SerpApi: {data['error']}")
        return None

    all_flights = data.get("best_flights", []) + data.get("other_flights", [])
    print(f"Nombre d'options de vol trouvées: {len(all_flights)}")

    prices = [f["price"] for f in all_flights if "price" in f]

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

    last_price = load_last_price()

    if current_price is None:
        print("Impossible de récupérer un prix, on ne notifie rien.")
        write_status_page(None, last_price)
        sys.exit(0)

    print(f"Prix actuel: {current_price}{CURRENCY} | Dernier prix connu: {last_price}{CURRENCY}")

    should_notify = False
    title = ""
    message = ""
    priority = "default"

    if current_price <= MAX_PRICE_EUR:
        should_notify = True
        title = "✈️ Prix sous ton seuil !"
        message = f"{ORIGIN} → {DESTINATION} le {DEPARTURE_DATE} : {current_price}{CURRENCY} (seuil: {MAX_PRICE_EUR}{CURRENCY})"
        priority = "high"
    elif last_price is not None and current_price < last_price:
        should_notify = True
        title = "📉 Le prix a baissé"
        message = f"{ORIGIN} → {DESTINATION} le {DEPARTURE_DATE} : {current_price}{CURRENCY} (contre {last_price}{CURRENCY} avant)"

    if should_notify:
        notify(title, message, priority)
        print("Notification envoyée.")
    else:
        print("Pas de notification (prix stable ou en hausse).")

    write_status_page(current_price, last_price)
    save_price(current_price)


if __name__ == "__main__":
    main()
