import streamlit as st
import sqlite3
import hashlib
import random
import os
import json
import sys
import io
import time
import base64
import pandas as pd
import plotly.express as px
from fpdf import FPDF
from streamlit_ace import st_ace  # NEW: Professional Code Editor
from openai import OpenAI

# --- 1. SETTINGS & THEME ENGINE ---
st.set_page_config(page_title="Hilda's Epic IT-RPG", page_icon="⚔️", layout="wide")

# VS Code Theme Palettes
THEMES = {
    "Dracula": {"bg": "#282a36", "sidebar": "#21222c", "text": "#f8f8f2", "accent": "#bd93f9", "ace": "dracula"},
    "Monokai": {"bg": "#272822", "sidebar": "#1e1f1c", "text": "#f8f8f2", "accent": "#ae81ff", "ace": "monokai"},
    "One Dark": {"bg": "#282c34", "sidebar": "#21252b", "text": "#abb2bf", "accent": "#61afef", "ace": "tomorrow_night"},
    "SynthWave 84": {"bg": "#2b213a", "sidebar": "#241b30", "text": "#ffffff", "accent": "#f92aad", "ace": "chaos"}
}

def apply_theme(theme_name):
    t = THEMES.get(theme_name, THEMES["Dracula"])
    st.markdown(f"""
        <style>
        /* Base Backgrounds */
        .stApp, .main {{ background-color: {t['bg']} !important; color: {t['text']} !important; }}
        section[data-testid="stSidebar"] {{ background-color: {t['sidebar']} !important; }}
        
        /* Typography & Headers */
        h1, h2, h3, p, div, span, label {{ color: {t['text']} !important; }}
        
        /* УСИЛЕННЫЙ СТИЛЬ ДЛЯ ТЕКСТОВЫХ ПОЛЕЙ */
        .stTextInput div[data-baseweb="base-input"], 
        .stTextInput div[data-baseweb="input"] {{
            background-color: {t['sidebar']} !important;
            border: 2px solid #555 !important;
            border-radius: 8px !important;
            transition: 0.3s !important;
        }}
        
        .stTextInput div[data-baseweb="base-input"]:focus-within,
        .stTextInput div[data-baseweb="input"]:focus-within {{
            border-color: {t['accent']} !important;
            box-shadow: 0 0 10px {t['accent']} !important;
        }}
        
        .stTextInput input {{
            color: {t['text']} !important;
            -webkit-text-fill-color: {t['text']} !important;
            background-color: transparent !important;
        }}
        
        /* Custom UI Elements */
        .skill-card {{ background: {t['sidebar']}; padding: 15px; border-radius: 5px; border-left: 4px solid {t['accent']}; margin-bottom: 5px; font-family: monospace; }}
        .skill-locked {{ border-left: 4px solid #ff4b4b; opacity: 0.6; }}
        .monster-box {{ font-family: monospace; background: #000; color: #ff4b4b; padding: 20px; border-radius: 5px; text-align: center; border: 1px solid #333; }}
        .avatar-large {{ font-size: 90px; text-align: center; margin-bottom: -10px; line-height: 1; }}
        .term-log {{ background-color: #050505; color: #00ff00; padding: 15px; border-radius: 5px; font-family: monospace; height: 180px; overflow-y: auto; border: 1px solid #333; }}
        
        /* Hide Native Audio */
        audio {{ display: none !important; }}
        
        /* Primary Buttons */
        div.stButton > button:first-child {{ background-color: {t['accent']} !important; color: #000 !important; font-weight: bold; border: none; }}
        </style>
    """, unsafe_allow_html=True)
    
# --- 2. DATABASE & HELPER FUNCTIONS ---
def init_db():
    conn = sqlite3.connect('rpg_world.db')
    c = conn.cursor()
    # Added 'theme' column
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password_hash TEXT, salt_front TEXT, salt_back TEXT, progress TEXT, display_name TEXT, avatar TEXT, theme TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_hash(password, salt_f, salt_b):
    return hashlib.sha256((salt_f + password + salt_b).encode()).hexdigest()

def update_profile(username, new_name, new_avatar, new_theme):
    conn = sqlite3.connect('rpg_world.db')
    c = conn.cursor()
    c.execute("UPDATE users SET display_name=?, avatar=?, theme=? WHERE username=?", (new_name, new_avatar, new_theme, username))
    conn.commit()
    conn.close()

