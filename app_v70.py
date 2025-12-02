import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Sniper V70 - Golden Strategy", page_icon="🏆", layout="wide")
st.title("🏆 Sniper Bet V70 (Configurazione Vincente)")
st.markdown(f"""
### ⚡ STRATEGIA ATTIVA: "IL CECCHINO OSPITE"
Stiamo cercando solo le situazioni che hanno generato **+11.52u** a Novembre:
- **Puntata:** SQUADRA OSPITE (2)
- **Range Quote:** 2.06 - 2.80
- **Valore (EV):** 11% - 19.5%
""")
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

def calc_sniper(row, base_hfa, dyn):
    res = {'Signal': 'SKIP', 'EV': 0, 'Pick': '-', 'HFA': base_hfa}
    try:
        def to_f(v):
            try: return float(str(v).replace(',', '.'))
            except: return 0.0

        elo_h = to_f(row.get('elohomeo', 1500))
        elo_a = to_f(row.get('eloawayo', 1500))
        o1 = to_f(row.get('cotaa', 0))
        ox = to_f(row.get('cotae', 0))
        o2 = to_f(row.get('cotad', 0))
        
        # HFA Dinamico
        curr_hfa = base_hfa
        if dyn:
            r1 = row.get('place1a') or row.get('Place 1a') or row.get('place 1a')
            r2 = row.get('place2d') or row.get('Place 2d') or row.get('place 2d')
            
            if pd.notna(r1) and pd.notna(r2):
                try:
                    curr_hfa += (float(r2) - float(r1)) * 3
                    curr_hfa = max(0, min(curr_hfa, 200))
                except: pass
        
        res['HFA'] = int(curr_hfa)
        
        # Calcoli
        f1, fx, f2 = no_margin(o1, ox, o2)
        ph, pa = get_probs(elo_h, elo_a, curr_hfa)
        rem = 1 - fx
        fin2 = rem * pa # Ci interessa solo l'ospite per ora
        
        ev2 = (o2 * fin2) - 1
        ev2_perc = ev2 * 100
        res['EV'] = round(ev2_perc, 2)
        
        # --- FILTRO VINCENTE (I tuoi parametri) ---
        # Range Quote: 2.06 - 2.80
        # Range EV: 11% - 19.5%
        if (11.0 <= ev2_perc <= 19.5) and (2.06 <= o2 <= 2.80):
            res['Signal'] = '💎 GOLDEN PICK'
            res['Pick'] = '2 (Ospite)'

    except: pass
    return pd.Series(res)

@st.cache_data(ttl=0)
def load_data(file, hfa, dyn):
    try:
        df = pd.read_csv(file, sep=';', encoding='latin1', on_bad_lines='skip', engine='python')
        df.columns = df.columns.str.strip()
        ren = {
            '1': 'cotaa', '2': 'cotad', 'x': 'cotae', 'X': 'cotae', 
            'eloc': 'elohomeo', 'eloo': 'eloawayo',
            'home': 'txtechipa1', 'away': 'txtechipa2', 'casa': 'txtechipa1', 'ospite': 'txtechipa2'
        }
        new = {}
        for c in df.columns:
            if c.lower() in ren: new[c] = ren[c.lower()]
        df = df.rename(columns=new)
        df = df.dropna(subset=['cotaa'])
        
        if not df.empty:
            calc = df.apply(lambda r: calc_sniper(r, hfa, dyn), axis=1)
            df = pd.concat([df, calc], axis=1)
        return df, None
    except Exception as e: return None, str(e)

# --- UI ---
st.sidebar.header("⚙️ Parametri Vincenti")
# Ho impostato i default sui tuoi valori vincenti
base_hfa = st.sidebar.number_input("HFA Base", 90, step=10)
use_dyn = st.sidebar.checkbox("Usa HFA Dinamico", True)

st.sidebar.markdown("---")
st.sidebar.info("I filtri sono automatici sulla strategia 2.06-2.80 / EV 11-19.5%")

uploaded = st.file_uploader("Carica File Partite (CSV)", type=["csv"])

if uploaded:
    df, err = load_data(uploaded, base_hfa, use_dyn)
    
    if df is not None:
        # Filtra solo i Diamanti
        gold_df = df[df['Signal'] == '💎 GOLDEN PICK'].copy()
        
        if not gold_df.empty:
            st.success(f"🎉 TROVATE {len(gold_df)} PARTITE D'ORO!")
            st.balloons()
            
            # Tabella Operativa
            cols_show = ['datameci', 'league', 'txtechipa1', 'txtechipa2', 'cotad', 'EV', 'HFA']
            final_cols = [c for c in cols_show if c in gold_df.columns]
            
            st.dataframe(
                gold_df[final_cols].style.applymap(
                    lambda x: 'background-color: #d4edda; color: #155724; font-weight: bold', 
                    subset=['cotad', 'EV']
                ),
                use_container_width=True,
                height=500
            )
            
            st.markdown("### 📝 Consigli Operativi")
            st.info("""
            1. **Giocata:** Segno 2 (Vittoria Ospite)
            2. **Stake:** Usa uno stake fisso (es. 2% del budget) visto che le quote sono stabili.
            3. **Verifica:** Controlla che non manchino giocatori chiave dell'ospite prima di piazzare.
            """)
            
        else:
            st.warning("Nessuna partita rientra nei parametri 'Golden' oggi. Meglio non forzare la giocata.")
            
        with st.expander("Vedi tutte le partite analizzate"):
            st.dataframe(df)
            
    else:
        st.error(f"Errore: {err}")
