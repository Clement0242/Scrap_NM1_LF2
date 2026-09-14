"""Calculs locomotion / mécanique / métabolique sur une trace GPS.

Références :
- Osgnach C, di Prampero PE, Zamparo P, Morin JB, Pavei G (2023) Mechanical and metabolic power in
  accelerated running – Part II: team sports. Eur J Appl Physiol.  (#burst, #MPE, highEW, EPthr = 80 % EP_ASP)
- di Prampero PE, Osgnach C, Morin JB, Zamparo P, Pavei G (2023) Part I: the 100-m dash.
  Pext = Wext_const·v + a·v, Wext_const = 1.3 − 0.4/v (Pavei 2019), Cr = 3.8 J/kg/m, k = 0.01.
- di Prampero PE, Osgnach C (2018) Metabolic power in team sports – Part 1. Int J Sports Med.
  ES = (a + k·v²)/g, EM = sqrt(a²/g² + 1), ECr = Minetti(ES)·EM.
- Minetti AE et al. (2002) polynôme coût énergétique vs pente, valide pour |i| ≤ 0.45.
- Morin JB et al. (2021) Acceleration-Speed Profile in-situ.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

G = 9.81
K_AIR = 0.01          # J·s²·kg⁻¹·m⁻³ (Pugh 1970 ; di Prampero 1986)
ES_LIMIT = 0.45       # bornes de validité du polynôme de Minetti


# ---------------------------------------------------------------------------
# Événements (bouts contigus au-dessus d'un masque)
# ---------------------------------------------------------------------------
def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Indices [start, end) des suites contiguës de True."""
    m = np.asarray(mask, dtype=int)
    edges = np.diff(np.concatenate(([0], m, [0])))
    return list(zip(np.where(edges == 1)[0], np.where(edges == -1)[0]))


def merge_runs(bouts: list[tuple[int, int]], t: np.ndarray, gap_s: float) -> list[tuple[int, int]]:
    """Fusionne les bouts séparés de moins de gap_s secondes."""
    if gap_s <= 0 or not bouts:
        return bouts
    out = [bouts[0]]
    for s, e in bouts[1:]:
        ps, pe = out[-1]
        if t[s] - t[pe - 1] <= gap_s:
            out[-1] = (ps, e)
        else:
            out.append((s, e))
    return out


def events_table(mask: np.ndarray, df: pd.DataFrame, min_dur: float, gap_s: float = 0.0,
                 extra: dict[str, np.ndarray] | None = None) -> pd.DataFrame:
    """Table des bouts où `mask` est vrai pendant ≥ min_dur s.

    extra : {nom: série} → ajoute moyenne, pic et intégrale (·dt) de chaque série sur le bout.
    """
    t = df["t"].to_numpy()
    dt = df["dt"].to_numpy()
    spd = df["speed"].to_numpy()
    dist = df["dist"].to_numpy()
    extra = extra or {}
    rows = []
    for s, e in merge_runs(runs(mask), t, gap_s):
        dur = t[e - 1] - t[s] + dt[s]
        if dur < min_dur:
            continue
        row = dict(
            debut_s=t[s], fin_s=t[e - 1], duree_s=dur,
            v_debut=spd[s], v_fin=spd[e - 1], v_max=spd[s:e].max(),
            distance_m=dist[e - 1] - dist[s],
        )
        for name, arr in extra.items():
            seg = arr[s:e]
            row[f"{name}_moy"] = seg.mean()
            row[f"{name}_pic"] = seg[np.argmax(np.abs(seg))]
            row[f"{name}_int"] = float(np.sum(seg * dt[s:e]))
        rows.append(row)
    cols = ["debut_s", "fin_s", "duree_s", "v_debut", "v_fin", "v_max", "distance_m"]
    for name in extra:
        cols += [f"{name}_moy", f"{name}_pic", f"{name}_int"]
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# ASP in-situ (Morin et al. 2021)
# ---------------------------------------------------------------------------
def fit_asp(v: np.ndarray, a: np.ndarray, bin_w: float = 0.2, n_keep: int = 2, v_min: float = 3.0,
            sd_out: float = 2.0, max_iter: int = 10) -> dict:
    """Profil accélération-vitesse : a_max(v) = a0·(1 − v/v0).

    1. tranches de vitesse de `bin_w` m/s à partir de `v_min`, on garde les `n_keep` accélérations max ;
    2. régression linéaire a = a0 − s·v ;
    3. retrait itératif des points à plus de `sd_out` écarts-types du résidu, puis re-fit.
    """
    v = np.asarray(v, float)
    a = np.asarray(a, float)
    ok = (a > 0) & (v >= v_min) & np.isfinite(v) & np.isfinite(a)
    v, a = v[ok], a[ok]
    if len(v) < 10:
        return dict(a0=np.nan, v0=np.nan, points=pd.DataFrame(columns=["v", "a", "kept"]), r2=np.nan)
    bins = np.floor((v - v_min) / bin_w).astype(int)
    pts = pd.DataFrame({"v": v, "a": a, "bin": bins})
    pts = pts.sort_values("a", ascending=False).groupby("bin").head(n_keep).reset_index(drop=True)
    pts["kept"] = True
    for _ in range(max_iter):
        sel = pts["kept"].to_numpy()
        if sel.sum() < 3:
            break
        slope, intercept = np.polyfit(pts.loc[sel, "v"], pts.loc[sel, "a"], 1)
        resid = pts["a"] - (intercept + slope * pts["v"])
        sd = resid[sel].std()
        new_sel = sel & (np.abs(resid) <= sd_out * sd).to_numpy()
        if new_sel.sum() == sel.sum():
            break
        pts["kept"] = new_sel
    sel = pts["kept"].to_numpy()
    slope, intercept = np.polyfit(pts.loc[sel, "v"], pts.loc[sel, "a"], 1)
    pred = intercept + slope * pts.loc[sel, "v"]
    ss_res = ((pts.loc[sel, "a"] - pred) ** 2).sum()
    ss_tot = ((pts.loc[sel, "a"] - pts.loc[sel, "a"].mean()) ** 2).sum()
    a0 = float(intercept)
    v0 = float(-intercept / slope) if slope < 0 else np.nan
    return dict(a0=a0, v0=v0, points=pts, r2=float(1 - ss_res / ss_tot) if ss_tot > 0 else np.nan)


