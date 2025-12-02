import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Sniper Bet V65 - Validator", page_icon="⚖️", layout="wide")
st.title("⚖️ Sniper Validator (V65)")
st.markdown("---")

# --- CORE LOGIC (Calcolo Pronostici) ---
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

def calc_signal(row, base_hfa, dyn):
    res = {'Signal': 'SKIP', 'EV_1': 0, 'EV_2': 0, 'Odds_Play': 0, 'Pick': None}
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
            r1 = row.get('place1a'); 
            if pd.isna(r1): r1 = row.get('Place 1a')
            if pd.isna(r1): r1 = row.get('place 1a')
            
            r2 = row.get('place2d')
            if pd.isna(r2): r2 = row.get('Place 2d')
            if pd.isna(r2): r2 = row.get('place 2d')
            
            if pd.notna(r1) and pd.notna(r2):
                try:
                    d = float(r2) - float(r1)
                    adj = d * 3
                    curr_hfa += adj
                    curr_hfa = max(0, min(curr_hfa, 200))
                except: pass
        
        f1, fx, f2 = no_margin(o1, ox, o2)
        ph, pa = get_probs(elo_h, elo_a, curr_hfa)
        rem = 1 - fx
        fin1 = rem * ph
        fin2 = rem * pa
        
        ev1 = (o1 * fin1) - 1
        ev2 = (o2 * fin2) - 1
        
        res['EV_1'] = round(ev1 * 100, 2)
        res['EV_2'] = round(ev2 * 100, 2)
        
        # LOGICA SEGNALI (Percentuale)
        # Strategia Ospite
        if (ev2 * 100) > 4.0 and 1.70 <= o2 <= 3.50:
            res['Signal'] = '💎 AWAY'
            res['Pick'] = '2'
            res['Odds_Play'] = o2
        elif (ev2 * 100) > 1.5 and 1.50 <= o2 <= 4.00:
            res['Signal'] = '✅ VALUE 2'
            res['Pick'] = '2'
            res['Odds_Play'] = o2
            
        # Strategia Casa
        elif (ev1 * 100) > 4.0 and 1.50 <= o1 <= 2.50:
            res['Signal'] = '💎 HOME'
            res['Pick'] = '1'
            res['Odds_Play'] = o1
        elif (ev1 * 100) > 1.5 and 1.40 <= o1 <= 3.00:
            res['Signal'] = '✅ VALUE 1'
            res['Pick'] = '1'
            res['Odds_Play'] = o1

    except: pass
    return pd.Series(res)

@st.cache_data(ttl=0)
def load_and_standardize(file):
    try:
        # Tenta lettura
        df = pd.read_csv(file, sep=';', encoding='latin1', on_bad_lines='skip', engine='python')
        df.columns = df.columns.str.strip()
        
        # Mapping Standard
        ren = {
            '1': 'cotaa', '2': 'cotad', 'x': 'cotae', 'X': 'cotae', 
            'eloc': 'elohomeo', 'eloo': 'eloawayo',
            'home': 'txtechipa1', 'away': 'txtechipa2', 
            'casa': 'txtechipa1', 'ospite': 'txtechipa2',
            'gfinc': 'scor1', 'gfino': 'scor2'
        }
        new = {}
        for c in df.columns:
            if c.lower() in ren: new[c] = ren[c.lower()]
        df = df.rename(columns=new)
        
        # Crea ID univoco per il match (es. Inter-Juve) per incrociare i file
        # Normalizziamo togliendo spazi e minuscolo
        df['MatchID'] = df['txtechipa1'].str.lower().str.replace(' ', '') + "-" + df['txtechipa2'].str.lower().str.replace(' ', '')
        
        return df, None
    except Exception as e: return None, str(e)

# --- UI ---
st.sidebar.header("⚙️ Impostazioni Strategia")
base_hfa = st.sidebar.number_input("HFA Base", 90, step=10)
use_dyn = st.sidebar.checkbox("Usa Classifica", True)

c1, c2 = st.columns(2)

with c1:
    st.subheader("1. File Analisi (Quote & Elo)")
    file_analysis = st.file_uploader("Carica CSV Partite (Prematch)", type=["csv"], key="f1")

with c2:
    st.subheader("2. File Risultati (Opzionale)")
    file_results = st.file_uploader("Carica CSV Risultati (Postmatch)", type=["csv"], key="f2")
    st.caption("Se non lo carichi, il programma cercherà i risultati nel File 1.")

