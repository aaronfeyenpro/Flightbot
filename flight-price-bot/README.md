# Flight Price Bot

Surveille le prix d'un vol et envoie une notification push quand il baisse ou passe sous un seuil.

## Setup (10 min)

### 1. Créer le repo
Pousse ce dossier sur un repo GitHub (public ou privé, peu importe pour GitHub Actions gratuit).

### 2. Installer l'app ntfy sur ton téléphone
- [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
- [iOS](https://apps.apple.com/us/app/ntfy/id1625396347)

Choisis un nom de "topic" **unique et difficile à deviner** (ex: `aaron-vol-paris-gru-x7k2`), car n'importe qui connaissant ce nom peut lire tes notifs. Abonne-toi à ce topic dans l'app.

### 3. Configurer le secret GitHub
Dans ton repo → Settings → Secrets and variables → Actions → New repository secret :
- Nom : `NTFY_TOPIC`
- Valeur : le nom de topic choisi ci-dessus

### 4. Adapter les paramètres du vol
Édite les variables d'environnement dans `.github/workflows/flight-price-check.yml` :
- `FLIGHT_ORIGIN` / `FLIGHT_DESTINATION` : codes IATA (ex: CDG, GRU)
- `FLIGHT_DATE` : date de départ souhaitée
- `FLIGHT_RETURN_DATE` : optionnel, pour un aller-retour
- `FLIGHT_MAX_PRICE` : seuil de prix en euros qui déclenche une alerte "achète maintenant"

### 5. Activer et tester
Va dans l'onglet **Actions** de ton repo, sélectionne "Flight Price Check", clique "Run workflow" pour un test manuel. Ensuite ça tournera automatiquement toutes les 6h.

## Comment ça marche
- `scripts/check_price.py` interroge Google Flights via la librairie `fast-flights`
- Le prix trouvé est comparé au dernier prix connu, stocké dans `state/last_price.json`
- Si le prix baisse OU passe sous ton seuil → notification push via ntfy.sh
- Le fichier d'état est commité automatiquement à chaque run pour garder l'historique

## Limites à connaître
- `fast-flights` s'appuie sur l'API interne de Google Flights (non officielle) : elle peut casser si Google change son format. Si ça arrive, il faudra mettre à jour la librairie ou changer de source.
- ntfy.sh public est gratuit mais non chiffré de bout en bout — évite d'y mettre des infos sensibles, garde juste le topic secret.
- Un cron toutes les 6h = 4 requêtes/jour, largement dans les limites gratuites de GitHub Actions (2000 min/mois pour un repo privé, illimité pour un repo public).

## Idées d'évolution
- Suivre plusieurs routes en parallèle (boucle sur une liste de configs, ou plusieurs jobs matrix)
- Historiser tous les prix dans un CSV pour visualiser la tendance
- Ajouter une marge de flexibilité de dates (±3 jours) pour trouver le meilleur prix sur une fenêtre
