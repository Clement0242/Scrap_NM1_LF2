"""Dashboard Streamlit – analyse d'une trace GPS (distance, haute vitesse, accélérations, décélérations).

Lancer :  streamlit run app.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Config & palette
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Analyse GPS – Clément", page_icon="🏃", layout="wide")

DATA_FILE = Path(__file__).with_name("Clement_data.xlsx")

COL = {
    "speed": "#2a78d6",   # bleu
    "hsr": "#eb6834",     # orange
    "acc": "#1baf7a",     # aqua
    "dec": "#4a3aa7",     # violet
    "dist": "#2a78d6",
    "muted": "#52514e",
}

LAYOUT = dict(
    template="plotly_white",
    margin=dict(l=40, r=20, t=40, b=40),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    xaxis=dict(showgrid=False, zeroline=False),
    yaxis=dict(showgrid=False, zeroline=False),
)


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Chargement des données…")
def load_data(source) -> pd.DataFrame:
    df = pd.read_excel(source)
    df.columns = ["t", "datetime", "dist", "acc", "speed", "lat", "lon"]
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["t_min"] = df["t"] / 60
    df["d_step"] = df["dist"].diff().fillna(0).clip(lower=0)  # distance parcourue entre 2 points
    df["dt"] = df["t"].diff().fillna(df["t"].diff().median())
    return df


def find_events(mask: np.ndarray, df: pd.DataFrame, min_dur: float) -> pd.DataFrame:
    """Regroupe les points contigus où `mask` est vrai en événements ; garde ceux qui durent >= min_dur."""
    m = mask.astype(int)
    edges = np.diff(np.concatenate(([0], m, [0])))
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]  # exclusif
    rows = []
    t = df["t"].to_numpy()
    acc = df["acc"].to_numpy()
    spd = df["speed"].to_numpy()
    dist = df["dist"].to_numpy()
    dt = df["dt"].to_numpy()
    for s, e in zip(starts, ends):
        dur = t[e - 1] - t[s] + dt[s]
        if dur < min_dur:
            continue
        seg = acc[s:e]
        i_peak = s + int(np.argmax(np.abs(seg)))
        rows.append(
            dict(
                debut_s=t[s],
                fin_s=t[e - 1],
                duree_s=dur,
                acc_pic=acc[i_peak],
                t_pic=t[i_peak],
                v_debut=spd[s],
                v_fin=spd[e - 1],
                delta_v=spd[e - 1] - spd[s],
                distance_m=dist[e - 1] - dist[s],
            )
        )
    cols = ["debut_s", "fin_s", "duree_s", "acc_pic", "t_pic", "v_debut", "v_fin", "delta_v", "distance_m"]
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.header("Données")
upload = st.sidebar.file_uploader("Autre fichier (.xlsx, mêmes colonnes)", type=["xlsx"])
df_full = load_data(upload if upload is not None else DATA_FILE)

st.sidebar.header("Unités")
unit = st.sidebar.radio("Vitesse", ["km/h", "m/s"], horizontal=True)
K = 3.6 if unit == "km/h" else 1.0

st.sidebar.header("Seuils")
hs_default = 20.0 if unit == "km/h" else 5.5
hs_thr_disp = st.sidebar.number_input(
    f"Haute vitesse (> {unit})", min_value=0.0, value=hs_default, step=0.5,
    help="Distance parcourue avec une vitesse instantanée au-dessus de ce seuil.",
)
hs_thr = hs_thr_disp / K  # en m/s

acc_thr = st.sidebar.number_input("Accélération (> m/s²)", min_value=0.1, value=2.0, step=0.5)
dec_thr = st.sidebar.number_input("Décélération (< −m/s²)", min_value=0.1, value=2.0, step=0.5)
min_dur = st.sidebar.number_input(
    "Durée mini d'un événement (s)", min_value=0.0, value=0.5, step=0.1,
    help="Une accélération = une suite de points contigus au-dessus du seuil pendant au moins cette durée.",
)

st.sidebar.header("Fenêtre temporelle")
t_max = float(df_full["t_min"].iloc[-1])
t_lo, t_hi = st.sidebar.slider("Minutes", 0.0, round(t_max, 1), (0.0, round(t_max, 1)), step=0.5)
df = df_full[(df_full["t_min"] >= t_lo) & (df_full["t_min"] <= t_hi)].reset_index(drop=True)

# ---------------------------------------------------------------------------
# Calculs
# ---------------------------------------------------------------------------
total_dist = df["d_step"].sum()
hs_mask = df["speed"] > hs_thr
hs_dist = df.loc[hs_mask, "d_step"].sum()
hs_time = df.loc[hs_mask, "dt"].sum()

acc_events = find_events((df["acc"] > acc_thr).to_numpy(), df, min_dur)
dec_events = find_events((df["acc"] < -dec_thr).to_numpy(), df, min_dur)

duration_s = df["t"].iloc[-1] - df["t"].iloc[0]
v_max = df["speed"].max()
v_mean = total_dist / duration_s if duration_s > 0 else 0

# ---------------------------------------------------------------------------
# En-tête + KPIs
# ---------------------------------------------------------------------------
st.title("🏃 Analyse GPS")
st.caption(
    f"Session du {df_full['datetime'].iloc[0]:%d/%m/%Y %H:%M} · "
    f"{len(df_full):,} points à {1/df_full['dt'].median():.0f} Hz · "
    f"fenêtre affichée : {t_lo:.1f} → {t_hi:.1f} min".replace(",", " ")
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Distance totale", f"{total_dist/1000:.2f} km", f"{total_dist:.0f} m", delta_color="off")
c2.metric(
    "Distance haute vitesse",
    f"{hs_dist:.0f} m",
    f"{100*hs_dist/total_dist if total_dist else 0:.1f} % du total · {hs_time:.0f} s",
    delta_color="off",
)
c3.metric("Accélérations", f"{len(acc_events)}", f"> {acc_thr:g} m/s²", delta_color="off")
c4.metric("Décélérations", f"{len(dec_events)}", f"< −{dec_thr:g} m/s²", delta_color="off")

c5, c6, c7, c8 = st.columns(4)
c5.metric("Durée", f"{duration_s/60:.1f} min")
c6.metric("Vitesse max", f"{v_max*K:.1f} {unit}")
c7.metric("Vitesse moyenne", f"{v_mean*K:.1f} {unit}")
c8.metric(
    "Acc. / Déc. par minute",
    f"{len(acc_events)/(duration_s/60):.2f} / {len(dec_events)/(duration_s/60):.2f}"
    if duration_s else "–",
)

st.divider()

# ---------------------------------------------------------------------------
# Vitesse
# ---------------------------------------------------------------------------
st.subheader("Vitesse")
fig = go.Figure()
fig.add_trace(go.Scattergl(
    x=df["t_min"], y=df["speed"] * K, name="Vitesse", mode="lines",
    line=dict(color=COL["speed"], width=1), hovertemplate="%{y:.1f} " + unit,
))
hs_speed = (df["speed"] * K).where(hs_mask)
fig.add_trace(go.Scattergl(
    x=df["t_min"], y=hs_speed, name=f"> {hs_thr_disp:g} {unit}", mode="lines",
    line=dict(color=COL["hsr"], width=2), connectgaps=False, hovertemplate="%{y:.1f} " + unit,
))
fig.add_hline(y=hs_thr_disp, line=dict(color=COL["hsr"], dash="dot", width=1),
              annotation_text="seuil HV", annotation_position="top left")
fig.update_layout(**LAYOUT, height=320, xaxis_title="Temps (min)", yaxis_title=f"Vitesse ({unit})")
st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# Accélération
# ---------------------------------------------------------------------------
st.subheader("Accélération")
fig = go.Figure()
fig.add_trace(go.Scattergl(
    x=df["t_min"], y=df["acc"], name="Accélération", mode="lines",
    line=dict(color=COL["muted"], width=0.8), opacity=0.6, hovertemplate="%{y:.2f} m/s²",
))
if len(acc_events):
    fig.add_trace(go.Scattergl(
        x=acc_events["t_pic"] / 60, y=acc_events["acc_pic"], name=f"Accél. ({len(acc_events)})",
        mode="markers", marker=dict(color=COL["acc"], size=8, line=dict(color="white", width=1)),
        hovertemplate="pic %{y:.2f} m/s²",
    ))
if len(dec_events):
    fig.add_trace(go.Scattergl(
        x=dec_events["t_pic"] / 60, y=dec_events["acc_pic"], name=f"Décél. ({len(dec_events)})",
        mode="markers", marker=dict(color=COL["dec"], size=8, line=dict(color="white", width=1)),
        hovertemplate="pic %{y:.2f} m/s²",
    ))
fig.add_hline(y=acc_thr, line=dict(color=COL["acc"], dash="dot", width=1))
fig.add_hline(y=-dec_thr, line=dict(color=COL["dec"], dash="dot", width=1))
fig.update_layout(**LAYOUT, height=320, xaxis_title="Temps (min)", yaxis_title="Accélération (m/s²)")
st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# Distance cumulée + zones de vitesse
# ---------------------------------------------------------------------------
left, right = st.columns([3, 2])

with left:
    st.subheader("Distance cumulée")
    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        x=df["t_min"], y=df["d_step"].cumsum(), name="Totale", mode="lines",
        line=dict(color=COL["dist"], width=2), hovertemplate="%{y:.0f} m",
    ))
    fig.add_trace(go.Scattergl(
        x=df["t_min"], y=df["d_step"].where(hs_mask, 0).cumsum(), name="Haute vitesse", mode="lines",
        line=dict(color=COL["hsr"], width=2), hovertemplate="%{y:.0f} m",
    ))
    fig.update_layout(**LAYOUT, height=300, xaxis_title="Temps (min)", yaxis_title="Distance (m)")
    st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("Distance par zone de vitesse")
    if unit == "km/h":
        edges = [0, 7, 14, 20, 25, np.inf]
    else:
        edges = [0, 2, 4, 5.5, 7, np.inf]
    labels = [
        f"{edges[i]:g}–{edges[i+1]:g}" if np.isfinite(edges[i + 1]) else f"> {edges[i]:g}"
        for i in range(len(edges) - 1)
    ]
    zone = pd.cut(df["speed"] * K, bins=edges, labels=labels, right=False, include_lowest=True)
    dist_zone = df.groupby(zone, observed=False)["d_step"].sum()
    colors = [COL["hsr"] if edges[i] >= hs_thr_disp else COL["speed"] for i in range(len(labels))]
    fig = go.Figure(go.Bar(
        x=labels, y=dist_zone.values, marker_color=colors,
        text=[f"{v:.0f} m" for v in dist_zone.values], textposition="outside",
        hovertemplate="%{x} " + unit + " : %{y:.0f} m<extra></extra>",
    ))
    fig.update_layout(**{**LAYOUT, "hovermode": "closest"}, height=300, showlegend=False,
                      xaxis_title=f"Zone ({unit})", yaxis_title="Distance (m)")
    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# Événements par tranche
# ---------------------------------------------------------------------------
st.subheader("Événements par tranche de temps")
bin_min = st.select_slider("Taille de tranche (min)", options=[1, 2, 5, 10, 15], value=5)
bins = np.arange(np.floor(t_lo), np.ceil(t_hi) + bin_min, bin_min)
centers = bins[:-1] + bin_min / 2
n_acc = np.histogram(acc_events["t_pic"].to_numpy() / 60, bins=bins)[0]
n_dec = np.histogram(dec_events["t_pic"].to_numpy() / 60, bins=bins)[0]
hs_bin = (
    df["d_step"].where(hs_mask, 0)
    .groupby(pd.cut(df["t_min"], bins=bins), observed=False)
    .sum()
)

fig = go.Figure()
fig.add_trace(go.Bar(x=centers, y=n_acc, name="Accélérations", marker_color=COL["acc"], width=bin_min * 0.4,
                     offset=-bin_min * 0.42, hovertemplate="%{y}"))
fig.add_trace(go.Bar(x=centers, y=n_dec, name="Décélérations", marker_color=COL["dec"], width=bin_min * 0.4,
                     offset=bin_min * 0.02, hovertemplate="%{y}"))
fig.update_layout(**LAYOUT, height=280, barmode="overlay",
                  xaxis_title="Temps (min)", yaxis_title="Nombre")
st.plotly_chart(fig, width="stretch")

fig = go.Figure(go.Bar(x=centers, y=hs_bin.values, name="Distance HV", marker_color=COL["hsr"],
                       width=bin_min * 0.8, hovertemplate="%{y:.0f} m"))
fig.update_layout(**LAYOUT, height=240, showlegend=False,
                  xaxis_title="Temps (min)", yaxis_title="Distance HV (m)")
st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# Carte
# ---------------------------------------------------------------------------
with st.expander("Carte de la trace", expanded=False):
    step = max(1, len(df) // 5000)
    sub = df.iloc[::step]
    fig = go.Figure(go.Scattermap(
        lat=sub["lat"], lon=sub["lon"], mode="markers",
        marker=dict(size=5, color=sub["speed"] * K, colorscale="Blues", showscale=True,
                    colorbar=dict(title=unit)),
        hovertemplate="%{marker.color:.1f} " + unit + "<extra></extra>",
    ))
    fig.update_layout(
        map=dict(style="open-street-map", center=dict(lat=sub["lat"].mean(), lon=sub["lon"].mean()), zoom=17),
        margin=dict(l=0, r=0, t=0, b=0), height=450,
    )
    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# Tableaux
# ---------------------------------------------------------------------------
with st.expander("Liste des accélérations / décélérations"):
    tab1, tab2 = st.tabs([f"Accélérations ({len(acc_events)})", f"Décélérations ({len(dec_events)})"])

    def show_events(ev: pd.DataFrame):
        if ev.empty:
            st.info("Aucun événement avec ces seuils.")
            return
        out = ev.copy()
        out["v_debut"] *= K
        out["v_fin"] *= K
        out["delta_v"] *= K
        out = out.rename(columns={
            "debut_s": "Début (s)", "fin_s": "Fin (s)", "duree_s": "Durée (s)", "acc_pic": "Pic (m/s²)",
            "t_pic": "t pic (s)", "v_debut": f"V début ({unit})", "v_fin": f"V fin ({unit})",
            "delta_v": f"ΔV ({unit})", "distance_m": "Distance (m)",
        })
        st.dataframe(out.round(2), width="stretch", hide_index=True)
        st.caption(
            f"Durée moyenne {ev['duree_s'].mean():.2f} s · pic moyen {ev['acc_pic'].mean():.2f} m/s² · "
            f"pic max {ev['acc_pic'].abs().max():.2f} m/s²"
        )

    with tab1:
        show_events(acc_events)
    with tab2:
        show_events(dec_events)

with st.expander("Données brutes"):
    st.dataframe(df.head(2000), width="stretch")
    st.download_button(
        "Télécharger la fenêtre en CSV", df.to_csv(index=False).encode(), "trace_gps.csv", "text/csv"
    )