def a_asp(v: np.ndarray, a0: float, v0: float) -> np.ndarray:
    return np.clip(a0 * (1 - np.asarray(v, float) / v0), 0, None)


# ---------------------------------------------------------------------------
# Puissance mécanique externe (Part I, Eq. 1–2)
# ---------------------------------------------------------------------------
def w_ext_const(v: np.ndarray) -> np.ndarray:
    """Travail externe par unité de distance à vitesse constante (J/kg/m), Pavei 2019."""
    v = np.asarray(v, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        w = 1.3 - 0.4 / v
    return np.where(v > 0, np.clip(w, 0, None), 0.0)


def external_power(v: np.ndarray, a: np.ndarray) -> np.ndarray:
    """EP (W/kg) = Wext_const·v + a·v  (puissance positive ; les décélérations ne comptent pas)."""
    v = np.asarray(v, float)
    a = np.asarray(a, float)
    return np.clip(w_ext_const(v) * v + a * v, 0, None)


def ep_asp(v: np.ndarray, a0: float, v0: float) -> np.ndarray:
    """Puissance externe maximale atteignable à la vitesse v d'après l'ASP."""
    return external_power(v, a_asp(v, a0, v0))


# ---------------------------------------------------------------------------
# Puissance métabolique (di Prampero & Osgnach 2018 ; Minetti 2002)
# ---------------------------------------------------------------------------
_MINETTI = np.array([155.4, -30.4, -43.3, 46.3, 19.5])  # coefficients i^5 … i^1 (sans le terme constant)


def _minetti_poly(i: np.ndarray) -> np.ndarray:
    return np.polyval(np.append(_MINETTI, 0.0), i)


def _minetti_deriv(i: float) -> float:
    return float(np.polyval(np.polyder(np.append(_MINETTI, 0.0)), i))


def energy_cost(es: np.ndarray, em: np.ndarray, ec0: float = 3.8) -> np.ndarray:
    """ECr (J/kg/m) = (Minetti(ES) + EC0)·EM, extrapolation linéaire (tangente) au-delà de |ES| = 0.45."""
    es = np.asarray(es, float)
    inside = _minetti_poly(np.clip(es, -ES_LIMIT, ES_LIMIT))
    over = np.where(es > ES_LIMIT, (es - ES_LIMIT) * _minetti_deriv(ES_LIMIT), 0.0)
    under = np.where(es < -ES_LIMIT, (es + ES_LIMIT) * _minetti_deriv(-ES_LIMIT), 0.0)
    return (inside + over + under + ec0) * em


def metabolic_power(v: np.ndarray, a: np.ndarray, ec0: float = 3.8, k_air: float = K_AIR) -> np.ndarray:
    """MP (W/kg) = ECr·v avec ES = (a + k·v²)/g et EM = sqrt(a²/g² + 1)."""
    v = np.asarray(v, float)
    a = np.asarray(a, float)
    es = (a + k_air * v ** 2) / G
    em = np.sqrt(a ** 2 / G ** 2 + 1)
    return energy_cost(es, em, ec0) * v


def vo2_kinetics(mp: np.ndarray, dt: np.ndarray, tau: float = 20.0, vo2max: float | None = 18.0,
                 vo2_0: float | None = None) -> np.ndarray:
    """VO2 estimé (W/kg) : réponse du 1er ordre à MP, dVO2/dt = (MP − VO2)/tau, bornée à VO2max."""
    mp = np.asarray(mp, float)
    dt = np.asarray(dt, float)
    vo2 = np.empty_like(mp)
    cur = float(mp[0]) if vo2_0 is None else vo2_0
    for i in range(len(mp)):
        cur += (mp[i] - cur) * (1 - np.exp(-dt[i] / tau))
        if vo2max is not None:
            cur = min(cur, vo2max)
        vo2[i] = cur
    return vo2
