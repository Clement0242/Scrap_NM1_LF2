"""Dashboard Streamlit – analyse locomotion / mécanique (#burst) / métabolique (#MPE) d'un match.

D'après Osgnach, di Prampero et al. (2023) « Mechanical and metabolic power in accelerated running –
Part II: team sports ». Lancer :  streamlit run app_burst.py
"""
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import gps_metrics as gm

st.set_page_config(page_title="Bursts & MPE – Clément", page_icon="⚡", layout="wide")

DATA_FILE = Path(__file__).with_name("Clement_data.xlsx")

COL = {
    "speed": "#2a78d6", "hsr": "#eb6834", "acc": "#1baf7a", "dec": "#4a3aa7",
    "ep": "#2a78d6", "burst": "#eb6834", "mp": "#e34948", "vo2": "#2a78d6", "mpe": "#eb6834",
    "muted": "#52514e", "grey": "#c3c2b7",
}
LAYOUT = dict(
    template="plotly_white", margin=dict(l=40, r=20, t=40, b=40), hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False, zeroline=False),
)


# ---------------------------------------------------------------------------
# Données
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Chargement des données…")
def load_data(source) -> pd.DataFrame:
    df = pd.read_excel(source)
    df.columns = ["t", "datetime", "dist", "acc", "speed", "lat", "lon"]
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["t_min"] = df["t"] / 60
    df["d_step"] = df["dist"].diff().fillna(0).clip(lower=0)
    df["dt"] = df["t"].diff().fillna(df["t"].diff().median())
    return df


def fmt_hm(ts: pd.Timestamp) -> str:
    return f"{ts:%H:%M}"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
sb = st.sidebar
sb.header("Données")
upload = sb.file_uploader("Autre fichier (.xlsx, mêmes colonnes)", type=["xlsx"])
df_full = load_data(upload if upload is not None else DATA_FILE)

sb.header("Fenêtre d'analyse")
full_session = sb.checkbox("Session complète", value=False)
c1, c2 = sb.columns(2)
t_start = c1.time_input("Début", value=time(10, 0), step=60)
t_end = c2.time_input("Fin", value=time(10, 43), step=60)
tod = df_full["datetime"].dt.time
if full_session:
    df = df_full.copy()
else:
    df = df_full[(tod >= t_start) & (tod < t_end)].reset_index(drop=True)
if df.empty:
    st.error("Aucun point dans la fenêtre choisie.")
    st.stop()

sb.header("Unités")
unit = sb.radio("Vitesse", ["km/h", "m/s"], horizontal=True)
K = 3.6 if unit == "km/h" else 1.0

sb.header("Locomotion")
hs1 = sb.number_input("Seuil vitesse 1 (m/s)", value=5.5, step=0.5, help="D_speed>5.5 dans l'article")
hs2 = sb.number_input("Seuil vitesse 2 (m/s)", value=7.0, step=0.5, help="D_speed>7.0 et #speed dans l'article")
acc_thr = sb.number_input("Seuil accélération (m/s²)", value=2.5, step=0.5, help="#acc et D_acc>2.5")
min_dur = sb.number_input("Durée mini d'un événement (s)", value=0.5, step=0.1, min_value=0.0)

sb.header("Mécanique (ASP / bursts)")
asp_source = sb.radio("ASP calculée sur", ["Session complète", "Fenêtre d'analyse"],
                      help="L'article recommande ≥ 45 min de données et vmax ≥ 80 % de v0.")
asp_vmin = sb.number_input("Vitesse mini pour l'ASP (m/s)", value=3.0, step=0.5, min_value=0.0)
ep_frac = sb.slider("Seuil EPthr (fraction de EP_ASP)", 0.5, 1.0, 0.8, 0.05,
                    help="80 % dans l'article (Margaria 1971).")
burst_min_dur = sb.number_input("Durée mini d'un burst (s)", value=0.3, step=0.1, min_value=0.0)