if file_analysis:
    df_main, err1 = load_and_standardize(file_analysis)
    
    if df_main is not None:
        # 1. CALCOLA I SEGNALI SUL FILE 1
        st.info(f"Analisi in corso su {len(df_main)} partite...")
        signals = df_main.apply(lambda r: calc_signal(r, base_hfa, use_dyn), axis=1)
        df_main = pd.concat([df_main, signals], axis=1)
        
        # Filtra solo le giocate
        played_df = df_main[df_main['Signal'] != 'SKIP'].copy()
        
        # 2. CERCA I RISULTATI (Dal File 2 o dal File 1)
        df_res = None
        if file_results:
            df_res, err2 = load_and_standardize(file_results)
            if df_res is None: st.error(f"Errore File Risultati: {err2}")
        else:
            df_res = df_main # Cerca nello stesso file se non ne carichi un altro

        if not played_df.empty:
            st.success(f"Trovate {len(played_df)} Scommesse Potenziali.")
            
            # 3. INCROCIO DATI (MATCHING)
            # Dobbiamo trovare il risultato per ogni scommessa
            if df_res is not None and 'scor1' in df_res.columns:
                # Crea dizionario risultati dal file risultati: MatchID -> (scor1, scor2)
                res_map = df_res.set_index('MatchID')[['scor1', 'scor2']].to_dict('index')
                
                valid_outcomes = 0
                profit = 0
                wins = 0
                history = []
                
                for idx, row in played_df.iterrows():
                    match_id = row['MatchID']
                    
                    # Cerca risultato
                    s1, s2 = np.nan, np.nan
                    if match_id in res_map:
                        try:
                            s1 = float(str(res_map[match_id]['scor1']).replace(',','.'))
                            s2 = float(str(res_map[match_id]['scor2']).replace(',','.'))
                        except: pass
                    
                    if not np.isnan(s1) and not np.isnan(s2):
                        # Calcola esito reale
                        real_res = 'X'
                        if s1 > s2: real_res = '1'
                        elif s2 > s1: real_res = '2'
                        
                        # Calcola Profitto (Stake fisso 10€ per simulazione)
                        stake = 10
                        pnl = -stake
                        status = '❌ LOSS'
                        
                        if row['Pick'] == real_res:
                            pnl = (row['Odds_Play'] * stake) - stake
                            status = '✅ WIN'
                            wins += 1
                        
                        profit += pnl
                        valid_outcomes += 1
                        
                        history.append({
                            'Match': f"{row['txtechipa1']} vs {row['txtechipa2']}",
                            'Segnale': row['Signal'],
                            'Pick': row['Pick'],
                            'Quota': row['Odds_Play'],
                            'Risultato': f"{int(s1)}-{int(s2)} ({real_res})",
                            'Esito': status,
                            'Profitto': pnl
                        })
                
                # MOSTRA REPORT
                if valid_outcomes > 0:
                    roi = (profit / (valid_outcomes * 10)) * 100
                    win_rate = (wins / valid_outcomes) * 100
                    
                    st.divider()
                    st.header("📊 RISULTATO VERIFICA")
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Partite Verificate", f"{valid_outcomes} / {len(played_df)}")
                    m2.metric("Vittorie", f"{wins}")
                    m3.metric("Win Rate", f"{win_rate:.1f}%")
                    m4.metric("Profitto Netto (Stake 10€)", f"{profit:.2f}€", delta=f"{roi:.2f}% ROI")
                    
                    st.subheader("Dettaglio Giocate")
                    res_df = pd.DataFrame(history)
                    
                    # Colora la tabella
                    def highlight_rows(row):
                        color = '#d4edda' if 'WIN' in row['Esito'] else '#f8d7da'
                        return [f'background-color: {color}' for _ in row]
                        
                    st.dataframe(res_df.style.apply(highlight_rows, axis=1), use_container_width=True)
                else:
                    st.warning("⚠️ Nessun risultato trovato per le partite selezionate. Controlla che i nomi delle squadre coincidano nei due file o che il file contenga le colonne 'scor1' e 'scor2'.")
            else:
                st.warning("Il file dei risultati non contiene le colonne 'scor1' e 'scor2'. Impossibile verificare.")
                st.dataframe(played_df) # Mostra solo le previsioni senza verifica
        else:
            st.warning("Nessuna scommessa trovata con i filtri attuali.")
    else:
        st.error(f"Errore File 1: {err1}")