def play_sound(file_name):
    if os.path.exists(file_name):
        st.audio(file_name, format="audio/mp3", autoplay=True)

def create_pdf(name):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 24)
    pdf.cell(200, 20, txt="PYTHON ARCHMAGE DIPLOMA", ln=True, align='C')
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(200, 20, txt=name.upper(), ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1')

# --- 3. GAME DATA ---
TASKS = {
    'Variables': {"task": "x = 100", "check": "x == 100", "loot": "🧪 Data Potion", "category": "Syntax"},
    'Lists': {"task": "L = [1, 2, 3]", "check": "L == [1, 2, 3]", "loot": "🎒 Index Bag", "category": "Syntax"},
    'Loops': {"task": "total = 15 (sum 1 to 5)", "check": "total == 15", "loot": "🔄 Loop Ring", "category": "Logic"},
    'Conditionals': {"task": "res = 'ok' if 5 > 0 else 'no'", "check": "res == 'ok'", "loot": "⚖️ Logic Scales", "category": "Logic"},
    'Exceptions': {"task": "try/except that sets 'err' = True", "check": "err == True", "loot": "🛡️ Error Shield", "category": "Architecture"},
    'Functions': {"task": "def f(): return 'quack'", "check": "f() == 'quack'", "loot": "📜 Summon Scroll", "category": "Architecture"},
    'Files': {"task": "f = open('test.txt', 'w')", "check": "'f' in locals()", "loot": "🗃️ Archive Key", "category": "Tools"},
    'Testing': {"task": "assert 2 + 2 == 4", "check": "True", "loot": "🔎 Debugger Glass", "category": "Tools"},
    'OOP': {"task": "class Hero: hp = 100", "check": "Hero().hp == 100", "loot": "🧱 Creator Stone", "category": "Architecture"},
    'GUI': {"task": "ui = 'streamlit'", "check": "ui == 'streamlit'", "loot": "🖼️ UI Mirror", "category": "Tools"},
    'SQL': {"task": "q = 'SELECT *'", "check": "'select' in q.lower()", "loot": "🗝️ DB Lockpick", "category": "Database"}
}
# FIX: Added a double backslash '\\' to the Error Ghost ASCII art
MONSTERS = ["(ง'̀-'́)ง\nBinary Slime", "[✖‿✖]\nArray Hydra", "༼ つ ◕_◕ ༽つ\nLoop Spirit", "(҂‾ ▱ ‾)\nIf-Else Golem", "¯\\_(ツ)_/¯\nError Ghost", "ʕ•ᴥ•ʔ\nFunction Bear", "[̲̅$̲̅(̲̅5̲̅)̲̅$̲̅]\nFile Mimic", "(⌐■_■)\nDebug Sniper", "🤖\nClass Titan", "🖼️\nWindow Dragon", "🐙\nSQL Kraken"]
AVATARS = {"🧙‍♂️ Code Wizard": "🧙‍♂️", "🥷 Cyber Ninja": "🥷", "🧝‍♀️ Data Elf": "🧝‍♀️", "👨‍💻 Tech Knight": "👨‍💻"}
TITLES = {1: "Wanderer 🎒", 2: "Code Apprentice 📖", 3: "Script Master ⚡", 4: "Python Archmage 🧙‍♂️", 5: "Database Tamer 🐉", 6: "Server Legend 👑"}

# --- 4. AUTHENTICATION & MAIN LOBBY ---
# --- 4. AUTHENTICATION & MAIN LOBBY ---
if 'username' not in st.session_state:
    apply_theme("Dracula") # <--- ВОТ ЭТА СТРОЧКА ВЕРНЕТ СТИЛИ И БОЛЬШИЕ АВАТАРКИ
    
    # ЭПИЧНЫЙ ЭКРАН ВХОДА (ВМЕСТО САЙДБАРА)
    st.markdown("<h1 style='text-align: center; font-size: 3em;'>⚔️ Python Mastery RPG</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.2em; color: #888;'>Enter the realm of Code Town, defeat the Syntax Monsters, and become an Archmage.</p>", unsafe_allow_html=True)
    st.write("")
    st.write("")
    
    col_lore, col_auth = st.columns([1.5, 1])
    
    with col_lore:
        st.markdown("### 📜 The Legend")
        st.write("""
        For centuries, the ancient servers were peaceful. But recently, a dark force known as the **Spaghetti Code** has corrupted the lands. 
        Bugs, infinite loops, and unhandled exceptions roam freely.
        
        The guild is looking for a new hero. Will you take up the keyboard and cleanse the realm?
        """)
        
        st.markdown("### 🧙‍♂️ Choose Your Path")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown("<div class='avatar-large'>🧙‍♂️</div><br><center><b>Code Wizard</b></center>", unsafe_allow_html=True)
        c2.markdown("<div class='avatar-large'>🥷</div><br><center><b>Cyber Ninja</b></center>", unsafe_allow_html=True)
        c3.markdown("<div class='avatar-large'>🧝‍♀️</div><br><center><b>Data Elf</b></center>", unsafe_allow_html=True)
        c4.markdown("<div class='avatar-large'>👨‍💻</div><br><center><b>Tech Knight</b></center>", unsafe_allow_html=True)

    with col_auth:
        with st.container(border=True):
            st.subheader("🛡️ Guild Portal")
            mode = st.radio("Select Action:", ["Login", "Create Account"], horizontal=True)
            user = st.text_input("Hero Name (Username)")
            pwd = st.text_input("Secret Spell (Password)", type="password")
            
            if mode == "Create Account": 
                chosen_class = st.selectbox("Select Class:", list(AVATARS.keys()))
            
            if st.button("🚀 ENTER REALM", type="primary", width="stretch"):
                conn = sqlite3.connect('rpg_world.db')
                c = conn.cursor()
                if mode == "Create Account":
                    s_f, s_b = os.urandom(8).hex(), os.urandom(8).hex()
                    h = get_hash(pwd, s_f, s_b)
                    prog = json.dumps({k: False for k in TASKS.keys()})
                    try:
                        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)", (user, h, s_f, s_b, prog, user, AVATARS[chosen_class], "Dracula"))
                        conn.commit()
                        st.success("✨ Hero registered! Switch to Login to enter.")
                    except: st.error("❌ Name already taken by another hero!")
                else:
                    c.execute("SELECT password_hash, salt_front, salt_back, progress, display_name, avatar, theme FROM users WHERE username=?", (user,))
                    res = c.fetchone()
                    if res and get_hash(pwd, res[1], res[2]) == res[0]:
                        st.session_state.username = user
                        st.session_state.skills = json.loads(res[3])
                        st.session_state.display_name = res[4]
                        st.session_state.avatar = res[5]
                        st.session_state.theme = res[6]
                        st.session_state.battle_log = "> IDE Initialized...\n"
                        st.rerun()
                    else: st.error("❌ Invalid spell or hero name!")
                conn.close()