sb.header("Métabolique (MP / MPE)")
ec0 = sb.number_input("EC0 course à plat (J/kg/m)", value=3.8, step=0.1, help="3.8 (Part I 2023) ; 3.6 Minetti ; 4.0 di Prampero 2018")
k_air = sb.number_input("k résistance de l'air", value=0.010, step=0.001, format="%.3f")
vo2max = sb.number_input("VO2max net (W/kg)", value=18.0, step=1.0, help="18 W/kg ≈ 52 ml/kg/min au-dessus du repos")
tau = sb.number_input("τ cinétique VO2 (s)", value=20.0, step=5.0)
mp_thr = sb.number_input("Seuil D_MP>20 (W/kg)", value=20.0, step=1.0)
mpe_min_dur = sb.number_input("Durée mini d'un MPE (s)", value=1.0, step=0.5, min_value=0.0)
mpe_gap = sb.number_input("Fusion des MPE séparés de moins de (s)", value=2.0, step=0.5, min_value=0.0)

# ---------------------------------------------------------------------------
# Calculs
# ---------------------------------------------------------------------------
v = df["speed"].to_numpy()
a = df["acc"].to_numpy()
dt = df["dt"].to_numpy()
d_step = df["d_step"].to_numpy()
duration_s = float(dt.sum())
TD = float(d_step.sum())

# --- locomotion
D_hs1 = d_step[v > hs1].sum()
D_hs2 = d_step[v > hs2].sum()
n_speed = len(gm.events_table(v > hs2, df, min_dur))
D_acc = d_step[a > acc_thr].sum()
acc_ev = gm.events_table(a > acc_thr, df, min_dur, extra={"a": a})
dec_ev = gm.events_table(a < -acc_thr, df, min_dur, extra={"a": a})

# --- ASP & mécanique
src = df_full if asp_source == "Session complète" else df
asp = gm.fit_asp(src["speed"].to_numpy(), src["acc"].to_numpy(), v_min=asp_vmin)
a0, v0 = asp["a0"], asp["v0"]
asp_ok = np.isfinite(a0) and np.isfinite(v0)
ep = gm.external_power(v, a)
EW = float(ep @ dt)
EP_mean = EW / duration_s
if asp_ok:
    ep_thr = ep_frac * gm.ep_asp(v, a0, v0)
    burst_mask = ep > ep_thr
    bursts = gm.events_table(burst_mask, df, burst_min_dur, extra={"ep": ep})
    high_mask = burst_mask
    zones = np.digitize(v, [v0 / 3, 2 * v0 / 3])  # 0 force, 1 power, 2 speed
    highEW = np.array([(ep[high_mask & (zones == z)] @ dt[high_mask & (zones == z)]) for z in range(3)])
else:
    ep_thr = np.full_like(ep, np.nan)
    bursts = gm.events_table(np.zeros(len(df), bool), df, 0)
    highEW = np.zeros(3)

# --- métabolique
mp = gm.metabolic_power(v, a, ec0=ec0, k_air=k_air)
vo2 = gm.vo2_kinetics(mp, dt, tau=tau, vo2max=vo2max)
EE = float(mp @ dt)
MP_mean = EE / duration_s
AnE = float(np.clip(mp - vo2, 0, None) @ dt)
D_mp = d_step[mp > mp_thr].sum()
mpe = gm.events_table(mp > vo2max, df, mpe_min_dur, gap_s=mpe_gap, extra={"mp": mp})
if len(mpe) > 1:
    rec_dur = (mpe["debut_s"].to_numpy()[1:] - mpe["fin_s"].to_numpy()[:-1])
    t_arr = df["t"].to_numpy()
    rec_mp = []
    for s_prev, s_next in zip(mpe["fin_s"].to_numpy()[:-1], mpe["debut_s"].to_numpy()[1:]):
        seg = (t_arr > s_prev) & (t_arr < s_next)
        rec_mp.append(float(mp[seg].mean()) if seg.any() else np.nan)
    rec_dur_mean, rec_mp_mean = float(np.mean(rec_dur)), float(np.nanmean(rec_mp))
else:
    rec_dur_mean = rec_mp_mean = np.nan

# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------
st.title("⚡ Bursts & Metabolic Power Events")
st.caption(
    f"Fenêtre : {fmt_hm(df['datetime'].iloc[0])} → {fmt_hm(df['datetime'].iloc[-1])} "
    f"({duration_s/60:.1f} min, {len(df):,} points) · "
    f"ASP sur {asp_source.lower()} : a0 = {a0:.2f} m/s², v0 = {v0:.2f} m/s ({v0*3.6:.1f} km/h), R² = {asp['r2']:.3f}"
    .replace(",", " ")
)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Distance totale", f"{TD/1000:.2f} km")
k2.metric(f"Distance > {hs1:g} m/s", f"{D_hs1:.0f} m", f"{100*D_hs1/TD:.1f} %", delta_color="off")
k3.metric(f"#acc > {acc_thr:g} m/s²", f"{len(acc_ev)}", f"{len(dec_ev)} décél.", delta_color="off")
k4.metric("#burst", f"{len(bursts)}", f"EP > {ep_frac:.0%} EP_ASP", delta_color="off")
k5.metric("#MPE", f"{len(mpe)}", f"MP > {vo2max:g} W/kg", delta_color="off")
k6.metric("AnE / EE", f"{100*AnE/EE:.1f} %", f"{AnE/1000:.1f} kJ/kg", delta_color="off")

tab_loc, tab_mec, tab_met, tab_cmp = st.tabs(["Locomotion", "Mécanique · bursts", "Métabolique · MPE", "Comparaison"])

# ---------------------------------------------------------------------------
# Locomotion
# ---------------------------------------------------------------------------
with tab_loc:
    c = st.columns(4)
    c[0].metric("TD", f"{TD:.0f} m")
    c[1].metric("Vitesse moyenne", f"{TD/duration_s*K:.2f} {unit}", f"{TD/duration_s*60:.0f} m/min", delta_color="off")
    c[2].metric(f"D_speed>{hs1:g}", f"{D_hs1:.0f} m")
    c[3].metric(f"D_speed>{hs2:g}", f"{D_hs2:.0f} m", f"#speed = {n_speed}", delta_color="off")
    c = st.columns(4)
    c[0].metric(f"D_acc>{acc_thr:g}", f"{D_acc:.0f} m")
    c[1].metric("#acc", f"{len(acc_ev)}")
    c[2].metric("#dec", f"{len(dec_ev)}")
    c[3].metric("Vitesse max", f"{v.max()*K:.1f} {unit}", f"{100*v.max()/v0:.0f} % de v0" if asp_ok else None, delta_color="off")

    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=df["t_min"], y=v * K, name="Vitesse", mode="lines",
                               line=dict(color=COL["speed"], width=1), hovertemplate="%{y:.1f} " + unit))
    fig.add_trace(go.Scattergl(x=df["t_min"], y=pd.Series(v * K).where(v > hs1), name=f"> {hs1:g} m/s", mode="lines",
                               line=dict(color=COL["hsr"], width=2), connectgaps=False, hovertemplate="%{y:.1f} " + unit))
    if len(acc_ev):
        fig.add_trace(go.Scattergl(x=acc_ev["debut_s"] / 60, y=acc_ev["v_debut"] * K, name=f"#acc ({len(acc_ev)})",
                                   mode="markers", marker=dict(color=COL["acc"], size=8, symbol="triangle-up",
                                                               line=dict(color="white", width=1)),
                                   hovertemplate="départ %{y:.1f} " + unit))
    fig.update_layout(**LAYOUT, height=320, xaxis_title="Temps session (min)", yaxis_title=f"Vitesse ({unit})")
    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# Mécanique
