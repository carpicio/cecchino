import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Optimizer V69 - EV Range", page_icon="🎚️", layout="wide")
st.title("🎚️ Strategy Fixer (V69 - EV Range)")
st.markdown("""
Usa il nuovo slider **Range EV** per selezionare un intervallo specifico (es. da 2% a 10%).
Spesso eliminare gli EV estremi (>15%) riduce la varianza e migliora il profitto.
""")
st.markdown("---")

# --- FUNZIONI DI CALCOLO ---
def get_probs(elo_h, elo_a, hfa):
    try:
        diff = elo_a - (elo_h + hfa)
        exp = diff / 400
        p_h = 1 / (1 + 10**exp)
        return p_h, 1 - p_h
    except: return 0, 0

def no_margin(o1, ox, o2):
    try:
        if o1<=0 or ox<=0 or o2<=0: return 0,0,0
        i1 = 1/o1; ix = 1/ox; i2 = 1/o2
        s = i1 + ix + i2
        return i1/s, ix/s, i2/s
    except: return 0,0,0

@st.cache_data(ttl=0)
def load_data(file):
    try:
        df = pd.read_csv(file, sep=';', encoding='latin1', on_bad_lines='skip', engine='python')
        df.columns = df.columns.str.strip()
        ren = {
            '1': 'cotaa', '2': 'cotad', 'x': 'cotae', 'X': 'cotae', 
            'eloc': 'elohomeo', 'eloo': 'eloawayo',
            'gfinc': 'scor1', 'gfino': 'scor2'
        }
        new = {}
        for c in df.columns:
            if c.lower() in ren: new[c] = ren[c.lower()]
        df = df.rename(columns=new)
        
        cols_num = ['cotaa', 'cotae', 'cotad', 'elohomeo', 'eloawayo', 'scor1', 'scor2']
        for c in cols_num:
            if c in df.columns:
                df[c] = df[c].astype(str).str.replace(',', '.', regex=False)
                df[c] = pd.to_numeric(df[c], errors='coerce')

        df['Real_Res'] = '-'
        if 'scor1' in df.columns and 'scor2' in df.columns:
            mask = df['scor1'].notna() & df['scor2'].notna()
            df.loc[mask & (df['scor1'] > df['scor2']), 'Real_Res'] = '1'
            df.loc[mask & (df['scor1'] == df['scor2']), 'Real_Res'] = 'X'
            df.loc[mask & (df['scor1'] < df['scor2']), 'Real_Res'] = '2'
            
        return df.dropna(subset=['cotaa', 'cotad', 'Real_Res']), None
    except Exception as e: return None, str(e)

# --- CALCOLO MASSIVO ---
def calculate_all_metrics(df, base_hfa, use_dyn):
    data = []
    for idx, row in df.iterrows():
        if row['Real_Res'] == '-': continue
        
        curr_hfa = base_hfa
        if use_dyn:
            r1 = row.get('place1a') if pd.notna(row.get('place1a')) else row.get('Place 1a')
            r2 = row.get('place2d') if pd.notna(row.get('place2d')) else row.get('Place 2d')
            if pd.notna(r1) and pd.notna(r2):
                try:
                    curr_hfa += (float(r2) - float(r1)) * 3
                    curr_hfa = max(0, min(curr_hfa, 200))
                except: pass
        
        f1, fx, f2 = no_margin(row['cotaa'], row['cotae'], row['cotad'])
        ph, pa = get_probs(row['elohomeo'], row['eloawayo'], curr_hfa)
        rem = 1 - fx
        fin1 = rem * ph
        fin2 = rem * pa
        
        ev1 = (row['cotaa'] * fin1) - 1
        ev2 = (row['cotad'] * fin2) - 1
        
        pnl_1 = (row['cotaa'] - 1) if row['Real_Res'] == '1' else -1
        pnl_2 = (row['cotad'] - 1) if row['Real_Res'] == '2' else -1
        
        data.append({
            'Odds_1': row['cotaa'],
            'Odds_2': row['cotad'],
            'EV_1': ev1 * 100,
            'EV_2': ev2 * 100,
            'PNL_1': pnl_1,
            'PNL_2': pnl_2,
            'League': row.get('league', 'Unknown'),
            'Match': f"{row.get('txtechipa1')} vs {row.get('txtechipa2')}"
        })
    return pd.DataFrame(data)

