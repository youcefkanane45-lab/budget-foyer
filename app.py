import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Budget Foyer Kanane", page_icon="💰", layout="wide")

# ============================================================
# AUTHENTIFICATION
# ============================================================
PASSWORD = st.secrets["PASSWORD"]
SHEET_ID = st.secrets["SHEET_ID"]

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("💰 Budget Foyer Kanane")
    pwd = st.text_input("🔒 Mot de passe", type="password")
    if pwd == PASSWORD:
        st.session_state.auth = True
        st.rerun()
    elif pwd:
        st.error("Mot de passe incorrect")
    st.stop()

# ============================================================
# CHARGEMENT
# ============================================================
def parse_number(val):
    if pd.isna(val): return 0.0
    s = str(val).replace(" ", "").replace("€", "").replace(",", ".").replace("\xa0", "").replace("\u202f", "").strip()
    try: return float(s)
    except: return 0.0

@st.cache_data(ttl=300)
def load_parametres():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Parametres"
    raw = pd.read_csv(url, header=None)
    data = {}
    for _, row in raw.iterrows():
        label = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        val = parse_number(row.iloc[2]) if len(row) > 2 else 0
        note = str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else ""
        if label and label not in ["", "nan"]:
            data[label] = {"valeur": val, "note": note}
    return data

@st.cache_data(ttl=300)
def load_saisie():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Saisie"
    df = pd.read_csv(url, skiprows=3)
    df.columns = ["Date", "Libelle", "Montant", "Categorie", "Type", "Mois", "Note"]
    df["Montant"] = df["Montant"].apply(parse_number)
    df = df.dropna(subset=["Date"])
    df = df[df["Date"].astype(str).str.strip() != ""]
    return df

try:
    params = load_parametres()
    df = load_saisie()
    mois_dispo = sorted(df["Mois"].dropna().unique(), reverse=True)
except Exception as e:
    st.error(f"Erreur : {e}")
    st.stop()

def g(label, default=0):
    if label in params: return params[label]["valeur"]
    for k, v in params.items():
        if label.lower() in k.lower(): return v["valeur"]
    return default

def g_note(label):
    if label in params: return params[label]["note"]
    for k, v in params.items():
        if label.lower() in k.lower(): return v["note"]
    return ""

# --- Valeurs du Sheet ---
total_revenus = g("Total revenus foyer")
total_charges = g("Total charges fixes")
reste_dispatcher = g("Reste à dispatcher")
total_enveloppes = g("Total enveloppes")
budget_vie = g("Vie du foyer")

ENVELOPPES_KEYS = [
    "Reconstitution matelas", "Sur-remboursement crédit conso",
    "Investissement long terme", "Lancement freelance", "Vacances",
    "Réserve achats / imprévus",
]
enveloppes = {}
for k in ENVELOPPES_KEYS:
    val = g(k, None)
    if val is not None and val > 0:
        enveloppes[k] = {"mensuel": val, "destination": g_note(k)}

patrimoine_raw = {
    "Livret A": {"objectif": 10000, "icone": "🛡️"},
    "PEA titres (Ondaine Pilat)": {"objectif": 48000, "icone": "📈"},
    "Livret Vacances": {"objectif": 2400, "icone": "✈️"},
    "Livret Business": {"objectif": 5000, "icone": "🚀"},
    "Livret Imprévus": {"objectif": 3000, "icone": "🔧"},
    "Épargne compagne": {"objectif": 5000, "icone": "👩"},
}
patrimoine = {}
for label, config in patrimoine_raw.items():
    solde = g(label, -1)
    if solde >= 0:
        if label == "PEA titres (Ondaine Pilat)":
            pea_num = g("Numéraire PEA CE", 0)
            patrimoine["PEA (total)"] = {"solde": solde + pea_num, "objectif": 48000, "icone": "📈"}
        else:
            patrimoine[label] = {"solde": solde, **config}

credit_solde = g("Crédit conso (mensualité 255,64", g("Crédit conso", 5900))
credit_mensualite = 255.64
credit_sur = g("Sur-remboursement crédit conso", 400)
versement_matelas = g("Reconstitution matelas", 500)

# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.title("⚙️ Paramètres")
mois = st.sidebar.selectbox("Mois à analyser", mois_dispo)
st.sidebar.divider()
st.sidebar.metric("Revenus foyer", f"{total_revenus:,.0f} €".replace(",", " "))
st.sidebar.metric("Charges fixes", f"{total_charges:,.0f} €".replace(",", " "))
st.sidebar.metric("Reste à dispatcher", f"{reste_dispatcher:,.0f} €".replace(",", " "))
st.sidebar.metric("Enveloppes", f"{total_enveloppes:,.0f} €".replace(",", " "))
st.sidebar.metric("Vie du foyer", f"{budget_vie:,.0f} €".replace(",", " "))
st.sidebar.divider()
st.sidebar.caption("Données : Google Sheets (auto-sync 5 min)")

# ============================================================
# FILTRAGE
# ============================================================
dm = df[df["Mois"] == mois].copy()
depenses = dm[dm["Montant"] < 0].copy()
depenses["Montant_abs"] = depenses["Montant"].abs()
depenses_reelles = depenses[~depenses["Type"].isin(["Interne", "Recette", "Épargne"])]
depenses_variables = depenses_reelles[depenses_reelles["Type"] == "Variable"]
total_depense = depenses_reelles["Montant_abs"].sum()
total_variable = depenses_variables["Montant_abs"].sum()

# ============================================================
# HEADER
# ============================================================
st.title("💰 Budget Foyer Kanane")
st.caption(f"📅 Mois analysé : **{mois}**")

col1, col2, col3, col4 = st.columns(4)
reste = budget_vie - total_variable
col1.metric("Reste à dépenser", f"{reste:,.0f} €".replace(",", " "), "vie foyer")
col2.metric("Dépenses variables", f"{total_variable:,.0f} €".replace(",", " "))
col3.metric("Total dépensé", f"{total_depense:,.0f} €".replace(",", " "))
col4.metric("Transactions", f"{len(dm)}")

if reste < 0:
    st.error(f"🔴 DÉPASSÉ de {abs(reste):,.0f} € !".replace(",", " "))
elif reste < 100:
    st.warning(f"🟠 Attention, plus que {reste:,.0f} €".replace(",", " "))
else:
    st.success(f"🟢 OK — il reste {reste:,.0f} €".replace(",", " "))

st.divider()

# ============================================================
# CAMEMBERT + TABLEAU
# ============================================================
col_chart, col_table = st.columns([1, 1])

with col_chart:
    st.subheader("📊 Répartition des dépenses")
    by_cat = depenses_reelles.groupby("Categorie")["Montant_abs"].sum().reset_index()
    by_cat = by_cat.sort_values("Montant_abs", ascending=False)
    by_cat = by_cat[by_cat["Montant_abs"] > 0]
    if not by_cat.empty:
        fig = px.pie(by_cat, values="Montant_abs", names="Categorie", hole=0.4)
        fig.update_traces(textinfo="label+value", texttemplate="%{label}<br>%{value:.0f} €")
        fig.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20), height=400)
        st.plotly_chart(fig, use_container_width=True)

with col_table:
    st.subheader("📋 Détail par catégorie")
    seuils = {"Restauration": 300, "Courses": 350, "Loisirs cinéma": 50, "Achats": 100,
              "Essence": 120, "Péage autoroute": 60, "Transport": 40, "Vêtements": 60,
              "Santé": 50, "Retrait espèces": 80}
    rows = []
    for _, r in by_cat.iterrows():
        cat, dep = r["Categorie"], r["Montant_abs"]
        seuil = seuils.get(cat)
        statut = ""
        if seuil:
            statut = "🔴 Trop" if dep > seuil else ("🟠 Attention" if dep > seuil * 0.7 else "🟢 OK")
        rows.append({"Catégorie": cat, "Dépensé": f"{dep:,.0f} €".replace(",", " "), "Statut": statut})
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

st.divider()

# ============================================================
# ENVELOPPES
# ============================================================
st.subheader("💼 Enveloppes d'épargne mensuelles")
st.caption(f"Objectif total : {total_enveloppes:,.0f} €/mois".replace(",", " "))

if enveloppes:
    env_cols = st.columns(3)
    for i, (nom, info) in enumerate(enveloppes.items()):
        with env_cols[i % 3]:
            st.markdown(f"**{nom}**")
            st.caption(f"→ {info['destination']}")
            st.markdown(f"### {info['mensuel']:,.0f} €/mois".replace(",", " "))

st.divider()

# ============================================================
# JAUGES PATRIMOINE
# ============================================================
st.subheader("🎯 Objectifs patrimoine")

