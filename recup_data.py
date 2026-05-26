"""
Scraper de statistiques FFBB (Fédération Française de BasketBall).
Cible : pages équipe sur ffbb.com (nm1, lf2, pro b, etc.)
"""
import argparse
import csv
import time
import unicodedata
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Indices des colonnes dans le tableau de stats FFBB (structure fixe du site)
COL_NUMERO   = 0
COL_NOM      = 1
COL_MINUTES  = 2
COL_POINTS   = 3
COL_TIRS_2   = 4
COL_TIRS_3   = 5
COL_LF       = 7
COL_REB_TOT  = 11
COL_PASSES   = 12
COL_EVAL     = 19

RETRY_DELAYS = [1, 3, 7]  # secondes entre tentatives


def _normaliser_nom(nom: str) -> str:
    """Normalise un nom pour la jointure : minuscules sans accents."""
    nom = unicodedata.normalize("NFD", nom)
    nom = "".join(c for c in nom if unicodedata.category(c) != "Mn")
    return nom.lower().strip()


def _charger_naissances(fichier: str) -> dict:
    """Charge un CSV 'player;date_naissance' et retourne un dict nom_normalisé → date."""
    naissances = {}
    try:
        with open(fichier, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                cle = _normaliser_nom(row["player"])
                naissances[cle] = row["date_naissance_personne"].strip()
        print(f"[OK] {len(naissances)} dates de naissance chargees depuis '{fichier}'")
    except FileNotFoundError:
        print(f"[WARN] Fichier naissance introuvable : '{fichier}' -- colonne ignoree.")
    return naissances


class FFBBScraper:
    def __init__(self, team_url: str, naissances: dict | None = None):
        self.team_url = team_url
        parsed = urlparse(team_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        self.naissances = naissances or {}
        self.all_data: list[dict] = []

    # ------------------------------------------------------------------
    # Utilitaires réseau
    # ------------------------------------------------------------------

    def _get(self, url: str) -> requests.Response | None:
        """GET avec retry automatique sur erreur réseau ou 5xx."""
        for tentative, delai in enumerate([0] + RETRY_DELAYS, start=1):
            if delai:
                time.sleep(delai)
            try:
                r = requests.get(url, headers=self.headers, timeout=15)
                if r.status_code == 200:
                    return r
                if r.status_code < 500:
                    print(f"   [ERREUR] HTTP {r.status_code} - {url}")
                    return None
                print(f"   [WARN] HTTP {r.status_code} (tentative {tentative}/4) - {url}")
            except requests.RequestException as exc:
                print(f"   [WARN] Erreur reseau (tentative {tentative}/4) : {exc}")
        print(f"   [ERREUR] Abandon apres 4 tentatives - {url}")
        return None

    # ------------------------------------------------------------------
    # Étape 1 : saisons disponibles
    # ------------------------------------------------------------------

    def get_calendars(self, annee_min: int = 2021) -> list[str]:
        print(f"Recherche des saisons sur {self.base_url} (depuis {annee_min})...")
        r = self._get(self.team_url)
        urls_calendrier = []

        if r is None:
            return urls_calendrier

        soup = BeautifulSoup(r.text, "html.parser")
        for link in soup.find_all("a", class_="season"):
            href = link.get("href", "")
            annee_str = href.split("/")[-1]
            if annee_str.isdigit() and int(annee_str) >= annee_min:
                if "/calendrier/" not in href:
                    href = href.replace("/equipe/", "/equipe/calendrier/")
                urls_calendrier.append(urljoin(self.base_url, href))

        print(f"[OK] {len(urls_calendrier)} saison(s) trouvee(s).")
        return urls_calendrier

    # ------------------------------------------------------------------
    # Étape 2 : matchs d'une saison
    # ------------------------------------------------------------------

    def get_matches(self, calendar_url: str) -> list[dict]:
        r = self._get(calendar_url)
        matchs_info = []

        if r is None:
            return matchs_info

        soup = BeautifulSoup(r.text, "html.parser")
        tbody = soup.find("tbody")
        if not tbody:
            return matchs_info

        for ligne in tbody.find_all("tr"):
            colonnes = ligne.find_all("td")
            if len(colonnes) < 4:
                continue

            span_date = colonnes[0].find("span", itemprop="startDate")
            date_match = span_date.text.strip() if span_date else "Date inconnue"

            colonne_score = ligne.find("td", class_="right")
            if not colonne_score:
                continue
            lien = colonne_score.find("a", title="Voir le match")
            if lien and lien.get("href"):
                matchs_info.append({
                    "url": urljoin(self.base_url, lien["href"]),
                    "date": date_match,
                })

        return matchs_info

    # ------------------------------------------------------------------
    # Étape 3 : stats d'un match
    # ------------------------------------------------------------------

    @staticmethod
    def _separer_tirs(stat_str: str) -> tuple[str, str]:
        stat_str = stat_str.strip()
        if "-" in stat_str and stat_str != "-":
            reussi, total = stat_str.split("-", 1)
            return reussi.strip(), total.strip()
        return "0", "0"

    def get_stats(
        self,
        match_url: str,
        date_match: str,
        nom_equipe_cible: str = "pôle france",
    ) -> list[dict]:
        r = self._get(match_url)
        stats_match = []

        if r is None:
            return stats_match

        soup = BeautifulSoup(r.text, "html.parser")

        for section in soup.find_all("section", class_="main__game__table__entry"):
            h2 = section.find("h2", class_="generic__title")
            if not (h2 and nom_equipe_cible in h2.text.strip().lower()):
                continue

            tbody = section.find("tbody")
            if not tbody:
                break

            for ligne in tbody.find_all("tr"):
                colonnes = ligne.find_all("td")
                # Ligne de séparation (colspan) → on saute
                if not colonnes or colonnes[0].has_attr("colspan"):
                    continue
                if len(colonnes) <= COL_EVAL:
                    continue

                t2_r, t2_t = self._separer_tirs(colonnes[COL_TIRS_2].text)
                t3_r, t3_t = self._separer_tirs(colonnes[COL_TIRS_3].text)
                lf_r, lf_t = self._separer_tirs(colonnes[COL_LF].text)

                nom = colonnes[COL_NOM].text.strip()
                naissance = self.naissances.get(_normaliser_nom(nom), "")

                joueur = {
                    "Date": date_match,
                    "Match_URL": match_url,
                    "Numero": colonnes[COL_NUMERO].text.strip(),
                    "Nom": nom,
                    "Date_Naissance": naissance,
                    "Minutes": colonnes[COL_MINUTES].text.strip(),
                    "Points": colonnes[COL_POINTS].text.strip(),
                    "Tirs_2pts_Reussi": t2_r,
                    "Tirs_2pts_Total": t2_t,
                    "Tirs_3pts_Reussi": t3_r,
                    "Tirs_3pts_Total": t3_t,
                    "Lancers_Francs_Reussi": lf_r,
                    "Lancers_Francs_Total": lf_t,
                    "Rebonds_Tot": colonnes[COL_REB_TOT].text.strip(),
                    "Passes_Dec": colonnes[COL_PASSES].text.strip(),
                    "Evaluation": colonnes[COL_EVAL].text.strip(),
                }
                stats_match.append(joueur)
            break  # on a trouvé l'équipe cible, inutile de continuer

        return stats_match

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def run(
        self,
        annee_limite: int = 2021,
        nom_equipe_cible: str = "pôle france",
        pause: float = 0.5,
    ) -> list[dict]:
        calendars = self.get_calendars(annee_min=annee_limite)

        for cal_url in calendars:
            print(f"\nSaison : {cal_url}")
            match_infos = self.get_matches(cal_url)
            print(f"   {len(match_infos)} match(s) trouve(s).")

            for info in match_infos:
                stats = self.get_stats(info["url"], info["date"], nom_equipe_cible)
                self.all_data.extend(stats)
                time.sleep(pause)

        print(f"\n[OK] Scraping termine -- {len(self.all_data)} ligne(s) recuperee(s).")
        return self.all_data

    def export_to_csv(self, filename: str = "stats_equipe.csv") -> None:
        if not self.all_data:
            print("[WARN] Aucune donnee a exporter.")
            return

        keys = self.all_data[0].keys()
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.all_data)
        print(f"[OK] Donnees sauvegardees dans '{filename}'")


# ======================================================================
# Interface en ligne de commande
# ======================================================================

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scraper de stats FFBB — extrait les statistiques d'une équipe.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "url",
        help="URL de la page équipe FFBB (ex: https://nm1.ffbb.com/equipe/13656-pole-france)",
    )
    parser.add_argument(
        "-o", "--output",
        default="stats_equipe.csv",
        help="Nom du fichier CSV de sortie",
    )
    parser.add_argument(
        "-a", "--annee",
        type=int,
        default=2021,
        dest="annee_limite",
        help="Année minimale des saisons à récupérer",
    )
    parser.add_argument(
        "-e", "--equipe",
        default="pôle france",
        dest="nom_equipe",
        help="Nom (partiel) de l'équipe cible dans les feuilles de match",
    )
    parser.add_argument(
        "-n", "--naissances",
        default=None,
        dest="fichier_naissances",
        help="Chemin vers un CSV 'player;date_naissance_personne' pour enrichir les données",
    )
    parser.add_argument(
        "-p", "--pause",
        type=float,
        default=0.5,
        help="Délai (secondes) entre chaque requête de match",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    naissances = {}
    if args.fichier_naissances:
        naissances = _charger_naissances(args.fichier_naissances)

    scraper = FFBBScraper(args.url, naissances=naissances)
    scraper.run(
        annee_limite=args.annee_limite,
        nom_equipe_cible=args.nom_equipe,
        pause=args.pause,
    )
    scraper.export_to_csv(args.output)