# ---------------------------------------------------------------------------
with tab_mec:
    if not asp_ok:
        st.warning("ASP non ajustable (pas assez de points au-dessus de la vitesse mini).")
    c = st.columns(5)
    c[0].metric("EW", f"{EW/1000:.1f} kJ/kg")
    c[1].metric("EP moyenne", f"{EP_mean:.2f} W/kg")
    c[2].metric("highEW", f"{highEW.sum():.0f} J/kg", f"{100*highEW.sum()/EW:.1f} % de EW" if EW else None, delta_color="off")
    c[3].metric("#burst", f"{len(bursts)}")
    c[4].metric("Burst moyen", f"{bursts['duree_s'].mean():.2f} s" if len(bursts) else "–",
                f"EP pic {bursts['ep_pic'].mean():.1f} W/kg · départ {bursts['v_debut'].mean()*K:.1f} {unit}" if len(bursts) else None,
                delta_color="off")

    left, right = st.columns([2, 3])
    with left:
        st.subheader("Profil accélération-vitesse (ASP)")
        pts = asp["points"]
        src_v = src["speed"].to_numpy()
        src_a = src["acc"].to_numpy()
        step = max(1, len(src_v) // 8000)
        fig = go.Figure()
        fig.add_trace(go.Scattergl(x=src_v[::step] * K, y=src_a[::step], mode="markers", name="Tous les points",
                                   marker=dict(color=COL["grey"], size=3), hoverinfo="skip"))
        if len(pts):
            kept = pts[pts["kept"]]
            drop = pts[~pts["kept"]]
            fig.add_trace(go.Scattergl(x=drop["v"] * K, y=drop["a"], mode="markers", name="Exclus (> 2 SD)",
                                       marker=dict(color=COL["muted"], size=7, symbol="x")))
            fig.add_trace(go.Scattergl(x=kept["v"] * K, y=kept["a"], mode="markers", name="2 max / 0,2 m/s",
                                       marker=dict(color=COL["burst"], size=8, line=dict(color="white", width=1))))
        if asp_ok:
            vv = np.linspace(0, v0, 50)
            fig.add_trace(go.Scatter(x=vv * K, y=gm.a_asp(vv, a0, v0), mode="lines", name=f"ASP : a0 {a0:.2f}, v0 {v0*K:.1f}",
                                     line=dict(color=COL["burst"], width=2, dash="dash")))
            for f in (1 / 3, 2 / 3):
                fig.add_vline(x=v0 * f * K, line=dict(color=COL["grey"], dash="dot", width=1))
        fig.update_layout(**{**LAYOUT, "hovermode": "closest"}, height=380,
                          xaxis_title=f"Vitesse ({unit})", yaxis_title="Accélération (m/s²)")
        st.plotly_chart(fig, width="stretch")

    with right:
        st.subheader("highEW par zone de vitesse")
        labels = [f"Force (0–⅓ v0)", f"Power (⅓–⅔ v0)", f"Speed (⅔–v0)"]
        fig = go.Figure(go.Bar(x=labels, y=highEW, marker_color=[COL["acc"], COL["burst"], COL["speed"]],
                               text=[f"{x:.0f} J/kg" for x in highEW], textposition="outside",
                               hovertemplate="%{x} : %{y:.0f} J/kg<extra></extra>"))
        fig.update_layout(**{**LAYOUT, "hovermode": "closest"}, height=380, showlegend=False, yaxis_title="J/kg")
        st.plotly_chart(fig, width="stretch")

    st.subheader("Puissance externe (EP) et seuil individuel EPthr")
    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=df["t_min"], y=ep, name="EP", mode="lines", line=dict(color=COL["ep"], width=1),
                               hovertemplate="%{y:.1f} W/kg"))
    fig.add_trace(go.Scattergl(x=df["t_min"], y=ep_thr, name=f"EPthr ({ep_frac:.0%} EP_ASP)", mode="lines",
                               line=dict(color=COL["muted"], width=1, dash="dot"), hovertemplate="%{y:.1f} W/kg"))
    if len(bursts):
        fig.add_trace(go.Scattergl(x=(bursts["debut_s"] + bursts["duree_s"] / 2) / 60, y=bursts["ep_pic"],
                                   name=f"#burst ({len(bursts)})", mode="markers",
                                   marker=dict(color=COL["burst"], size=9, line=dict(color="white", width=1)),
                                   hovertemplate="pic %{y:.1f} W/kg"))
    fig.update_layout(**LAYOUT, height=320, xaxis_title="Temps session (min)", yaxis_title="W/kg")
    st.plotly_chart(fig, width="stretch")

    with st.expander(f"Liste des bursts ({len(bursts)})"):
        if len(bursts):
            out = bursts.copy()
            for cc in ("v_debut", "v_fin", "v_max"):
                out[cc] *= K
            out = out.rename(columns={
                "debut_s": "Début (s)", "fin_s": "Fin (s)", "duree_s": "Durée (s)", "v_debut": f"V départ ({unit})",
                "v_fin": f"V fin ({unit})", "v_max": f"V max ({unit})", "distance_m": "Distance (m)",
                "ep_moy": "EP moy (W/kg)", "ep_pic": "EP pic (W/kg)", "ep_int": "EW (J/kg)",
            })
            st.dataframe(out.round(2), width="stretch", hide_index=True)
        else:
            st.info("Aucun burst avec ces réglages.")

