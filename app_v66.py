import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Optimizer V66", page_icon="🧮", layout="wide")
st.title("🧮 Strategy Optimizer (V66 - Analisi Novembre)")
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

# --- CARICAMENTO FILE ---
@st.cache_data(ttl=0)
def load_data(file):
    try:
        df = pd.read_csv(file, sep=';', encoding='latin1', on_bad_lines='skip', engine='python')
        df.columns = df.columns.str.strip()
        
        # Standardizza nomi
        ren = {
            '1': 'cotaa', '2': 'cotad', 'x': 'cotae', 'X': 'cotae', 
            'eloc': 'elohomeo', 'eloo': 'eloawayo',
            'gfinc': 'scor1', 'gfino': 'scor2'
        }
        new = {}
        for c in df.columns:
            if c.lower() in ren: new[c] = ren[c.lower()]
        df = df.rename(columns=new)
        
        # Pulisce dati numerici
        cols_num = ['cotaa', 'cotae', 'cotad', 'elohomeo', 'eloawayo', 'scor1', 'scor2']
        for c in cols_num:
            if c in df.columns:
                df[c] = df[c].astype(str).str.replace(',', '.', regex=False)
                df[c] = pd.to_numeric(df[c], errors='coerce')

        # Determina Risultato Reale (1, X, 2)
        df['Real_Res'] = '-'
        if 'scor1' in df.columns and 'scor2' in df.columns:
            mask = df['scor1'].notna() & df['scor2'].notna()
            df.loc[mask & (df['scor1'] > df['scor2']), 'Real_Res'] = '1'
            df.loc[mask & (df['scor1'] == df['scor2']), 'Real_Res'] = 'X'
            df.loc[mask & (df['scor1'] < df['scor2']), 'Real_Res'] = '2'
            
        return df.dropna(subset=['cotaa', 'cotad', 'Real_Res']), None
    except Exception as e: return None, str(e)

# --- MOTORE DI SIMULAZIONE MASSIVA ---
def run_optimization(df, base_hfa, use_dyn):
    results = []
    
    for idx, row in df.iterrows():
        if row['Real_Res'] == '-': continue
        
        # 1. Calcola HFA
        curr_hfa = base_hfa
        if use_dyn:
            r1 = row.get('place1a') if pd.notna(row.get('place1a')) else row.get('Place 1a')
            r2 = row.get('place2d') if pd.notna(row.get('place2d')) else row.get('Place 2d')
            if pd.notna(r1) and pd.notna(r2):
                try:
                    curr_hfa += (float(r2) - float(r1)) * 3
                    curr_hfa = max(0, min(curr_hfa, 200))
                except: pass
        
        # 2. Calcola EV
        f1, fx, f2 = no_margin(row['cotaa'], row['cotae'], row['cotad'])
        ph, pa = get_probs(row['elohomeo'], row['eloawayo'], curr_hfa)
        rem = 1 - fx
        fin1 = rem * ph
        fin2 = rem * pa
        
        ev1 = (row['cotaa'] * fin1) - 1
        ev2 = (row['cotad'] * fin2) - 1
        
        # 3. Registra dati per analisi
        # PNL se avessimo giocato 1
        pnl_1 = (row['cotaa'] - 1) if row['Real_Res'] == '1' else -1
        # PNL se avessimo giocato 2
        pnl_2 = (row['cotad'] - 1) if row['Real_Res'] == '2' else -1
        
        results.append({
            'Odds_1': row['cotaa'],
            'Odds_2': row['cotad'],
            'EV_1': ev1 * 100,
            'EV_2': ev2 * 100,
            'PNL_1': pnl_1,
            'PNL_2': pnl_2,
            'HFA_Used': curr_hfa,
            'League': row.get('league', 'Unknown')
        })
        
    return pd.DataFrame(results)

# --- UI ---
st.sidebar.header("⚙️ Parametri Base")
base_hfa = st.sidebar.number_input("HFA Base", 90, step=10)
use_dyn = st.sidebar.checkbox("Usa HFA Dinamico", True)