if patrimoine:
    jauge_cols = st.columns(min(len(patrimoine), 5))
    for i, (nom, info) in enumerate(patrimoine.items()):
        with jauge_cols[i % len(jauge_cols)]:
            pct = min(info["solde"] / info["objectif"] * 100, 100) if info["objectif"] > 0 else 0
            color = "green" if pct >= 80 else ("orange" if pct >= 40 else "red")
            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=info["solde"],
                number={"suffix": " €", "font": {"size": 20}},
                title={"text": f"{info['icone']} {nom}", "font": {"size": 12}},
                gauge={"axis": {"range": [0, info["objectif"]]}, "bar": {"color": color},
                       "steps": [
                           {"range": [0, info["objectif"] * 0.4], "color": "#ffebee"},
                           {"range": [info["objectif"] * 0.4, info["objectif"] * 0.8], "color": "#fff8e1"},
                           {"range": [info["objectif"] * 0.8, info["objectif"]], "color": "#e8f5e9"},
                       ]}))
            fig.update_layout(height=200, margin=dict(t=40, b=10, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"Objectif : {info['objectif']:,} €".replace(",", " "))

st.divider()

# ============================================================
# PROJECTION CRÉDIT
# ============================================================
st.subheader("📉 Projection extinction du crédit conso")

mois_proj = []
solde = credit_solde
for m in range(1, 13):
    mens = min(credit_mensualite, solde) if solde > 0 else 0
    sur = min(credit_sur, max(0, solde - mens)) if solde > mens else 0
    solde_fin = max(0, solde - mens - sur)
    mois_proj.append({"Mois": f"M+{m}", "Solde début": solde, "Mensualité": mens,
                       "Sur-remboursement": sur, "Solde fin": solde_fin})
    solde = solde_fin

df_proj = pd.DataFrame(mois_proj)
col_c1, col_c2 = st.columns([1, 1])

with col_c1:
    fig_credit = px.bar(df_proj, x="Mois", y="Solde fin", text_auto=".0f",
                         color_discrete_sequence=["#e74c3c"])
    fig_credit.update_layout(yaxis_title="Solde (€)", height=300, margin=dict(t=20, b=20))
    st.plotly_chart(fig_credit, use_container_width=True)
    mois_zero = next((r["Mois"] for _, r in df_proj.iterrows() if r["Solde fin"] == 0), "M+12+")
    st.success(f"🎯 Crédit soldé à **{mois_zero}** ({credit_mensualite:.0f} + {credit_sur:.0f} €/mois)")

with col_c2:
    dp = df_proj.copy()
    for c in ["Solde début", "Mensualité", "Sur-remboursement", "Solde fin"]:
        dp[c] = dp[c].apply(lambda x: f"{x:,.0f} €".replace(",", " "))
    st.dataframe(dp, hide_index=True, use_container_width=True, height=300)

st.divider()

# ============================================================
# PROJECTION LIVRET A
# ============================================================
st.subheader("🛡️ Projection matelas Livret A")

livret_proj = []
solde_la = g("Livret A", 6830)
for m in range(1, 13):
    interets = solde_la * (0.024 / 12)
    solde_fin = solde_la + versement_matelas + interets
    livret_proj.append({"Mois": f"M+{m}", "Solde": round(solde_fin, 0)})
    solde_la = solde_fin

df_livret = pd.DataFrame(livret_proj)
fig_livret = px.area(df_livret, x="Mois", y="Solde", text="Solde", color_discrete_sequence=["#27ae60"])
fig_livret.update_traces(texttemplate="%{text:,.0f} €", textposition="top center")
fig_livret.update_layout(yaxis_title="Solde (€)", height=300, margin=dict(t=20, b=20))
fig_livret.add_hline(y=10000, line_dash="dash", line_color="orange", annotation_text="Objectif 10 000 €")
st.plotly_chart(fig_livret, use_container_width=True)
mois_10k = next((r["Mois"] for _, r in df_livret.iterrows() if r["Solde"] >= 10000), "M+12+")
st.info(f"📌 Matelas 10 000 € atteint à **{mois_10k}** avec {versement_matelas:,.0f} €/mois".replace(",", " "))

st.divider()

# ============================================================
# TRANSACTIONS
# ============================================================
st.subheader("🔍 Dernières transactions du mois")
recent = dm[["Date", "Libelle", "Montant", "Categorie"]].copy()
recent["Montant"] = recent["Montant"].apply(lambda x: f"{x:,.2f} €".replace(",", " ") if pd.notna(x) else "")
st.dataframe(recent, hide_index=True, use_container_width=True, height=300)

st.divider()
st.caption("Budget Foyer Kanane — Google Sheets (auto-sync) • Streamlit • par Youcef 🚀")