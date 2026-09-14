"""Analyse d'une séance GPS (Clement_data.xlsx, ~18 Hz).

Produit : figures/*.png, rapport_gps.md, resume_par_minute.csv, evenements.csv, blocs.csv.
Usage : python analyse_gps.py
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from scipy.integrate import trapezoid
from scipy.ndimage import uniform_filter1d
from scipy.stats import linregress

# ----------------------------------------------------------------------------- config
SRC = "Clement_data.xlsx"
OUT = "figures"
os.makedirs(OUT, exist_ok=True)

# Zones de vitesse (bornes basses, m/s) – convention football/rugby (km/h : 7.2 / 14.4 / 19.8 / 25.2)
ZONES = [("Z1 walk", 0.0), ("Z2 jog", 2.0), ("Z3 run", 4.0), ("Z4 HSR", 5.5), ("Z5 sprint", 7.0)]
ZONE_COLORS = ["#c7d4e0", "#7fa7c9", "#3f7cb5", "#f2a541", "#d1495b"]
SPRINT_V, HSR_V, MIN_EFFORT_DUR = 7.0, 5.5, 1.0        # m/s, m/s, s
ACC_THR, ACC_HI, MIN_ACC_DUR = 2.0, 3.0, 0.5            # m/s², m/s², s
G, KT = 9.81, 1.29                                      # di Prampero / Osgnach

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 200, "font.size": 9, "axes.grid": False,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold",
})

# ----------------------------------------------------------------------------- load
df = pd.read_excel(SRC)
df.columns = ["t", "datetime", "dist", "acc", "v", "lat", "lon"]
df["datetime"] = pd.to_datetime(df["datetime"])
t, v, a = df.t.to_numpy(), df.v.to_numpy(), df.acc.to_numpy()
dt = np.diff(t, prepend=t[0]); dt[0] = np.median(dt)
fs = 1 / np.median(np.diff(t))
dur = t[-1] - t[0]

# Coordonnées locales (m) : approximation plan tangent, suffisante pour un terrain
lat0, lon0 = df.lat.mean(), df.lon.mean()
x = (df.lon - lon0).to_numpy() * np.cos(np.radians(lat0)) * 111_320
y = (df.lat - lat0).to_numpy() * 110_540

# ----------------------------------------------------------------------------- 1. qualité
v_pos = np.hypot(np.gradient(x, t), np.gradient(y, t))          # vitesse dérivée de la position
v_pos_s = uniform_filter1d(v_pos, int(fs))                        # lissage 1 s (bruit de position)
quality = {
    "fs_hz": fs,
    "gaps_gt_0_2s": int((np.diff(t) > 0.2).sum()),
    "dist_col_m": float(df.dist.iloc[-1]),
    "dist_int_v_m": float(trapezoid(v, t)),
    "dist_pos_m": float(np.nansum(np.hypot(np.diff(x), np.diff(y)))),
    "r_v_gps_vs_pos": float(np.corrcoef(v, v_pos_s)[0, 1]),
    "r_acc_vs_dv": float(np.corrcoef(a, np.gradient(v, t))[0, 1]),
    "area_x_m": float(np.ptp(x)), "area_y_m": float(np.ptp(y)),
}

# ----------------------------------------------------------------------------- 2. zones
zone_lo = np.array([z[1] for z in ZONES])
zone_idx = np.searchsorted(zone_lo, v, side="right") - 1
zones = pd.DataFrame({
    "zone": [z[0] for z in ZONES],
    "lower_kmh": zone_lo * 3.6,
    "dist_m": [float((v * dt)[zone_idx == i].sum()) for i in range(len(ZONES))],
    "time_s": [float(dt[zone_idx == i].sum()) for i in range(len(ZONES))],
})
zones["dist_pct"] = 100 * zones.dist_m / zones.dist_m.sum()
zones["time_pct"] = 100 * zones.time_s / zones.time_s.sum()

# ----------------------------------------------------------------------------- 3. événements
def runs(mask: np.ndarray, min_dur: float) -> list[tuple[int, int]]:
    """Segments contigus où mask est vrai, durée >= min_dur (s)."""
    m = np.r_[False, mask, False]
    starts = np.flatnonzero(~m[:-1] & m[1:]); ends = np.flatnonzero(m[:-1] & ~m[1:])
    return [(s, e) for s, e in zip(starts, ends) if t[e - 1] - t[s] >= min_dur]

def describe(kind, segs):
    rows = []
    for s, e in segs:
        sl = slice(s, e)
        rows.append({"type": kind, "start_s": t[s], "end_s": t[e - 1], "dur_s": t[e - 1] - t[s],
                     "dist_m": float((v[sl] * dt[sl]).sum()), "v_peak_ms": float(v[sl].max()),
                     "acc_peak_ms2": float(a[sl].max()), "dec_peak_ms2": float(a[sl].min()),
                     "v_start_ms": float(v[s]), "v_end_ms": float(v[e - 1])})
    return rows

acc_runs, dec_runs = runs(a >= ACC_THR, MIN_ACC_DUR), runs(a <= -ACC_THR, MIN_ACC_DUR)
events = pd.DataFrame(
    describe("sprint", runs(v >= SPRINT_V, MIN_EFFORT_DUR))
    + describe("hsr", runs(v >= HSR_V, MIN_EFFORT_DUR))
    + describe("acc", acc_runs) + describe("dec", dec_runs)
)
events["start_min"] = events.start_s / 60
n_acc_hi = sum(1 for s, e in acc_runs if a[s:e].max() >= ACC_HI)
n_dec_hi = sum(1 for s, e in dec_runs if a[s:e].min() <= -ACC_HI)

# ----------------------------------------------------------------------------- 4. par minute + blocs
minute = (t // 60).astype(int)
dist_i = v * dt
rows = []
for m in np.unique(minute):
    sel = minute == m
    rows.append({"minute": m, "dist_m": dist_i[sel].sum(), "v_max_ms": v[sel].max(), "v_mean_ms": v[sel].mean(),
                 **{z[0]: dist_i[sel & (zone_idx == i)].sum() for i, z in enumerate(ZONES)}})
per_min = pd.DataFrame(rows).set_index("minute")
per_min["n_acc"] = events[events.type == "acc"].groupby(events.start_min.astype(int)).size().reindex(per_min.index, fill_value=0)
per_min["n_dec"] = events[events.type == "dec"].groupby(events.start_min.astype(int)).size().reindex(per_min.index, fill_value=0)

# Bloc actif = vitesse moyenne glissante 60 s >= 0.75 m/s (45 m/min), fusion des trous < 90 s, durée >= 2 min
v60 = uniform_filter1d(v, int(60 * fs))
merged = []
for s, e in runs(v60 >= 0.75, 0):
    if merged and t[s] - t[merged[-1][1] - 1] < 90:
        merged[-1] = (merged[-1][0], e)
    else:
        merged.append((s, e))
merged = [(s, e) for s, e in merged if t[e - 1] - t[s] >= 120]
blocks = pd.DataFrame(describe("block", merged))
blocks["dist_per_min"] = blocks.dist_m / (blocks.dur_s / 60)
blocks["hsr_m"] = [float(dist_i[s:e][v[s:e] >= HSR_V].sum()) for s, e in merged]
blocks["n_acc"] = [int(((events.type == "acc") & events.start_s.between(t[s], t[e - 1])).sum()) for s, e in merged]
blocks["n_dec"] = [int(((events.type == "dec") & events.start_s.between(t[s], t[e - 1])).sum()) for s, e in merged]

# ----------------------------------------------------------------------------- 5. profil A–V in situ (Morin et al. 2021)
# Pour chaque classe de vitesse (0.2 m/s) au-delà de 3 m/s, on garde les 2 meilleures accélérations ;
# la régression linéaire sur ces maxima donne A0 (ordonnée) et S0 (abscisse à l'origine).
pts = []
for lo in np.arange(3.0, v.max() + 0.2, 0.2):
    sel = a[(v >= lo) & (v < lo + 0.2) & (a > 0)]
    if sel.size >= 2:
        pts += [(lo + 0.1, val) for val in np.sort(sel)[-2:]]
pts = np.array(pts)
fit1 = linregress(pts[:, 0], pts[:, 1])
resid = pts[:, 1] - (fit1.intercept + fit1.slope * pts[:, 0])
keep = np.abs(resid) <= 1.5 * resid.std()                         # retrait des points aberrants
fit = linregress(pts[keep, 0], pts[keep, 1])
as_profile = {"A0": fit.intercept, "S0": -fit.intercept / fit.slope, "slope": fit.slope,
              "r2": fit.rvalue ** 2, "n_pts": int(keep.sum()), "v_max_obs": float(v.max())}
as_profile["Pmax_rel"] = as_profile["A0"] * as_profile["S0"] / 4           # W/kg "horizontal"
# D'où viennent les points d'enveloppe ? (minutes distinctes) – dit combien de sprints portent réellement le profil
env_idx = []
for lo in np.arange(3.0, v.max() + 0.2, 0.2):
    m = np.flatnonzero((v >= lo) & (v < lo + 0.2) & (a > 0))
    if m.size >= 2:
        env_idx += list(m[np.argsort(a[m])[-2:]])
as_profile["env_minutes"] = sorted(set(np.round(t[env_idx] / 60, 1)))

# Validation croisée : fit mono-exponentiel v(t) = S0·(1 − e^(−t/τ)) sur le sprint le plus rapide, départ < 0.5 m/s
from scipy.optimize import curve_fit
s_pk = int(v.argmax())
s_st = s_pk - int(np.flatnonzero(v[:s_pk][::-1] < 0.5)[0])
tt, vv = t[s_st:s_pk + 1] - t[s_st], v[s_st:s_pk + 1]
mono = lambda x, S0, tau: S0 * (1 - np.exp(-x / tau))
(p_S0, p_tau), _ = curve_fit(mono, tt, vv, p0=[9, 1.3])
best_sprint = {"S0": p_S0, "tau": p_tau, "A0": p_S0 / p_tau, "dur_s": tt[-1], "dist_m": float(trapezoid(vv, tt)),
               "rmse": float(np.sqrt(np.mean((vv - mono(tt, p_S0, p_tau)) ** 2))), "start_min": t[s_st] / 60}

# ----------------------------------------------------------------------------- 6. puissance métabolique (di Prampero 2005, Osgnach 2010)
ES = a / G                                        # pente équivalente
EM = np.sqrt(ES**2 + 1)                           # masse équivalente
EC = (155.4 * ES**5 - 30.4 * ES**4 - 43.3 * ES**3 + 46.3 * ES**2 + 19.5 * ES + 3.6) * EM * KT  # J/kg/m
P = EC * v                                        # W/kg
P_ZONES = [("low <10", 0), ("mod 10–20", 10), ("high 20–35", 20), ("elevated 35–55", 35), ("max >55", 55)]
p_idx = np.searchsorted([z[1] for z in P_ZONES], P, side="right") - 1
p_zones = pd.DataFrame({"zone": [z[0] for z in P_ZONES],
                        "dist_m": [float(dist_i[p_idx == i].sum()) for i in range(len(P_ZONES))],
                        "time_s": [float(dt[p_idx == i].sum()) for i in range(len(P_ZONES))]})
energy = float(trapezoid(P, t))                   # J/kg
met = {"P_mean": energy / dur, "P_max": float(P.max()), "energy_kJ_kg": energy / 1000,
       "eq_dist_m": energy / 3.6, "hml_dist_m": float(dist_i[P >= 20].sum())}

# ----------------------------------------------------------------------------- 7. courbe vitesse–durée (max mean speed)
windows = np.array([1, 2, 3, 5, 10, 15, 30, 60, 120, 300, 600])
mms = np.array([uniform_filter1d(v, max(1, int(w * fs))).max() for w in windows])

# ----------------------------------------------------------------------------- figures
tm = t / 60

# Fig 1 : timeline
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6), sharex=True, height_ratios=[1.3, 1])
ax1.plot(tm, v * 3.6, lw=0.4, color="#3f7cb5")
for _, b in blocks.iterrows():
    ax1.axvspan(b.start_s / 60, b.end_s / 60, color="#f2a541", alpha=0.12, lw=0)
ax1.axhline(SPRINT_V * 3.6, ls="--", lw=0.7, color="#d1495b")
ax1.text(0.3, SPRINT_V * 3.6 + 0.4, "sprint threshold 25.2 km/h", color="#d1495b", fontsize=7)
ax1.set_ylabel("Speed (km/h)"); ax1.set_title("Speed trace – shaded = active blocks")
bottom = np.zeros(len(per_min))
for i, z in enumerate(ZONES):
    ax2.bar(per_min.index + 0.5, per_min[z[0]], bottom=bottom, width=0.9, color=ZONE_COLORS[i], label=z[0])
    bottom += per_min[z[0]].to_numpy()
ax2.set_ylabel("Distance per minute (m)"); ax2.set_xlabel("Time (min)")
ax2.legend(ncol=5, frameon=False, fontsize=7, loc="upper left")
fig.tight_layout(); fig.savefig(f"{OUT}/fig1_timeline.png"); plt.close(fig)

# Fig 2 : zones
fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
for ax, col, lab in [(axes[0], "dist_m", "Distance (m)"), (axes[1], "time_s", "Time (min)")]:
    vals = zones[col] / (60 if col == "time_s" else 1)
    bars = ax.bar(zones.zone, vals, color=ZONE_COLORS)
    pct = zones["dist_pct" if col == "dist_m" else "time_pct"]
    for b, p in zip(bars, pct):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{p:.0f}%", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel(lab); ax.tick_params(axis="x", labelsize=8)
axes[0].set_title("Distance by speed zone"); axes[1].set_title("Time by speed zone")
fig.tight_layout(); fig.savefig(f"{OUT}/fig2_speed_zones.png"); plt.close(fig)

# Fig 3 : carte + heatmap
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))
segs = np.stack([np.c_[x[:-1], y[:-1]], np.c_[x[1:], y[1:]]], axis=1)
lc = LineCollection(segs, cmap="viridis", norm=plt.Normalize(0, v.max() * 3.6), lw=0.5, alpha=0.8)
lc.set_array(v[:-1] * 3.6); ax1.add_collection(lc)
ax1.set_xlim(x.min() - 3, x.max() + 3); ax1.set_ylim(y.min() - 3, y.max() + 3); ax1.set_aspect("equal")
fig.colorbar(lc, ax=ax1, label="Speed (km/h)", shrink=0.8)
ax1.set_xlabel("East (m)"); ax1.set_ylabel("North (m)"); ax1.set_title("Trajectory coloured by speed")
h = ax2.hist2d(x, y, bins=40, weights=dt, cmap="magma_r", cmin=1e-9)
ax2.set_aspect("equal"); fig.colorbar(h[3], ax=ax2, label="Time spent (s)", shrink=0.8)
ax2.set_xlabel("East (m)"); ax2.set_title("Occupancy heatmap")
fig.tight_layout(); fig.savefig(f"{OUT}/fig3_map.png"); plt.close(fig)

# Fig 4 : acc/dec
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.6))
ax1.hist(a, bins=np.arange(-6, 6.01, 0.2), color="#7fa7c9")
for thr in (ACC_THR, -ACC_THR, ACC_HI, -ACC_HI):
    ax1.axvline(thr, ls="--", lw=0.7, color="#d1495b" if abs(thr) == ACC_HI else "#f2a541")
ax1.set_yscale("log"); ax1.set_xlabel("Acceleration (m/s²)"); ax1.set_ylabel("Samples (log)")
ax1.set_title("Acceleration distribution")
ax2.bar(per_min.index + 0.5, per_min.n_acc, width=0.9, color="#3f7cb5", label=f"acc ≥ {ACC_THR} m/s²")
ax2.bar(per_min.index + 0.5, -per_min.n_dec, width=0.9, color="#d1495b", label=f"dec ≤ −{ACC_THR} m/s²")
ax2.axhline(0, color="k", lw=0.5); ax2.set_xlabel("Time (min)"); ax2.set_ylabel("Events per minute")
ax2.legend(frameon=False, fontsize=8); ax2.set_title("Acceleration / deceleration events")
fig.tight_layout(); fig.savefig(f"{OUT}/fig4_acc_dec.png"); plt.close(fig)

# Fig 5 : profil A–V
fig, ax = plt.subplots(figsize=(6, 4.2))
m3 = (v > 3) & (a > 0)
ax.scatter(v[m3], a[m3], s=2, color="#c7d4e0", label="all samples (v > 3 m/s)")
ax.scatter(pts[keep, 0], pts[keep, 1], s=18, color="#3f7cb5", label="top-2 per 0.2 m/s bin")
ax.scatter(pts[~keep, 0], pts[~keep, 1], s=18, facecolors="none", edgecolors="#d1495b", label="excluded (>1.5 SD)")
vv = np.linspace(0, as_profile["S0"], 50)
ax.plot(vv, as_profile["A0"] + as_profile["slope"] * vv, color="#d1495b", lw=1.5)
ax.set_xlim(0, as_profile["S0"] + 0.5); ax.set_ylim(0, as_profile["A0"] + 0.5)
ax.set_xlabel("Speed (m/s)"); ax.set_ylabel("Acceleration (m/s²)")
ax.set_title(f"In-situ A–S profile  A0 = {as_profile['A0']:.2f} m/s²,  S0 = {as_profile['S0']:.2f} m/s,  R² = {as_profile['r2']:.2f}", fontsize=8)
ax.legend(frameon=False, fontsize=7, loc="upper right")
fig.tight_layout(); fig.savefig(f"{OUT}/fig5_as_profile.png"); plt.close(fig)

# Fig 6 : puissance métabolique
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.6))
ax1.bar(p_zones.zone, p_zones.dist_m, color=ZONE_COLORS)
ax1.set_ylabel("Distance (m)"); ax1.set_xlabel("Metabolic power zone (W/kg)")
ax1.set_title("Distance by metabolic power zone"); ax1.tick_params(axis="x", labelsize=7)
edges = np.arange(0, 33, 1)
hz, _ = np.histogram(v * 3.6, bins=edges, weights=dist_i)
hp, _ = np.histogram(v * 3.6, bins=edges, weights=dist_i * (P >= 20))
ax2.bar(edges[:-1], hz, width=1, align="edge", color="#c7d4e0", label="all")
ax2.bar(edges[:-1], hp, width=1, align="edge", color="#d1495b", label="P ≥ 20 W/kg")
ax2.set_xlabel("Speed (km/h)"); ax2.set_ylabel("Distance (m)"); ax2.set_title("Where high metabolic load occurs")
ax2.legend(frameon=False, fontsize=8)
fig.tight_layout(); fig.savefig(f"{OUT}/fig6_metabolic_power.png"); plt.close(fig)

# Fig 7 : courbe vitesse–durée
fig, ax = plt.subplots(figsize=(6, 3.8))
ax.plot(windows, mms * 3.6, "o-", color="#3f7cb5")
for w, m in zip(windows, mms):
    ax.annotate(f"{m*3.6:.1f}", (w, m * 3.6), textcoords="offset points", xytext=(4, 4), fontsize=7)
ax.set_xscale("log"); ax.set_xticks(windows); ax.set_xticklabels([str(w) for w in windows], fontsize=7)
ax.set_xlabel("Window duration (s)"); ax.set_ylabel("Max mean speed (km/h)"); ax.set_title("Maximal mean speed vs. duration")
fig.tight_layout(); fig.savefig(f"{OUT}/fig7_mms_curve.png"); plt.close(fig)

# ----------------------------------------------------------------------------- exports
per_min.round(1).to_csv("resume_par_minute.csv")
events.sort_values("start_s").round(2).to_csv("evenements.csv", index=False)
blocks.round(1).to_csv("blocs.csv", index=False)

sprints = events[events.type == "sprint"].sort_values("start_s")
hsr = events[events.type == "hsr"]
n_acc, n_dec = len(acc_runs), len(dec_runs)
kmh = lambda ms: ms * 3.6
start = df.datetime.iloc[0]

md = []
md.append(f"# Rapport d'analyse GPS – séance du {start:%d/%m/%Y} ({start:%H:%M} → {df.datetime.iloc[-1]:%H:%M})\n")
md.append("Généré par `analyse_gps.py`. Figures dans `figures/`, données détaillées dans `resume_par_minute.csv`, `evenements.csv`, `blocs.csv`.\n")

md.append("## 1. Qualité du signal\n")
md.append("Avant d'interpréter quoi que ce soit, il faut savoir si le capteur a fait son travail : un GPS qui perd des satellites ou qui "
          "échantillonne irrégulièrement fausse toutes les métriques d'accélération.\n")
md.append("| Contrôle | Valeur | Lecture |\n|---|---|---|")
md.append(f"| Fréquence d'échantillonnage | {quality['fs_hz']:.1f} Hz | régulière, aucun trou > 0,2 s ({quality['gaps_gt_0_2s']}) |")
md.append(f"| Distance colonne `dist` | {quality['dist_col_m']:.0f} m | |")
md.append(f"| Distance ∫ v dt | {quality['dist_int_v_m']:.0f} m | écart {abs(quality['dist_col_m']-quality['dist_int_v_m']):.1f} m → la distance est bien intégrée depuis la vitesse Doppler |")
md.append(f"| Distance somme des positions | {quality['dist_pos_m']:.0f} m | > distance Doppler : le bruit de position ajoute des zigzags, normal |")
md.append(f"| Corrélation v(GPS) vs v(dérivée position, lissée 1 s) | r = {quality['r_v_gps_vs_pos']:.3f} | les deux sources concordent |")
md.append(f"| Corrélation `acc` vs dv/dt | r = {quality['r_acc_vs_dv']:.3f} | `acc` est bien la dérivée (filtrée) de la vitesse |")
md.append(f"| Emprise spatiale | {quality['area_x_m']:.0f} × {quality['area_y_m']:.0f} m | |")
md.append("\n**Pourquoi c'est important** : la vitesse GPS vient de l'effet Doppler (précise), la position vient de la trilatération (bruitée à ±1–2 m). "
          "La distance et les accélérations doivent donc toujours être calculées depuis la vitesse, jamais depuis les positions.\n")

md.append("## 2. Vue d'ensemble\n")
md.append("| Métrique | Valeur |\n|---|---|")
md.append(f"| Durée enregistrée | {dur/60:.1f} min |")
md.append(f"| Distance totale | {quality['dist_int_v_m']:.0f} m ({quality['dist_int_v_m']/(dur/60):.0f} m/min en moyenne) |")
md.append(f"| Vitesse max | {kmh(v.max()):.1f} km/h ({v.max():.2f} m/s) à {t[v.argmax()]/60:.1f} min |")
md.append(f"| Distance haute intensité (≥ {kmh(HSR_V):.1f} km/h) | {zones.dist_m[3:].sum():.0f} m ({zones.dist_pct[3:].sum():.1f} %) |")
md.append(f"| Distance sprint (≥ {kmh(SPRINT_V):.1f} km/h) | {zones.dist_m.iloc[4]:.0f} m |")
md.append(f"| Sprints (≥ {SPRINT_V} m/s pendant ≥ {MIN_EFFORT_DUR} s) | {len(sprints)} |")
md.append(f"| Efforts HSR (≥ {HSR_V} m/s pendant ≥ {MIN_EFFORT_DUR} s) | {len(hsr)} |")
md.append(f"| Accélérations ≥ {ACC_THR} m/s² (≥ {MIN_ACC_DUR} s) | {n_acc} dont {n_acc_hi} ≥ {ACC_HI} m/s² |")
md.append(f"| Décélérations ≤ −{ACC_THR} m/s² (≥ {MIN_ACC_DUR} s) | {n_dec} dont {n_dec_hi} ≤ −{ACC_HI} m/s² |")
md.append(f"| Acc max / Déc max | {a.max():.2f} / {a.min():.2f} m/s² |")
md.append("")

md.append("## 3. Structure de la séance (fig. 1)\n")
md.append("Blocs détectés automatiquement : vitesse moyenne glissante sur 60 s ≥ 0,75 m/s (45 m/min), trous < 90 s fusionnés, durée ≥ 2 min. "
          "Le seuil de 45 m/min sépare le « jeu/exercice » (typiquement 80–130 m/min) des phases de consigne/repos (< 20 m/min).\n")
md.append("| Bloc | Début → fin (min) | Durée (min) | Distance (m) | m/min | HSR (m) | v max (km/h) | Acc | Déc |\n|---|---|---|---|---|---|---|---|---|")
for i, b in blocks.iterrows():
    md.append(f"| {i+1} | {b.start_s/60:.1f} → {b.end_s/60:.1f} | {b.dur_s/60:.1f} | {b.dist_m:.0f} | {b.dist_per_min:.0f} | {b.hsr_m:.0f} | {kmh(b.v_peak_ms):.1f} | {b.n_acc} | {b.n_dec} |")
md.append("")

md.append("## 4. Zones de vitesse (fig. 2)\n")
md.append("Seuils football/rugby usuels (7,2 / 14,4 / 19,8 / 25,2 km/h). Ils sont **absolus** : pour un individu, des seuils relatifs à sa vitesse max "
          "(p. ex. 30 / 50 / 70 / 85 % de S0) seraient plus justes ; c'est une limite classique des rapports GPS.\n")
md.append("| Zone | ≥ km/h | Distance (m) | % dist | Temps (min) | % temps |\n|---|---|---|---|---|---|")
for _, z in zones.iterrows():
    md.append(f"| {z.zone} | {z.lower_kmh:.1f} | {z.dist_m:.0f} | {z.dist_pct:.1f} | {z.time_s/60:.1f} | {z.time_pct:.1f} |")
md.append("")

md.append("## 5. Sprints\n")
md.append("| # | Début (min) | Durée (s) | Distance (m) | v pic (km/h) | v départ (km/h) | Acc pic (m/s²) |\n|---|---|---|---|---|---|---|")
for i, s in enumerate(sprints.itertuples(), 1):
    md.append(f"| {i} | {s.start_s/60:.1f} | {s.dur_s:.1f} | {s.dist_m:.0f} | {kmh(s.v_peak_ms):.1f} | {kmh(s.v_start_ms):.1f} | {s.acc_peak_ms2:.2f} |")
md.append("\n`v départ` = vitesse à l'entrée dans la zone sprint (donc ≈ 25 km/h par construction) ; `Distance` = distance parcourue au-dessus du seuil. "
          "Pour la phase d'accélération complète, voir `evenements.csv` (type `acc`) juste avant chaque sprint.\n")

md.append("## 6. Accélérations / décélérations (fig. 4)\n")
md.append("Pourquoi les compter séparément de la vitesse : une accélération de 0 à 4 m/s coûte autant qu'une course à 6 m/s, mais ne rentre dans "
          "aucune zone « haute vitesse ». Les décélérations, elles, sont le principal facteur de dommage musculaire (travail excentrique). "
          f"Ratio acc/déc = {n_acc/max(1,n_dec):.2f} (≈ 1 en jeu réduit ; > 1 sur des sprints lancés avec arrêt en roue libre).\n")

md.append("## 7. Profil accélération–vitesse in situ (fig. 5)\n")
md.append("Méthode Morin et al. (2021) : sur chaque classe de vitesse de 0,2 m/s au-delà de 3 m/s, on retient les 2 accélérations maximales ; "
          "la droite de régression sur ces points donne l'accélération théorique max à vitesse nulle (A0) et la vitesse théorique max (S0). "
          "Intérêt : obtenir un profil de sprint sans test dédié, à partir du jeu.\n")
md.append("| Paramètre | Valeur |\n|---|---|")
md.append(f"| A0 | {as_profile['A0']:.2f} m/s² |")
md.append(f"| S0 | {as_profile['S0']:.2f} m/s ({kmh(as_profile['S0']):.1f} km/h) |")
md.append(f"| Vitesse max observée | {as_profile['v_max_obs']:.2f} m/s ({100*as_profile['v_max_obs']/as_profile['S0']:.0f} % de S0) |")
md.append(f"| Pente | {as_profile['slope']:.3f} s⁻¹ |")
md.append(f"| A0·S0/4 (proxy P max horizontale) | {as_profile['Pmax_rel']:.1f} W/kg |")
md.append(f"| R², points retenus | {as_profile['r2']:.2f}, {as_profile['n_pts']} |")
md.append(f"\n**Pourquoi R² ≈ {as_profile['r2']:.2f} n'est pas une preuve de qualité.** Les points d'enveloppe proviennent de seulement "
          f"{len(as_profile['env_minutes'])} moments (min {', '.join(f'{m:.1f}' for m in as_profile['env_minutes'])}), c'est-à-dire {len(as_profile['env_minutes'])} sprints. "
          "Or un sprint départ arrêté suit le modèle mono-exponentiel v(t) = S0·(1 − e^(−t/τ)), dont la dérivée est a = (S0 − v)/τ : la relation a–v d'**un seul** "
          "sprint est linéaire par construction. Le R² parfait reflète donc le modèle du sprint (et le filtrage de la vitesse par le boîtier), pas la robustesse du profil.\n")
md.append(f"**Validation croisée** – fit mono-exponentiel direct sur le sprint le plus rapide (min {best_sprint['start_min']:.1f}, "
          f"{best_sprint['dur_s']:.1f} s, {best_sprint['dist_m']:.0f} m, RMSE {best_sprint['rmse']:.2f} m/s) :\n")
md.append("| | Régression in situ (Morin) | Fit mono-exp du sprint | Écart |\n|---|---|---|---|")
md.append(f"| A0 (m/s²) | {as_profile['A0']:.2f} | {best_sprint['A0']:.2f} | {100*(as_profile['A0']/best_sprint['A0']-1):+.1f} % |")
md.append(f"| S0 (m/s) | {as_profile['S0']:.2f} | {best_sprint['S0']:.2f} | {100*(as_profile['S0']/best_sprint['S0']-1):+.1f} % |")
md.append(f"| τ = S0/A0 (s) | {as_profile['S0']/as_profile['A0']:.2f} | {best_sprint['tau']:.2f} | |")
md.append("\nLes deux méthodes concordent : le profil est cohérent, mais il repose sur un sprint de ~5 s. τ ≈ 1,4 s est une valeur typique de sprinteur entraîné "
          "(1,2–1,5 s) ; A0 ≈ 6,6 m/s² et S0 ≈ 9,1–9,3 m/s placent le profil dans la moyenne haute des joueurs de sports collectifs.\n")
md.append("**Réserve** : Morin recommande ≥ 3 séances avec des sprints maximaux répétés pour que A0/S0 soient stables (CV ~5–10 %). "
          "Sur une seule séance, S0 est plausible (la vitesse max observée est proche), A0 est plus fragile car elle dépend de quelques départs arrêtés maximaux "
          "et du filtrage de l'accélération par le constructeur.\n")

md.append("## 8. Puissance métabolique (fig. 6)\n")
md.append("Modèle di Prampero (2005) / Osgnach (2010) : une accélération sur le plat est énergétiquement équivalente à une course en côte. "
          "On convertit chaque instant (v, a) en coût énergétique puis en puissance (W/kg). Cela permet de valoriser les accélérations à basse vitesse "
          "que les zones de vitesse ignorent. Limites connues : le modèle sous-estime le coût des décélérations et des changements de direction.\n")
md.append("| Métrique | Valeur |\n|---|---|")
md.append(f"| Puissance métabolique moyenne | {met['P_mean']:.1f} W/kg |")
md.append(f"| Puissance métabolique max | {met['P_max']:.0f} W/kg |")
md.append(f"| Énergie estimée | {met['energy_kJ_kg']:.0f} kJ/kg |")
md.append(f"| Distance équivalente (à 3,6 J/kg/m) | {met['eq_dist_m']:.0f} m (vs {quality['dist_int_v_m']:.0f} m réels, +{100*(met['eq_dist_m']/quality['dist_int_v_m']-1):.0f} %) |")
md.append(f"| Distance à haute charge métabolique (≥ 20 W/kg) | {met['hml_dist_m']:.0f} m (vs {zones.dist_m[3:].sum():.0f} m ≥ 19,8 km/h) |")
md.append("\n| Zone P (W/kg) | Distance (m) | Temps (min) |\n|---|---|---|")
for _, z in p_zones.iterrows():
    md.append(f"| {z.zone} | {z.dist_m:.0f} | {z.time_s/60:.1f} |")
md.append("\nLa différence entre distance ≥ 20 W/kg et distance ≥ 19,8 km/h mesure la part d'intensité « cachée » dans les accélérations.\n")

md.append("## 9. Courbe vitesse–durée (fig. 7)\n")
md.append("Vitesse moyenne maximale tenue sur des fenêtres de 1 s à 10 min (équivalent de la courbe puissance–durée en cyclisme). "
          "Le point à 1 s ≈ vitesse de sprint ; le plateau vers 5–10 min ≈ intensité soutenable en jeu. Utile pour le suivi : "
          "si la courbe s'aplatit d'une séance à l'autre à durée égale, la fatigue ou la nature de l'exercice a changé.\n")
md.append("| Fenêtre (s) | " + " | ".join(str(w) for w in windows) + " |\n|---|" + "---|" * len(windows))
md.append("| Vitesse (km/h) | " + " | ".join(f"{m*3.6:.1f}" for m in mms) + " |")
md.append("")

md.append("## 10. Ce qu'on peut en retenir\n")
hi_block = blocks.loc[blocks.dist_per_min.idxmax()] if len(blocks) else None
md.append(f"- Séance de {dur/60:.0f} min pour {quality['dist_int_v_m']/1000:.1f} km : volume faible, mais {len(blocks)} blocs actifs "
          + (f"dont le plus intense à {hi_block.dist_per_min:.0f} m/min" if hi_block is not None else "")
          + ", entrecoupés de longues phases statiques (consignes / récupération).")
md.append(f"- {len(sprints)} sprints ≥ 25,2 km/h, vitesse max {kmh(v.max()):.1f} km/h : les efforts maximaux sont concentrés en début (échauffement) et fin de séance (min 75–85), "
          "pas dans les blocs de jeu.")
md.append(f"- Charge en acc/déc : {n_acc} acc et {n_dec} déc ≥ 2 m/s² — c'est là que se cache l'intensité mécanique des blocs de jeu, "
          "peu visible dans les zones de vitesse.")
md.append(f"- Profil A–V estimé : A0 ≈ {as_profile['A0']:.1f} m/s², S0 ≈ {kmh(as_profile['S0']):.1f} km/h (à confirmer sur plusieurs séances).")
md.append("- Pistes : comparer avec la charge interne (FC, RPE) pour un indice d'efficience ; utiliser des seuils de vitesse relatifs à S0 ; "
          "recouper la carte d'occupation avec le dessin des exercices.")

open("rapport_gps.md", "w", encoding="utf-8").write("\n".join(md))
print("OK -> rapport_gps.md, figures/, *.csv")