# --- 5. MAIN INTERFACE (ONLY IF LOGGED IN) ---
if 'username' in st.session_state:
    apply_theme(st.session_state.theme)
    
    # --- САЙДБАР ТЕПЕРЬ ПОКАЗЫВАЕТСЯ ТОЛЬКО ПОСЛЕ ЛОГИНА ---
    with st.sidebar:
        st.markdown(f"<div class='avatar-large'>{st.session_state.avatar}</div>", unsafe_allow_html=True)
        new_name = st.text_input("Name:", value=st.session_state.display_name, label_visibility="collapsed")
        new_av = st.selectbox("Class:", list(AVATARS.values()), index=list(AVATARS.values()).index(st.session_state.avatar), label_visibility="collapsed")
        new_theme = st.selectbox("Editor Theme:", list(THEMES.keys()), index=list(THEMES.keys()).index(st.session_state.theme))
        
        if new_name != st.session_state.display_name or new_av != st.session_state.avatar or new_theme != st.session_state.theme:
            st.session_state.display_name = new_name
            st.session_state.avatar = new_av
            st.session_state.theme = new_theme
            update_profile(st.session_state.username, new_name, new_av, new_theme)
            st.rerun()

        xp = sum(st.session_state.skills.values())
        lvl = (xp // 2) + 1
        
        st.divider()
        st.markdown(f"**🌟 Level:** {lvl} | **🏅 Rank:** {TITLES.get(lvl, 'Server Legend 👑')}")
        st.progress(xp / len(TASKS))
        
        st.divider()
        st.markdown("### 🎒 Inventory")
        loot = [TASKS[k]["loot"] for k, v in st.session_state.skills.items() if v]
        if loot:
            for item in loot: st.caption(item)
        else: st.caption("Empty... Defeat monsters!")
            
        st.divider()
        if st.button("🚪 Logout", width="stretch"):
            st.session_state.clear()
            st.rerun()
            
    # --- ТАБЫ (Город, Арена, Ментор) ОСТАЮТСЯ КАК БЫЛИ ---
    t_town, t_lab, t_mentor = st.tabs(["📁 File Explorer (Town)", "💻 Code Editor (Arena)", "🦆 Copilot Mentor"])
    
    # ... ДАЛЬШЕ ИДЕТ ТВОЙ СТАРЫЙ КОД (with t_town: и т.д.) ...
    # === TOWN (FILE EXPLORER STYLE) ===
    with t_town:
        st.title(f"WORKSPACE: {st.session_state.display_name.upper()}")
        
        col_skills, col_radar = st.columns([1, 1])
        
        with col_skills:
            st.markdown("📂 **src/python_mastery/**")
            for skill, done in st.session_state.skills.items():
                c_class = "skill-card" if done else "skill-card skill-locked"
                icon = "🐍" if done else "🔒"
                file_name = f"{skill.lower().replace(' ', '_')}.py"
                st.markdown(f"<div class='{c_class}'>{icon} {file_name}</div>", unsafe_allow_html=True)
                
        with col_radar:
            st.subheader("🕸️ Analytics Radar")
            cat_scores = {"Syntax": 0, "Logic": 0, "Architecture": 0, "Tools": 0, "Database": 0}
            cat_max = {"Syntax": 2, "Logic": 2, "Architecture": 3, "Tools": 3, "Database": 1}
            for k, v in st.session_state.skills.items():
                if v: cat_scores[TASKS[k]["category"]] += 1
                
            df = pd.DataFrame(dict(r=[cat_scores[k] / cat_max[k] * 100 for k in cat_scores.keys()], theta=list(cat_scores.keys())))
            fig = px.line_polar(df, r='r', theta='theta', line_close=True, range_r=[0, 100], template="plotly_dark")
            fig.update_traces(fill='toself', line_color=THEMES[st.session_state.theme]['accent'])
            st.plotly_chart(fig, width="stretch")

    # === LABORATORY (WITH ACE EDITOR) ===
    with t_lab:
        st.title("💻 Development Arena")
        undone = [k for k, v in st.session_state.skills.items() if not v]
        
        if not undone:
            st.balloons()
            st.success("🎉 EPIC VICTORY! Main quest completed. Welcome to the Endgame.")
            
            # --- ENDLESS MODE: INFINITE TOWER ---
            st.markdown("## 🏰 The Infinite Tower")
            
            if 'tower_lvl' not in st.session_state: 
                st.session_state.tower_lvl = 1
                
            if 'tower_a' not in st.session_state:
                st.session_state.tower_a = random.randint(10, 500)
                st.session_state.tower_b = random.randint(10, 500)
                
            st.info(f"**Floor {st.session_state.tower_lvl}:** Create a variable `ans` equal to {st.session_state.tower_a} + {st.session_state.tower_b}")
            
            col_tower, col_term = st.columns([2, 1])
            with col_tower:
                tower_code = st_ace(language='python', theme=THEMES[st.session_state.theme]['ace'], height=200, key=f"tower_{st.session_state.tower_lvl}")
                if st.button("⚔️ STRIKE (Tower)"):
                    local_env = {}
                    try:
                        exec(tower_code, {}, local_env)
                        if local_env.get('ans') == (st.session_state.tower_a + st.session_state.tower_b):
                            play_sound("door.mp3")
                            st.success("Floor cleared!")
                            st.session_state.tower_lvl += 1
                            del st.session_state['tower_a']
                            st.rerun()
                        else:
                            play_sound("bonk.mp3")
                            st.error("Wrong logic. The floor guardian deflected your attack!")
                    except Exception as e:
                        play_sound("bonk.mp3")
                        st.error(f"Error: {e}")
            
            with col_term:
                st.markdown("### 🎓 Archmage Reward")
                pdf_bytes = create_pdf(st.session_state.display_name)
                st.download_button("📜 DOWNLOAD DIPLOMA", data=pdf_bytes, file_name=f"diploma.pdf", mime='application/octet-stream')
        else:
            col_info, col_code = st.columns([1, 2])
            
            with col_info:
                target = st.selectbox("Select Target Bug/Monster:", undone)
                idx = list(TASKS.keys()).index(target)
                st.markdown(f"<div class='monster-box'><h3>{MONSTERS[idx]}</h3></div>", unsafe_allow_html=True)
                st.info(f"**Task:** {TASKS[target]['task']}")
                
            with col_code:
                st.markdown(f"**Editing: {target.lower()}.py**")
                code = st_ace(
                    language='python',
                    theme=THEMES[st.session_state.theme]['ace'],
                    height=250,
                    font_size=14,
                    show_gutter=True,
                    auto_update=True
                )
                
                if st.button("▶️ COMPILE & ATTACK", type="primary", width="stretch"):
                    old_stdout = sys.stdout
                    new_stdout = io.StringIO()
                    sys.stdout = new_stdout
                    
                    local_env = {'os': os, 'st': st}
                    error_msg = None
                    try: exec(code, {}, local_env)
                    except Exception as e: error_msg = str(e)
                        
                    sys.stdout = old_stdout
                    terminal_output = new_stdout.getvalue()
                    
                    if not error_msg:
                        try: success = eval(TASKS[target]['check'], {}, local_env)
                        except: success = False
                    else: success = False

                    log_entry = f"\n[{time.strftime('%H:%M:%S')}] Executing script..."
                    if terminal_output: log_entry += f"\nstdout> {terminal_output.strip()}"
                        
                    if success:
                        play_sound("door.mp3") 
                        st.session_state.skills[target] = True
                        log_entry += f"\n✅ BUILD PASS: {target} resolved! Loot: {TASKS[target]['loot']}."
                        conn = sqlite3.connect('rpg_world.db')
                        c = conn.cursor()
                        c.execute("UPDATE users SET progress=? WHERE username=?", (json.dumps(st.session_state.skills), st.session_state.username))
                        conn.commit()
                        conn.close()
                    elif error_msg:
                        play_sound("bonk.mp3") 
                        log_entry += f"\n💥 RUNTIME ERROR: {error_msg}"
                    else:
                        play_sound("bonk.mp3") 
                        log_entry += f"\n❌ ASSERTION FAILED: Logic incorrect."
                        
                    st.session_state.battle_log = log_entry + "\n" + st.session_state.battle_log

            st.markdown("### 📜 Terminal Output")
            st.markdown(f"<div class='term-log'>{st.session_state.battle_log}</div>", unsafe_allow_html=True)

    # === MENTOR (GITHUB COPILOT STYLE) ===
    with t_mentor:
        st.title("🦆 Copilot Duck")
        
        # --- FIX: Инициализация чата перенесена сюда ---
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = [
                {"role": "assistant", "content": "Quack! I am your AI Copilot. Need help with your code or the tower Floors?"}
            ]
            
        # Отрисовка всех сообщений
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): 
                st.write(msg["content"])
                
        # Ввод пользователя
        if prompt := st.chat_input("Ask Copilot Duck..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)
            
            # --- REAL AI INTEGRATION (OPENROUTER FIX) ---
            try:
                client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key="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" 
                ) 
                
                messages = [{"role": "system", "content": "You are a wise coding mentor duck named Copilot Duck. You help with Python. Start answers with 'Quack!'. Do NOT give the exact code solution, but give a strong hint to help the user learn. Keep it short."}]
                
                for m in st.session_state.chat_history:
                    messages.append(m)
                    
                response = client.chat.completions.create(
                    model="google/gemma-7b-it:free",
                    messages=messages,
                    max_tokens=150
                )
                reply = response.choices[0].message.content
                
            except Exception as e:
                reply = f"Quack! API Error: {e}"
            
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            with st.chat_message("assistant"): st.write(reply)