uploaded = st.file_uploader("Carica File Risultati Novembre (CSV)", type=["csv"])

if uploaded:
    df, err = load_data(uploaded)
    
    if df is not None and not df.empty:
        st.success(f"Caricate {len(df)} partite con risultati.")
        
        # Esegui calcoli su tutto il dataset
        sim_data = run_optimization(df, base_hfa, use_dyn)
        
        tab1, tab2, tab3 = st.tabs(["📉 Perché perdiamo?", "🔍 DIAGNOSTICA (Dove sono i soldi?)", "🏆 Top Campionati"])
        
        with tab1:
            st.subheader("Performance Attuale (Strategia Cecchino)")
            # Simula la strategia attuale
            # Filtri attuali: EV > 4%, Quote 1.50-4.00
            
            mask_away = (sim_data['EV_2'] > 4.0) & (sim_data['Odds_2'].between(1.70, 3.50))
            mask_home = (sim_data['EV_1'] > 4.0) & (sim_data['Odds_1'].between(1.50, 2.50))
            
            profit_away = sim_data[mask_away]['PNL_2'].sum()
            profit_home = sim_data[mask_home]['PNL_1'].sum()
            
            c1, c2 = st.columns(2)
            c1.metric("Risultato Strategia AWAY (2)", f"{profit_away:.2f} u", delta_color="normal")
            c2.metric("Risultato Strategia HOME (1)", f"{profit_home:.2f} u", delta_color="normal")
            
            if profit_away < 0:
                st.error("La strategia AWAY sta perdendo. Probabilmente stiamo sopravvalutando le squadre ospiti.")
            
        with tab2:
            st.subheader("Analisi 'Heatmap': Dove si guadagna davvero?")
            st.write("Ho diviso le partite in fasce di quota. Vediamo quali fasce sono in verde.")
            
            # Crea fasce di quota
            bins = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 10.0]
            labels = ['1.0-1.5', '1.5-2.0', '2.0-2.5', '2.5-3.0', '3.0-4.0', '4.0+']
            
            sim_data['Odds_Bin_1'] = pd.cut(sim_data['Odds_1'], bins=bins, labels=labels)
            sim_data['Odds_Bin_2'] = pd.cut(sim_data['Odds_2'], bins=bins, labels=labels)
            
            # Calcola ROI per ogni fascia (solo se EV positivo)
            # Analisi HOME
            st.write("#### 🏠 Rendimento Puntate CASA (1) con EV > 2%")
            df_h = sim_data[sim_data['EV_1'] > 2.0].groupby('Odds_Bin_1')['PNL_1'].sum().reset_index()
            st.bar_chart(df_h.set_index('Odds_Bin_1'))
            
            # Analisi AWAY
            st.write("#### ✈️ Rendimento Puntate OSPITE (2) con EV > 2%")
            df_a = sim_data[sim_data['EV_2'] > 2.0].groupby('Odds_Bin_2')['PNL_2'].sum().reset_index()
            st.bar_chart(df_a.set_index('Odds_Bin_2'))
            
            st.info("💡 **INTERPRETAZIONE:** Guarda le barre che vanno verso l'alto. Quelle sono le fasce di quota dove il tuo modello funziona. Se vedi barre rosse verso il basso tra 2.5 e 3.0, significa che devi SMETTERE di scommettere su quelle quote.")

        with tab3:
            st.subheader("Quali campionati portano profitto?")
            # Raggruppa per campionato
            league_perf = sim_data.groupby('League')[['PNL_1', 'PNL_2']].sum().reset_index()
            league_perf['Total'] = league_perf['PNL_1'] + league_perf['PNL_2']
            league_perf = league_perf.sort_values('Total', ascending=False).head(15)
            
            st.dataframe(league_perf.style.format("{:.2f}"))
            st.write("Questi sono i campionati dove il modello ha 'letto' meglio le partite a Novembre.")

    else:
        st.error(f"Errore lettura file: {err}")
