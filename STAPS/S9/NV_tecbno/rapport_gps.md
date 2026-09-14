# Rapport d'analyse GPS – séance du 14/09/2026 (09:32 → 10:59)

Généré par `analyse_gps.py`. Figures dans `figures/`, données détaillées dans `resume_par_minute.csv`, `evenements.csv`, `blocs.csv`.

## 1. Qualité du signal

Avant d'interpréter quoi que ce soit, il faut savoir si le capteur a fait son travail : un GPS qui perd des satellites ou qui échantillonne irrégulièrement fausse toutes les métriques d'accélération.

| Contrôle | Valeur | Lecture |
|---|---|---|
| Fréquence d'échantillonnage | 18.2 Hz | régulière, aucun trou > 0,2 s (0) |
| Distance colonne `dist` | 5263 m | |
| Distance ∫ v dt | 5263 m | écart 0.2 m → la distance est bien intégrée depuis la vitesse Doppler |
| Distance somme des positions | 5924 m | > distance Doppler : le bruit de position ajoute des zigzags, normal |
| Corrélation v(GPS) vs v(dérivée position, lissée 1 s) | r = 0.995 | les deux sources concordent |
| Corrélation `acc` vs dv/dt | r = 0.955 | `acc` est bien la dérivée (filtrée) de la vitesse |
| Emprise spatiale | 76 × 72 m | |

**Pourquoi c'est important** : la vitesse GPS vient de l'effet Doppler (précise), la position vient de la trilatération (bruitée à ±1–2 m). La distance et les accélérations doivent donc toujours être calculées depuis la vitesse, jamais depuis les positions.

## 2. Vue d'ensemble

| Métrique | Valeur |
|---|---|
| Durée enregistrée | 86.6 min |
| Distance totale | 5263 m (61 m/min en moyenne) |
| Vitesse max | 31.6 km/h (8.79 m/s) à 14.1 min |
| Distance haute intensité (≥ 19.8 km/h) | 427 m (8.1 %) |
| Distance sprint (≥ 25.2 km/h) | 166 m |
| Sprints (≥ 7.0 m/s pendant ≥ 1.0 s) | 9 |
| Efforts HSR (≥ 5.5 m/s pendant ≥ 1.0 s) | 16 |
| Accélérations ≥ 2.0 m/s² (≥ 0.5 s) | 39 dont 20 ≥ 3.0 m/s² |
| Décélérations ≤ −2.0 m/s² (≥ 0.5 s) | 35 dont 15 ≤ −3.0 m/s² |
| Acc max / Déc max | 4.59 / -5.43 m/s² |

## 3. Structure de la séance (fig. 1)

Blocs détectés automatiquement : vitesse moyenne glissante sur 60 s ≥ 0,75 m/s (45 m/min), trous < 90 s fusionnés, durée ≥ 2 min. Le seuil de 45 m/min sépare le « jeu/exercice » (typiquement 80–130 m/min) des phases de consigne/repos (< 20 m/min).

| Bloc | Début → fin (min) | Durée (min) | Distance (m) | m/min | HSR (m) | v max (km/h) | Acc | Déc |
|---|---|---|---|---|---|---|---|---|
| 1 | 7.3 → 15.0 | 7.7 | 589 | 77 | 182 | 31.6 | 3 | 1 |
| 2 | 16.8 → 19.3 | 2.5 | 165 | 67 | 0 | 18.8 | 1 | 1 |
| 3 | 20.9 → 25.3 | 4.4 | 198 | 45 | 0 | 17.2 | 1 | 0 |
| 4 | 27.0 → 45.5 | 18.5 | 1740 | 94 | 82 | 27.3 | 15 | 13 |
| 5 | 49.7 → 69.6 | 20.0 | 1795 | 90 | 67 | 23.0 | 15 | 17 |
| 6 | 73.9 → 77.4 | 3.5 | 196 | 56 | 39 | 30.1 | 2 | 2 |

## 4. Zones de vitesse (fig. 2)

Seuils football/rugby usuels (7,2 / 14,4 / 19,8 / 25,2 km/h). Ils sont **absolus** : pour un individu, des seuils relatifs à sa vitesse max (p. ex. 30 / 50 / 70 / 85 % de S0) seraient plus justes ; c'est une limite classique des rapports GPS.