# --- UI ---
st.sidebar.header("1. Parametri Modello")
base_hfa = st.sidebar.number_input("HFA Base", 90, step=10)
use_dyn = st.sidebar.checkbox("Usa HFA Dinamico", True)

uploaded = st.sidebar.file_uploader("Carica File Risultati (CSV)", type=["csv"])

if uploaded:
    raw_df, err = load_data(uploaded)
    
    if raw_df is not None and not raw_df.empty:
        # Calcola tutto
        full_data = calculate_all_metrics(raw_df, base_hfa, use_dyn)
        
        st.sidebar.header("2. FILTRI DI CORREZIONE")
        
        # NUOVO SLIDER RANGE EV
        min_ev, max_ev = st.sidebar.slider(
            "Range EV (%)", 
            min_value=-5.0, 
            max_value=30.0, 
            value=(2.0, 15.0), 
            step=0.5,
            help="Seleziona un intervallo. Consiglio: evita valori estremi (>20%) che spesso sono errori."
        )
        
        min_odds, max_odds = st.sidebar.slider("Range Quote Accettate", 1.20, 10.0, (1.50, 3.50))
        
        # Filtra il dataset
        # Strategia AWAY
        mask_away = (
            (full_data['EV_2'] >= min_ev) & (full_data['EV_2'] <= max_ev) &
            (full_data['Odds_2'] >= min_odds) & (full_data['Odds_2'] <= max_odds)
        )
        
        # Strategia HOME
        mask_home = (
            (full_data['EV_1'] >= min_ev) & (full_data['EV_1'] <= max_ev) &
            (full_data['Odds_1'] >= min_odds) & (full_data['Odds_1'] <= max_odds)
        )
        
        df_away = full_data[mask_away]
        df_home = full_data[mask_home]
        
        # CALCOLO PROFITTI
        pnl_away = df_away['PNL_2'].sum()
        pnl_home = df_home['PNL_1'].sum()
        total_pnl = pnl_away + pnl_home
        
        bets_count = len(df_away) + len(df_home)
        roi = 0
        if bets_count > 0:
            roi = (total_pnl / bets_count) * 100
            
        # --- DISPLAY RISULTATI ---
        st.subheader("💡 Risultati Simulazione con Filtri Attivi")
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Scommesse Totali", bets_count)
        k2.metric("Profitto Netto (Unità)", f"{total_pnl:.2f} u", delta_color="normal")
        k3.metric("ROI %", f"{roi:.2f}%", delta_color="normal")
        
        best_strat = "NESSUNA"
        if pnl_home > pnl_away and pnl_home > 0: best_strat = "CASA (1)"
        elif pnl_away > pnl_home and pnl_away > 0: best_strat = "OSPITE (2)"
        
        k4.metric("Migliore Strategia", best_strat, delta=f"{max(pnl_home, pnl_away):.2f} u")

        if total_pnl > 0:
            st.success("✅ CONFIGURAZIONE VINCENTE TROVATA!")
        else:
            st.warning("⚠️ Ancora in perdita. Prova a stringere il range EV (es. 4-10%) o abbassare la Quota Max.")

        st.markdown("---")
        
        # DETTAGLIO
        c1, c2 = st.columns(2)
        
        with c1:
            st.write(f"### 🏠 Strategia CASA (1) - {len(df_home)} bets")
            if not df_home.empty:
                st.dataframe(
                    df_home[['Match', 'Odds_1', 'EV_1', 'PNL_1']].style.format({
                        'Odds_1': '{:.2f}', 'EV_1': '{:.2f}%', 'PNL_1': '{:.2f}'
                    }), 
                    height=300
                )
        
        with c2:
            st.write(f"### ✈️ Strategia OSPITE (2) - {len(df_away)} bets")
            if not df_away.empty:
                st.dataframe(
                    df_away[['Match', 'Odds_2', 'EV_2', 'PNL_2']].style.format({
                        'Odds_2': '{:.2f}', 'EV_2': '{:.2f}%', 'PNL_2': '{:.2f}'
                    }), 
                    height=300
                )

    else:
        st.error(f"Errore: {err}")
