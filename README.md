# FFBB Stats Scraper

Outil Python pour extraire les statistiques individuelles d'une équipe depuis le site de la **Fédération Française de BasketBall** (ffbb.com — NM1, LF2, Pro B, etc.).

## Ce que ça fait

Le scraper parcourt automatiquement toutes les saisons disponibles pour une équipe donnée, récupère chaque feuille de match et extrait les stats des joueurs :

| Colonne | Description |
|---|---|
| Date | Date du match |
| Match_URL | Lien vers la feuille officielle |
| Numero | Numéro de maillot |
| Nom | Nom du joueur |
| Date_Naissance | Date de naissance (si fichier fourni) |
| Minutes | Temps de jeu |
| Points | Points marqués |
| Tirs_2pts_Reussi / Total | Tirs à 2 points |
| Tirs_3pts_Reussi / Total | Tirs à 3 points |
| Lancers_Francs_Reussi / Total | Lancers francs |
| Rebonds_Tot | Rebonds totaux |
| Passes_Dec | Passes décisives |
| Evaluation | Note d'évaluation FFBB |

## Installation

```bash
pip install requests beautifulsoup4
```

## Utilisation

### Exemple rapide

```bash
# Pôle France masculin (NM1), depuis 2021
python recup_data.py https://nm1.ffbb.com/equipe/256-pole-france -o stats_H.csv

# Pôle France féminin (LF2), depuis 2021
python recup_data.py https://lf2.ffbb.com/equipe/calendrier/13656-pole-france -o stats_F.csv
```

### Avec enrichissement des dates de naissance

```bash
# Les deux équipes avec les dates de naissance
python recup_data.py https://nm1.ffbb.com/equipe/256-pole-france -o stats_H.csv -n naissance.csv
python recup_data.py https://lf2.ffbb.com/equipe/calendrier/13656-pole-france -o stats_F.csv -n naissance.csv
```

### Toutes les options

```
usage: recup_data.py [-h] [-o OUTPUT] [-a ANNEE_LIMITE] [-e NOM_EQUIPE]
                     [-n FICHIER_NAISSANCES] [-p PAUSE]
                     url

Arguments positionnels:
  url                   URL de la page équipe FFBB

Options:
  -o, --output          Fichier CSV de sortie             [défaut: stats_equipe.csv]
  -a, --annee           Année minimale des saisons        [défaut: 2021]
  -e, --equipe          Nom partiel de l'équipe cible     [défaut: "pôle france"]
  -n, --naissances      Fichier CSV player;date_naissance [optionnel]
  -p, --pause           Délai entre requêtes (secondes)   [défaut: 0.5]
```

### Changer d'équipe cible

Le paramètre `-e` filtre le nom de l'équipe dans les feuilles de match (insensible à la casse) :

```bash
# Récupérer les stats de "Levallois" sur leur propre page équipe
python recup_data.py https://nm1.ffbb.com/equipe/calendrier/XXXX-levallois -e "levallois"
```

## Format du fichier naissances

Le fichier CSV doit être séparé par des **points-virgules** :

```csv
player;date_naissance_personne
Mehdi CHAOUAD;15/01/2008
Nathan SOLIMAN;14/05/2009
```

La correspondance avec les noms de joueurs est insensible à la casse et aux accents.

## Fonctionnement interne

```
URL équipe
   │
   ▼
get_calendars()  →  liste d'URLs de calendrier par saison
   │
   ▼ (pour chaque saison)
get_matches()    →  liste de { url_match, date }
   │
   ▼ (pour chaque match)
get_stats()      →  stats de chaque joueur de l'équipe cible
   │
   ▼
export_to_csv()  →  fichier CSV
```

Le scraper intègre un **retry automatique** (jusqu'à 4 tentatives avec backoff exponentiel) sur les erreurs réseau et les erreurs HTTP 5xx.

## Fichiers du projet

```
NM1_recup/
├── recup_data.py                     # scraper principal
├── naissance.csv                     # dates de naissance joueurs Pôle France
├── stats_pole_franceH_avec_dates.csv # exemple de sortie (équipe masculine)
├── stats_pole_franceF_avec_dates.csv # exemple de sortie (équipe féminine)
└── README.md
```