| Zone | ≥ km/h | Distance (m) | % dist | Temps (min) | % temps |
|---|---|---|---|---|---|
| Z1 walk | 0.0 | 2865 | 54.4 | 75.4 | 87.0 |
| Z2 jog | 7.2 | 1360 | 25.9 | 8.0 | 9.3 |
| Z3 run | 14.4 | 610 | 11.6 | 2.2 | 2.5 |
| Z4 HSR | 19.8 | 261 | 5.0 | 0.7 | 0.8 |
| Z5 sprint | 25.2 | 166 | 3.2 | 0.4 | 0.4 |

## 5. Sprints

| # | Début (min) | Durée (s) | Distance (m) | v pic (km/h) | v départ (km/h) | Acc pic (m/s²) |
|---|---|---|---|---|---|---|
| 1 | 9.4 | 2.0 | 15 | 27.5 | 25.3 | 0.97 |
| 2 | 10.9 | 2.5 | 19 | 27.9 | 25.3 | 0.73 |
| 3 | 14.0 | 4.5 | 37 | 31.6 | 25.2 | 1.56 |
| 4 | 29.8 | 2.1 | 16 | 27.3 | 25.3 | 0.93 |
| 5 | 39.6 | 1.1 | 8 | 26.9 | 25.2 | 0.85 |
| 6 | 75.1 | 1.5 | 12 | 28.4 | 25.5 | 1.47 |
| 7 | 76.9 | 1.6 | 13 | 30.1 | 25.4 | 1.65 |
| 8 | 81.9 | 1.5 | 12 | 27.8 | 25.3 | 1.25 |
| 9 | 84.6 | 3.7 | 29 | 30.1 | 25.2 | 1.27 |

`v départ` = vitesse à l'entrée dans la zone sprint (donc ≈ 25 km/h par construction) ; `Distance` = distance parcourue au-dessus du seuil. Pour la phase d'accélération complète, voir `evenements.csv` (type `acc`) juste avant chaque sprint.

## 6. Accélérations / décélérations (fig. 4)

Pourquoi les compter séparément de la vitesse : une accélération de 0 à 4 m/s coûte autant qu'une course à 6 m/s, mais ne rentre dans aucune zone « haute vitesse ». Les décélérations, elles, sont le principal facteur de dommage musculaire (travail excentrique). Ratio acc/déc = 1.11 (≈ 1 en jeu réduit ; > 1 sur des sprints lancés avec arrêt en roue libre).

## 7. Profil accélération–vitesse in situ (fig. 5)

Méthode Morin et al. (2021) : sur chaque classe de vitesse de 0,2 m/s au-delà de 3 m/s, on retient les 2 accélérations maximales ; la droite de régression sur ces points donne l'accélération théorique max à vitesse nulle (A0) et la vitesse théorique max (S0). Intérêt : obtenir un profil de sprint sans test dédié, à partir du jeu.

| Paramètre | Valeur |
|---|---|
| A0 | 6.65 m/s² |
| S0 | 9.33 m/s (33.6 km/h) |
| Vitesse max observée | 8.79 m/s (94 % de S0) |
| Pente | -0.712 s⁻¹ |
| A0·S0/4 (proxy P max horizontale) | 15.5 W/kg |
| R², points retenus | 1.00, 50 |

**Pourquoi R² ≈ 1.00 n'est pas une preuve de qualité.** Les points d'enveloppe proviennent de seulement 5 moments (min 14.0, 14.1, 75.0, 76.9, 84.6), c'est-à-dire 5 sprints. Or un sprint départ arrêté suit le modèle mono-exponentiel v(t) = S0·(1 − e^(−t/τ)), dont la dérivée est a = (S0 − v)/τ : la relation a–v d'**un seul** sprint est linéaire par construction. Le R² parfait reflète donc le modèle du sprint (et le filtrage de la vitesse par le boîtier), pas la robustesse du profil.

**Validation croisée** – fit mono-exponentiel direct sur le sprint le plus rapide (min 14.0, 4.8 s, 31 m, RMSE 0.08 m/s) :

