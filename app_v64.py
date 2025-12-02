import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Sniper Bet V64", page_icon="🎯", layout="wide")
st.title("🎯 Value Bet Sniper (V64 - Fix Novembre)")
st.markdown("---")

# --- CORE LOGIC ---
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

def calc_row(row, base_hfa, dyn):
    # Setup
    res = {'EV_1': -1, 'EV_X': -1, 'EV_2': -1, 'HFA': base_hfa, 'Signal': 'SKIP'}
    try:
        def to_f(v):
            try: return float(str(v).replace(',', '.'))
            except: return 0.0

        elo_h = to_f(row.get('elohomeo', 1500))
        elo_a = to_f(row.get('eloawayo', 1500))
        o1 = to_f(row.get('cotaa', 0))
        ox = to_f(row.get('cotae', 0))
        o2 = to_f(row.get('cotad', 0))
        
        # HFA Dinamico (Fix Nomi Colonne)
        curr_hfa = base_hfa
        if dyn:
            # Cerca tutte le varianti possibili del nome colonna
            r1 = row.get('place1a') 
            if pd.isna(r1): r1 = row.get('Place 1a')
            if pd.isna(r1): r1 = row.get('place 1a')
            
            r2 = row.get('place2d')
            if pd.isna(r2): r2 = row.get('Place 2d')
            if pd.isna(r2): r2 = row.get('place 2d')
            
            # Logica: Se ospite (r2) è molto meglio di casa (r1), riduci HFA
            if pd.notna(r1) and pd.notna(r2):
                try:
                    d = float(r2) - float(r1) # es. Ospite(3) - Casa(15) = -12
                    adj = d * 3 # -36 punti
                    curr_hfa += adj
                    curr_hfa = max(0, min(curr_hfa, 200))
                except: pass
        
        res['HFA'] = int(curr_hfa)
        
        # Matematica
        f1, fx, f2 = no_margin(o1, ox, o2)
        ph, pa = get_probs(elo_h, elo_a, curr_hfa)
        rem = 1 - fx
        fin1 = rem * ph
        fin2 = rem * pa
        
        ev1 = (o1 * fin1) - 1
        ev2 = (o2 * fin2) - 1
        
        # Salva in percentuale per visualizzazione
        res['EV_1'] = round(ev1 * 100, 2)
        res['EV_2'] = round(ev2 * 100, 2)
        
        # --- LOGICA CECCHINO (FIX PERCENTUALE) ---
        # Usiamo ev2 * 100 per confrontare con 4.0 (4%)
        
        # Strategia Ospite (Away Value)
        if (ev2 * 100) > 4.0 and 1.70 <= o2 <= 3.50:
            res['Signal'] = '💎 AWAY'
        elif (ev2 * 100) > 1.5 and 1.50 <= o2 <= 4.00:
            res['Signal'] = '✅ VALUE 2'
            
        # Strategia Casa (Home Value)
        elif (ev1 * 100) > 4.0 and 1.50 <= o1 <= 2.50:
            res['Signal'] = '💎 HOME'
        elif (ev1 * 100) > 1.5 and 1.40 <= o1 <= 3.00:
            res['Signal'] = '✅ VALUE 1'

    except: pass
    return pd.Series(res)

@st.cache_data(ttl=0)
def load_file(file, hfa, dyn):
    try:
        # Forza separatore punto e virgola per il tuo file
        df = pd.read_csv(file, sep=';', encoding='latin1', on_bad_lines='skip', engine='python')
        df.columns = df.columns.str.strip()
        # Mapping flessibile
        ren = {
            '1': 'cotaa', '2': 'cotad', 'x': 'cotae', 'X': 'cotae', 
            'eloc': 'elohomeo', 'eloo': 'eloawayo',
            'home': 'txtechipa1', 'away': 'txtechipa2', 'casa': 'txtechipa1', 'ospite': 'txtechipa2'
        }
        new = {}
        for c in df.columns:
            if c.lower() in ren: new[c] = ren[c.lower()]
        df = df.rename(columns=new)
        df = df.dropna(subset=['cotaa']) # Rimuove righe vuote
        
        if not df.empty:
            calc = df.apply(lambda r: calc_row(r, hfa, dyn), axis=1)
            df = pd.concat([df, calc], axis=1)
        return df, None
    except Exception as e: return None, str(e)

# --- UI ---
st.sidebar.header("⚙️ Impostazioni")
base_hfa = st.sidebar.number_input("HFA Base", 90, step=10)
use_dyn = st.sidebar.checkbox("Usa Classifica (Dynamic)", True)
uploaded = st.sidebar.file_uploader("Carica Partite Future (CSV)", type=["csv"])

if uploaded:
    df, err = load_file(uploaded, base_hfa, use_dyn)
    if df is not None:
        # Filtro Sniper
        sniper_df = df[df['Signal'] != 'SKIP'].copy()
        
        if not sniper_df.empty:
            # Ordina: Prima i Diamanti, poi il Valore
            sniper_df['SortOrder'] = sniper_df['Signal'].map({'💎 AWAY': 1, '💎 HOME': 2, '✅ VALUE 2': 3, '✅ VALUE 1': 4})
            sniper_df = sniper_df.sort_values('SortOrder')
            
            st.subheader(f"🎯 Trovate {len(sniper_df)} Occasioni su {len(df)} Partite")
            
            # Tabella Semplificata per Operare
            cols_view = ['Signal', 'datameci', 'league', 'txtechipa1', 'txtechipa2', 'HFA', 'cotaa', 'cotad', 'EV_1', 'EV_2']
            final_cols = [c for c in cols_view if c in sniper_df.columns]
            
            st.dataframe(
                sniper_df[final_cols].style.applymap(
                    lambda x: 'background-color: #d4edda; color: green' if '💎' in str(x) else '', subset=['Signal']
                ),
                use_container_width=True,
                height=600
            )
        else:
            st.info(f"Analizzate {len(df)} partite, ma nessuna occasione '💎' trovata con i parametri attuali.")
            
        st.markdown("---")
        with st.expander("📂 Vedi tutte le partite (Dati Completi)"):
            st.dataframe(df)
    else:
        st.error(f"Errore: {err}")
else:
    st.info("Carica il file CSV con le partite da giocare.")