# ---------------------------------------------------------------------------
# Métabolique
# ---------------------------------------------------------------------------
with tab_met:
    c = st.columns(6)
    c[0].metric("EE", f"{EE/1000:.1f} kJ/kg", f"{EE/4184:.2f} kcal/kg", delta_color="off")
    c[1].metric("MP moyenne", f"{MP_mean:.2f} W/kg", f"{MP_mean/20.9*60:.1f} ml O₂/kg/min", delta_color="off")
    c[2].metric("AnE", f"{AnE/1000:.2f} kJ/kg", f"AnE/EE = {100*AnE/EE:.1f} %", delta_color="off")
    c[3].metric(f"D_MP>{mp_thr:g}", f"{D_mp:.0f} m", f"{100*D_mp/TD:.1f} % de TD", delta_color="off")
    c[4].metric("#MPE", f"{len(mpe)}", f"{len(mpe)/(duration_s/60):.2f} / min", delta_color="off")
    c[5].metric("MPE moyen", f"{mpe['duree_s'].mean():.1f} s" if len(mpe) else "–",
                f"{mpe['mp_moy'].mean():.1f} W/kg" if len(mpe) else None, delta_color="off")
    c = st.columns(6)
    c[0].metric("Récup. moyenne", f"{rec_dur_mean:.1f} s" if np.isfinite(rec_dur_mean) else "–",
                f"{rec_mp_mean:.1f} W/kg" if np.isfinite(rec_mp_mean) else None, delta_color="off")
    c[1].metric("Cycle travail + récup.", f"{mpe['duree_s'].mean()+rec_dur_mean:.0f} s" if np.isfinite(rec_dur_mean) else "–")
    c[2].metric("MP max", f"{mp.max():.0f} W/kg")

    st.subheader("Puissance métabolique et VO₂ estimé")
    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=df["t_min"], y=mp, name="MP", mode="lines", line=dict(color=COL["mp"], width=1),
                               hovertemplate="%{y:.1f} W/kg"))
    fig.add_trace(go.Scattergl(x=df["t_min"], y=vo2, name=f"VO₂ estimé (τ = {tau:g} s)", mode="lines",
                               line=dict(color=COL["vo2"], width=2), hovertemplate="%{y:.1f} W/kg"))
    fig.add_hline(y=vo2max, line=dict(color=COL["muted"], dash="dot", width=1), annotation_text="VO₂max",
                  annotation_position="top left")
    if len(mpe):
        fig.add_trace(go.Scattergl(x=(mpe["debut_s"] + mpe["duree_s"] / 2) / 60, y=mpe["mp_pic"],
                                   name=f"#MPE ({len(mpe)})", mode="markers",
                                   marker=dict(color=COL["mpe"], size=8, line=dict(color="white", width=1)),
                                   hovertemplate="pic %{y:.1f} W/kg"))
    fig.update_layout(**LAYOUT, height=340, xaxis_title="Temps session (min)", yaxis_title="W/kg")
    st.plotly_chart(fig, width="stretch")

    with st.expander(f"Liste des MPE ({len(mpe)})"):
        if len(mpe):
            out = mpe.copy()
            for cc in ("v_debut", "v_fin", "v_max"):
                out[cc] *= K
            out = out.rename(columns={
                "debut_s": "Début (s)", "fin_s": "Fin (s)", "duree_s": "Durée (s)", "v_debut": f"V départ ({unit})",
                "v_fin": f"V fin ({unit})", "v_max": f"V max ({unit})", "distance_m": "Distance (m)",
                "mp_moy": "MP moy (W/kg)", "mp_pic": "MP pic (W/kg)", "mp_int": "Énergie (J/kg)",
            })
            st.dataframe(out.round(2), width="stretch", hide_index=True)
        else:
            st.info("Aucun MPE avec ces réglages.")