| | Régression in situ (Morin) | Fit mono-exp du sprint | Écart |
|---|---|---|---|
| A0 (m/s²) | 6.65 | 6.63 | +0.2 % |
| S0 (m/s) | 9.33 | 9.06 | +3.0 % |
| τ = S0/A0 (s) | 1.40 | 1.37 | |

Les deux méthodes concordent : le profil est cohérent, mais il repose sur un sprint de ~5 s. τ ≈ 1,4 s est une valeur typique de sprinteur entraîné (1,2–1,5 s) ; A0 ≈ 6,6 m/s² et S0 ≈ 9,1–9,3 m/s placent le profil dans la moyenne haute des joueurs de sports collectifs.

**Réserve** : Morin recommande ≥ 3 séances avec des sprints maximaux répétés pour que A0/S0 soient stables (CV ~5–10 %). Sur une seule séance, S0 est plausible (la vitesse max observée est proche), A0 est plus fragile car elle dépend de quelques départs arrêtés maximaux et du filtrage de l'accélération par le constructeur.

## 8. Puissance métabolique (fig. 6)

Modèle di Prampero (2005) / Osgnach (2010) : une accélération sur le plat est énergétiquement équivalente à une course en côte. On convertit chaque instant (v, a) en coût énergétique puis en puissance (W/kg). Cela permet de valoriser les accélérations à basse vitesse que les zones de vitesse ignorent. Limites connues : le modèle sous-estime le coût des décélérations et des changements de direction.

| Métrique | Valeur |
|---|---|
| Puissance métabolique moyenne | 5.2 W/kg |
| Puissance métabolique max | 91 W/kg |
| Énergie estimée | 27 kJ/kg |
| Distance équivalente (à 3,6 J/kg/m) | 7574 m (vs 5263 m réels, +44 %) |
| Distance à haute charge métabolique (≥ 20 W/kg) | 1061 m (vs 427 m ≥ 19,8 km/h) |

| Zone P (W/kg) | Distance (m) | Temps (min) |
|---|---|---|
| low <10 | 3138 | 76.6 |
| mod 10–20 | 1064 | 5.9 |
| high 20–35 | 656 | 2.8 |
| elevated 35–55 | 279 | 0.9 |
| max >55 | 125 | 0.4 |

La différence entre distance ≥ 20 W/kg et distance ≥ 19,8 km/h mesure la part d'intensité « cachée » dans les accélérations.

## 9. Courbe vitesse–durée (fig. 7)

Vitesse moyenne maximale tenue sur des fenêtres de 1 s à 10 min (équivalent de la courbe puissance–durée en cyclisme). Le point à 1 s ≈ vitesse de sprint ; le plateau vers 5–10 min ≈ intensité soutenable en jeu. Utile pour le suivi : si la courbe s'aplatit d'une séance à l'autre à durée égale, la fatigue ou la nature de l'exercice a changé.

| Fenêtre (s) | 1 | 2 | 3 | 5 | 10 | 15 | 30 | 60 | 120 | 300 | 600 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Vitesse (km/h) | 31.4 | 31.0 | 30.3 | 28.8 | 24.0 | 19.0 | 12.5 | 10.2 | 9.0 | 7.5 | 6.4 |

## 10. Ce qu'on peut en retenir

- Séance de 87 min pour 5.3 km : volume faible, mais 6 blocs actifs dont le plus intense à 94 m/min, entrecoupés de longues phases statiques (consignes / récupération).
- 9 sprints ≥ 25,2 km/h, vitesse max 31.6 km/h : les efforts maximaux sont concentrés en début (échauffement) et fin de séance (min 75–85), pas dans les blocs de jeu.
- Charge en acc/déc : 39 acc et 35 déc ≥ 2 m/s² — c'est là que se cache l'intensité mécanique des blocs de jeu, peu visible dans les zones de vitesse.
- Profil A–V estimé : A0 ≈ 6.6 m/s², S0 ≈ 33.6 km/h (à confirmer sur plusieurs séances).
- Pistes : comparer avec la charge interne (FC, RPE) pour un indice d'efficience ; utiliser des seuils de vitesse relatifs à S0 ; recouper la carte d'occupation avec le dessin des exercices.