# ---------------------------------------------------------------------------
# Comparaison
# ---------------------------------------------------------------------------
with tab_cmp:
    st.subheader("Trois façons de compter l'intensité")
    summary = pd.DataFrame({
        "Indicateur": [f"#acc > {acc_thr:g} m/s²", "#burst (EP > EPthr)", f"#MPE (MP > {vo2max:g} W/kg)"],
        "Nombre": [len(acc_ev), len(bursts), len(mpe)],
        "Par minute": [len(acc_ev) / (duration_s / 60), len(bursts) / (duration_s / 60), len(mpe) / (duration_s / 60)],
        "Durée moy (s)": [acc_ev["duree_s"].mean(), bursts["duree_s"].mean(), mpe["duree_s"].mean()],
        f"V départ moy ({unit})": [acc_ev["v_debut"].mean() * K, bursts["v_debut"].mean() * K, mpe["v_debut"].mean() * K],
        "Distance moy (m)": [acc_ev["distance_m"].mean(), bursts["distance_m"].mean(), mpe["distance_m"].mean()],
    })
    st.dataframe(summary.round(2), width="stretch", hide_index=True)
    if len(acc_ev):
        st.caption(f"Ratio #burst / #acc = {len(bursts)/len(acc_ev):.2f} (article : 1,61 en moyenne, 1,36 attaquants → 2,30 milieux).")

    bin_min = st.select_slider("Taille de tranche (min)", options=[1, 2, 5, 10, 15], value=5)
    t0, t1 = df["t_min"].iloc[0], df["t_min"].iloc[-1]
    bins = np.arange(np.floor(t0), np.ceil(t1) + bin_min, bin_min)
    centers = bins[:-1] + bin_min / 2
    fig = go.Figure()
    for name, ev, color, off in (("#acc", acc_ev, COL["acc"], -0.3), ("#burst", bursts, COL["burst"], 0.0),
                                 ("#MPE", mpe, COL["mp"], 0.3)):
        n = np.histogram(ev["debut_s"].to_numpy() / 60, bins=bins)[0]
        fig.add_trace(go.Bar(x=centers + off * bin_min * 0.8, y=n, name=name, marker_color=color,
                             width=bin_min * 0.25, hovertemplate="%{y}"))
    fig.update_layout(**{**LAYOUT, "hovermode": "closest"}, height=300, barmode="overlay",
                      xaxis_title="Temps session (min)", yaxis_title="Nombre")
    st.plotly_chart(fig, width="stretch")

    st.subheader("Où se situent les événements sur l'ASP ?")
    fig = go.Figure()
    if asp_ok:
        vv = np.linspace(0, v0, 50)
        fig.add_trace(go.Scatter(x=vv * K, y=gm.a_asp(vv, a0, v0), mode="lines", name="ASP",
                                 line=dict(color=COL["grey"], width=2, dash="dash")))
        fig.add_trace(go.Scatter(x=vv * K, y=gm.a_asp(vv, a0, v0) * ep_frac, mode="lines", name=f"{ep_frac:.0%} ASP",
                                 line=dict(color=COL["grey"], width=1, dash="dot")))
    fig.add_hline(y=acc_thr, line=dict(color=COL["acc"], dash="dot", width=1), annotation_text=f"a > {acc_thr:g}")
    for name, ev, color, key in (("#acc", acc_ev, COL["acc"], "a_pic"), ("#burst", bursts, COL["burst"], None)):
        if not len(ev):
            continue
        # pic d'accélération de chaque événement
        t_arr = df["t"].to_numpy()
        peaks_v, peaks_a = [], []
        for s_, e_ in zip(ev["debut_s"], ev["fin_s"]):
            seg = (t_arr >= s_) & (t_arr <= e_)
            i = np.argmax(np.where(seg, a, -np.inf))
            peaks_v.append(v[i] * K)
            peaks_a.append(a[i])
        fig.add_trace(go.Scatter(x=peaks_v, y=peaks_a, mode="markers", name=name,
                                 marker=dict(color=color, size=9, line=dict(color="white", width=1),
                                             symbol="triangle-up" if name == "#acc" else "circle"),
                                 hovertemplate="v %{x:.1f}, a %{y:.2f}"))
    fig.update_layout(**{**LAYOUT, "hovermode": "closest"}, height=380,
                      xaxis_title=f"Vitesse au pic ({unit})", yaxis_title="Accélération pic (m/s²)")
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Un #acc démarré à basse vitesse peut être loin des capacités maximales (sous la courbe 80 % ASP), "
        "alors qu'un burst démarré à haute vitesse peut être maximal sans jamais franchir 2,5 m/s² : "
        "c'est la limite du seuil fixe soulignée par l'article."
    )
