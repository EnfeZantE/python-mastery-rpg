from dis import code_info

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

# --- НОВАЯ СИСТЕМА РАНГОВ ---
# --- НОВАЯ СИСТЕМА РАНГОВ (ENGLISH) ---
def get_rank_display(xp, position=None):
    if xp < 500: return "🌱 Recruit"
    elif xp < 1000: return "🛡️ Guardian"
    elif xp < 2000: return "⚔️ Knight"
    elif xp < 3500: return "⚡ Hero"
    elif xp < 5000: return "🌟 Legend"
    elif xp < 7000: return "💜 Overlord"
    elif xp < 10000: return "🕊️ Divine"
    else:
        if position == 1: return "👑 Titan (Top-1)"
        elif position and position <= 10: return f"🔥 Titan (Top-{position})"
        elif position and position <= 100: return f"⚡ Titan (Top-{position})"
        return "⚔️ Titan"

# --- ОБНОВЛЕННАЯ БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('rpg_world.db')
    c = conn.cursor()
    # Добавляем total_xp, weekly_xp и achievements
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password_hash TEXT, salt_front TEXT, salt_back TEXT, 
                 progress TEXT, display_name TEXT, avatar TEXT, theme TEXT, 
                 total_xp INTEGER, weekly_xp INTEGER, achievements TEXT, join_date REAL)''')
    conn.commit()
    conn.close()

# --- 1. SETTINGS & THEME ENGINE ---
st.set_page_config(page_title="Hilda's Epic IT-RPG", page_icon="⚔️", layout="wide")

# VS Code Theme Palettes
# VS Code Theme Palettes
THEMES = {
    "Dracula": {"bg": "#282a36", "sidebar": "#21222c", "text": "#f8f8f2", "accent": "#bd93f9", "ace": "dracula"},
    "Monokai": {"bg": "#272822", "sidebar": "#1e1f1c", "text": "#f8f8f2", "accent": "#ae81ff", "ace": "monokai"},
    "One Dark": {"bg": "#282c34", "sidebar": "#21252b", "text": "#abb2bf", "accent": "#61afef", "ace": "tomorrow_night"},
    "SynthWave 84": {"bg": "#2b213a", "sidebar": "#241b30", "text": "#ffffff", "accent": "#f92aad", "ace": "chaos"},
    "Matrix Hacker": {"bg": "#0d1117", "sidebar": "#000000", "text": "#00ff00", "accent": "#00ff00", "ace": "terminal"} # НОВАЯ ТЕМА ИЗ МАГАЗИНА
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
        
        /* УСИЛЕННЫЙ СТИЛЬ ДЛЯ ТЕКСТОВЫХ ПОЛЕЙ (ИСПРАВЛЕНО) */
        .stTextInput > div > div[data-baseweb="base-input"] {{
            background-color: {t['sidebar']} !important;
            border: 2px solid #555 !important;
            border-radius: 8px !important;
            transition: 0.3s !important;
            overflow: hidden !important;
        }}
        
        .stTextInput > div > div[data-baseweb="base-input"]:focus-within {{
            border-color: {t['accent']} !important;
            box-shadow: 0 0 10px {t['accent']} !important;
        }}
        
        /* Убираем рамку с внутреннего инпута, чтобы не было хвостиков */
        .stTextInput div[data-baseweb="input"] {{
            background-color: transparent !important;
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
    # 1. Базовая таблица
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password_hash TEXT, salt_front TEXT, salt_back TEXT, 
                 progress TEXT, display_name TEXT, avatar TEXT, theme TEXT)''')
    
    # 2. МИГРАЦИЯ: Добавляем колонки для Магазина и Дейликов (если их еще нет)
    # 2. МИГРАЦИЯ БД
    new_columns = {
        "total_xp": "INTEGER DEFAULT 0",
        "gold": "INTEGER DEFAULT 0",
        "daily_quest_date": "TEXT DEFAULT ''",
        "daily_quest_count": "INTEGER DEFAULT 0",
        "unlocked_themes": "TEXT DEFAULT '[]'",
        "achievements": "TEXT DEFAULT '[]'",
        "join_date": "REAL DEFAULT 0.0",
        "unlocked_avatars": "TEXT DEFAULT '[]'",   # НОВАЯ КОЛОНКА ДЛЯ ЭМОДЗИ
        "gold_history": "TEXT DEFAULT '[0]'"       # НОВАЯ КОЛОНКА ДЛЯ ГРАФИКА
    }
    
    for col_name, col_type in new_columns.items():
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass # Если колонка уже есть, просто идем дальше
            
    conn.commit()
    conn.close()

init_db() # Запускаем создание/обновление базы при старте

# --- ТВОИ ХЕЛПЕРЫ (ОСТАВЛЯЕМ КАК БЫЛИ) ---
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

def create_social_card(name, avatar, xp, rank):
    from PIL import Image, ImageDraw, ImageFont
    import io
    
    # 1. Возвращаем компактный и аккуратный размер 600x300
    img = Image.new('RGB', (600, 320), color='#1e1e2e')
    draw = ImageDraw.Draw(img)
    
    # 2. Рисуем двойную неоновую рамку
    draw.rectangle([10, 10, 590, 310], outline='#bd93f9', width=4)
    draw.rectangle([18, 18, 582, 302], outline='#ff79c6', width=1)
    
    # 3. УМНЫЙ ПОИСК ШРИФТОВ (чтобы текст не был мелким)
    def get_font(size):
        # Ищем стандартные шрифты Windows, macOS и Linux
        fonts = ["Arial.ttf", "arial.ttf", "Helvetica.ttc", "DejaVuSans.ttf", "Verdana.ttf"]
        for f in fonts:
            try: return ImageFont.truetype(f, size)
            except: pass
        return ImageFont.load_default() # На крайний случай
        
    font_title = get_font(28)
    font_name = get_font(45)
    font_stats = get_font(22)
    
    # 4. ОЧИСТКА ОТ ЭМОДЗИ (чтобы не было перечеркнутых квадратиков!)
    # Берем всё, кроме первого символа-эмодзи
    clean_name = name.upper()
    clean_avatar = " ".join(avatar.split(' ')[1:]) if ' ' in avatar else avatar
    clean_rank = " ".join(rank.split(' ')[1:]) if ' ' in rank else rank
    
    # 5. Отрисовка чистого текста
    draw.text((30, 30), "PYTHON MASTERY RPG", fill="#8be9fd", font=font_title)
    draw.text((30, 80), f"HERO: {clean_name}", fill="#f8f8f2", font=font_name)
    
    # Декоративная линия
    draw.line([(30, 145), (570, 145)], fill="#44475a", width=3)
    
    draw.text((30, 170), f"CLASS:  {clean_avatar.upper()}", fill="#ffb86c", font=font_stats)
    draw.text((30, 210), f"RANK:   {clean_rank.upper()}", fill="#50fa7b", font=font_stats)
    draw.text((30, 250), f"TOTAL:  {xp} XP", fill="#bd93f9", font=font_stats)
    
    # Сохраняем
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

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
if 'username' not in st.session_state:
    # Инициализируем тему для страницы логина, если её еще нет
    if 'login_theme' not in st.session_state:
        st.session_state.login_theme = "Dracula"
        
    # Применяем выбранную тему ко всему экрану
    apply_theme(st.session_state.login_theme)
    
    # ЭПИЧНЫЙ ЭКРАН ВХОДА
    st.markdown("<h1 style='text-align: center; font-size: 3em;'>⚔️ Python Mastery RPG</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.2em; color: #888;'>Enter the realm of Code Town, defeat the Syntax Monsters, and become an Archmage.</p>", unsafe_allow_html=True)
    st.write("")
    st.write("")
    
    col_lore, col_auth = st.columns([1.5, 1])
    
    with col_lore:
        st.markdown("### 📜 The Legend")
        
        st.markdown("""
        <div style="background-color: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 10px; border-left: 4px solid #bd93f9; margin-bottom: 25px;">
            For centuries, the ancient servers were peaceful. But recently, a dark force known as the <b>Spaghetti Code</b> has corrupted the lands. 
            Bugs, infinite loops, and unhandled exceptions roam freely.<br><br>
            <i>The guild is looking for a new hero. Will you take up the keyboard and cleanse the realm?</i>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 🧙‍♂️ Choose Your Path")
        
        st.markdown("""
        <div style="display: flex; justify-content: space-between; text-align: center; gap: 15px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 110px; background-color: rgba(0,0,0,0.3); padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);">
                <div style="font-size: 55px; margin-bottom: 10px; line-height: 1;">🧙‍♂️</div>
                <b style="font-size: 14px;">Code Wizard</b>
            </div>
            <div style="flex: 1; min-width: 110px; background-color: rgba(0,0,0,0.3); padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);">
                <div style="font-size: 55px; margin-bottom: 10px; line-height: 1;">🥷</div>
                <b style="font-size: 14px;">Cyber Ninja</b>
            </div>
            <div style="flex: 1; min-width: 110px; background-color: rgba(0,0,0,0.3); padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);">
                <div style="font-size: 55px; margin-bottom: 10px; line-height: 1;">🧝‍♀️</div>
                <b style="font-size: 14px;">Data Elf</b>
            </div>
            <div style="flex: 1; min-width: 110px; background-color: rgba(0,0,0,0.3); padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);">
                <div style="font-size: 55px; margin-bottom: 10px; line-height: 1;">👨‍💻</div>
                <b style="font-size: 14px;">Tech Knight</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # --- ВОТ СЮДА ВСТАВЛЯЕМ ТЕМЫ ---
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 🎨 Realms of Magic (Themes)")
        st.markdown("""
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
            <div style="flex: 1; background: #282a36; border-left: 4px solid #bd93f9; padding: 10px; border-radius: 5px; text-align: center;"><span style="color: #f8f8f2; font-size: 13px;">🧛‍♂️ Dracula</span></div>
            <div style="flex: 1; background: #272822; border-left: 4px solid #ae81ff; padding: 10px; border-radius: 5px; text-align: center;"><span style="color: #f8f8f2; font-size: 13px;">🐍 Monokai</span></div>
            <div style="flex: 1; background: #282c34; border-left: 4px solid #61afef; padding: 10px; border-radius: 5px; text-align: center;"><span style="color: #abb2bf; font-size: 13px;">🌑 One Dark</span></div>
            <div style="flex: 1; background: #2b213a; border-left: 4px solid #f92aad; padding: 10px; border-radius: 5px; text-align: center;"><span style="color: #ffffff; font-size: 13px;">🌆 SynthWave</span></div>
        </div>
        <p style="font-size: 0.9em; color: #888; margin-top: 10px;"><i>Unlock more premium themes like Matrix Hacker in the Magic Shop!</i></p>
        """, unsafe_allow_html=True)
        # --- КОНЕЦ БЛОКА COL_LORE ---

    # Дальше у тебя идет with col_auth: ...

    with col_auth:
        st.markdown("<div style='margin-top: 55px;'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.subheader("🛡️ Guild Portal")
            
            new_theme = st.selectbox("🎨 Portal Theme:", list(THEMES.keys()), index=list(THEMES.keys()).index(st.session_state.login_theme))
            if new_theme != st.session_state.login_theme:
                st.session_state.login_theme = new_theme
                st.rerun()
            
            # ЗАМЕНИЛИ st.divider() НА КОМПАКТНУЮ ЛИНИЮ
            st.markdown("<hr style='margin: 10px 0; border-color: #555;'>", unsafe_allow_html=True) 
            
            mode = st.radio("Select Action:", ["Login", "Create Account"], horizontal=True)
            user = st.text_input("Hero Name (Username)")
            pwd = st.text_input("Secret Spell (Password)", type="password")
            
            # Если создаем аккаунт, показываем выбор класса
            if mode == "Create Account": 
                chosen_class = st.selectbox("Select Class:", list(AVATARS.keys()))
            else:
                st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True) # Небольшой отступ, чтобы кнопка не прилипала
            
            # ... ДАЛЬШЕ ИДЕТ КНОПКА st.button("🚀 ENTER REALM" ...
            
            if st.button("🚀 ENTER REALM", type="primary", width="stretch"):
                conn = sqlite3.connect('rpg_world.db')
                c = conn.cursor()
                if mode == "Create Account":
                    s_f, s_b = os.urandom(8).hex(), os.urandom(8).hex()
                    h = get_hash(pwd, s_f, s_b)
                    prog = json.dumps({k: False for k in TASKS.keys()})
                    try:
                        c.execute("""INSERT INTO users 
                                  (username, password_hash, salt_front, salt_back, progress, display_name, avatar, theme, join_date) 
                                  VALUES (?,?,?,?,?,?,?,?,?)""", 
                                 (user, h, s_f, s_b, prog, user, AVATARS[chosen_class], st.session_state.login_theme, time.time()))
                        conn.commit()
                        st.success("✨ Hero registered! Please login now.")
                    except sqlite3.IntegrityError: 
                        st.error("❌ Name taken!")
                    except Exception as e:
                        st.error(f"❌ DB Error: {e}")
                else:
                    # --- ИСПРАВЛЕННЫЙ "УМНЫЙ" ЛОГИН ---
                    c.execute("SELECT * FROM users WHERE username=?", (user,))
                    res = c.fetchone()
                    
                    if res:
                        # Достаем названия всех колонок из базы
                        columns = [desc[0] for desc in c.description]
                        # Собираем красивый словарь {колонка: значение}
                        user_data = dict(zip(columns, res))
                        
                        if get_hash(pwd, user_data['salt_front'], user_data['salt_back']) == user_data['password_hash']:
                            st.session_state.username = user
                            st.session_state.display_name = user_data['display_name']
                            st.session_state.avatar = user_data['avatar']
                            st.session_state.theme = user_data['theme']
                            
                            st.session_state.skills = json.loads(user_data['progress'])
                            st.session_state.total_xp = user_data.get('total_xp', 0)
                            st.session_state.gold = user_data.get('gold', 0)
                            
                            # Безопасная загрузка списков (инвентарь, темы, аватарки, график)
                            st.session_state.achievements = json.loads(user_data.get('achievements', '[]'))
                            st.session_state.unlocked_themes = json.loads(user_data.get('unlocked_themes', '[]'))
                            st.session_state.unlocked_avatars = json.loads(user_data.get('unlocked_avatars', '[]'))
                            st.session_state.gold_history = json.loads(user_data.get('gold_history', '[0]'))
                            
                            # Дейлики
                            today = time.strftime("%Y-%m-%d")
                            db_date = user_data.get('daily_quest_date', '')
                            if db_date != today and db_date != "":
                                st.session_state.daily_quest_count = 0 
                                st.session_state.daily_quest_date = ""
                            else:
                                st.session_state.daily_quest_date = db_date
                                st.session_state.daily_quest_count = user_data.get('daily_quest_count', 0)
                            
                            st.session_state.battle_log = "> IDE Initialized...\n"
                            st.rerun()
                        else: st.error("❌ Invalid spell!")
                    else: st.error("❌ Hero not found!")
                conn.close()

# --- 5. MAIN INTERFACE (ONLY IF LOGGED IN) ---
if 'username' in st.session_state:
    apply_theme(st.session_state.theme)
    
    # --- САЙДБАР ТЕПЕРЬ ПОКАЗЫВАЕТСЯ ТОЛЬКО ПОСЛЕ ЛОГИНА ---
    # --- САЙДБАР (ПРОФИЛЬ, РАНГИ, ИНВЕНТАРЬ) ---
    with st.sidebar:
        # 1. Высчитываем позицию для ранга Титан
        conn = sqlite3.connect('rpg_world.db')
        df_rank = pd.read_sql_query("SELECT username, total_xp FROM users ORDER BY total_xp DESC", conn)
        conn.close()
        try: pos = df_rank[df_rank['username'] == st.session_state.username].index[0] + 1
        except: pos = None
        
        # Получаем красивую строку ранга (например, [🌟 Легенда])
        current_rank = get_rank_display(st.session_state.total_xp, pos)
        
        # 2. Отображение аватара и ранга
        # 2. Отображение аватара (только эмодзи) и ранга
        # .split(' ')[0] берет только первый элемент до пробела (то есть сам эмодзи)
        emoji_only = st.session_state.avatar.split(' ')[0]
        st.markdown(f"<div class='avatar-large'>{emoji_only}</div>", unsafe_allow_html=True)
        # --- НОВЫЙ БЛОК: ПРЕВЬЮ ТЕМ ---
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"<h3 style='text-align:center;'>{current_rank}</h3>", unsafe_allow_html=True)
        
        # 3. Настройки профиля (ТВОЯ ЛОГИКА - ОСТАВЛЕНА КАК БЫЛО)
        # --- 3. Настройки профиля (С УЧЕТОМ ПОКУПОК ИЗ МАГАЗИНА) ---
        base_themes = ["Dracula", "Monokai", "One Dark", "SynthWave 84"]
        available_themes = base_themes + st.session_state.unlocked_themes
        available_avatars = list(AVATARS.values()) + st.session_state.unlocked_avatars
        
        # Страховка от ошибки индекса
        if st.session_state.theme not in available_themes: available_themes.append(st.session_state.theme)
        if st.session_state.avatar not in available_avatars: available_avatars.append(st.session_state.avatar)

        new_name = st.text_input("Name:", value=st.session_state.display_name, label_visibility="collapsed")
        new_av = st.selectbox("Class:", available_avatars, index=available_avatars.index(st.session_state.avatar), label_visibility="collapsed")
        new_theme = st.selectbox("Editor Theme:", available_themes, index=available_themes.index(st.session_state.theme))
        
        if new_name != st.session_state.display_name or new_av != st.session_state.avatar or new_theme != st.session_state.theme:
            st.session_state.display_name = new_name
            st.session_state.avatar = new_av
            st.session_state.theme = new_theme
            update_profile(st.session_state.username, new_name, new_av, new_theme)
            st.rerun()

        # 4. Прогресс-бар нового бесконечного опыта
        st.divider()
        st.markdown(f"**🌟 Total XP:** {st.session_state.total_xp}")
        # Шкала заполняется до 10000 (ранг Титан), потом всегда полная
        st.progress(min(st.session_state.total_xp / 10000, 1.0)) 
        
        # 5. Новый скрытый инвентарь и ачивки
        st.divider()
        with st.expander("📦 Inventory & Achievements"):
            st.write("**🏆 Trophies:**")
            if st.session_state.total_xp >= 100: st.caption("🩸 First Blood")
            if st.session_state.total_xp >= 1000: st.caption("💠 Elite-Coder")
            if len(st.session_state.achievements) > 0:
                for a in st.session_state.achievements: st.caption(f"⭐ {a}")
            
            st.write("**🎒 Items:**")
            loot = [TASKS[k]["loot"] for k, v in st.session_state.skills.items() if v]
            if loot:
                for item in loot: st.caption(item)
            else: st.caption("Empty... Defeat monsters!")
            
        # 6. Твоя кнопка Logout
        st.divider()
        if st.button("🚪 Logout", width="stretch"):
            st.session_state.clear()
            st.rerun()
            
    # --- ТАБЫ (Город, Арена, Ментор) ОСТАЮТСЯ КАК БЫЛИ ---
    # Добавили 4-й таб: 🏆 Hall of Fame
    t_town, t_lab, t_mentor, t_leader = st.tabs(["📁 File Explorer (Town)", "💻 Code Editor (Arena)", "🦆 Copilot Mentor", "🏆 Hall of Fame"])
    # ... ДАЛЬШЕ ИДЕТ ТВОЙ СТАРЫЙ КОД (with t_town: и т.д.) ...
    # === TOWN (FILE EXPLORER STYLE) ===
    # === FILE EXPLORER & TOWN (WORKSPACE) ===
    # === FILE EXPLORER & TOWN (WORKSPACE) ===
    with t_town:
        st.title(f"WORKSPACE: {st.session_state.display_name.upper()}")
        
        # --- НОВЫЙ ВЕРХНИЙ БЛОК (Магазин, Дейлики, График) ---
        col_shop, col_daily, col_graph = st.columns([1.5, 1, 1.5])
        
        with col_shop:
            st.markdown("### 🏪 Magic Shop")
            st.markdown(f"**Balance: {st.session_state.get('gold', 0)} 💰**")
            
            # Предмет 1: Премиум Тема
            if "Matrix Hacker" not in st.session_state.unlocked_themes:
                if st.button("🎨 Theme: Matrix Hacker (500 💰)", use_container_width=True):
                    if st.session_state.gold >= 500:
                        st.session_state.gold -= 500
                        st.session_state.unlocked_themes.append("Matrix Hacker")
                        st.session_state.gold_history.append(st.session_state.gold)
                        conn = sqlite3.connect('rpg_world.db'); c = conn.cursor()
                        c.execute("UPDATE users SET gold=?, unlocked_themes=?, gold_history=? WHERE username=?", 
                                 (st.session_state.gold, json.dumps(st.session_state.unlocked_themes), json.dumps(st.session_state.gold_history), st.session_state.username))
                        conn.commit(); conn.close(); st.rerun()
                    else: st.error("Not enough gold!")
            else: st.success("🎨 Theme: Matrix Hacker (Purchased)")
            
            # Предмет 2: Премиум Аватар
            if "🐉 Data Dragon" not in st.session_state.unlocked_avatars:
                if st.button("🐉 Avatar: Data Dragon (300 💰)", use_container_width=True):
                    if st.session_state.gold >= 300:
                        st.session_state.gold -= 300
                        st.session_state.unlocked_avatars.append("🐉 Data Dragon")
                        st.session_state.gold_history.append(st.session_state.gold)
                        conn = sqlite3.connect('rpg_world.db'); c = conn.cursor()
                        c.execute("UPDATE users SET gold=?, unlocked_avatars=?, gold_history=? WHERE username=?", 
                                 (st.session_state.gold, json.dumps(st.session_state.unlocked_avatars), json.dumps(st.session_state.gold_history), st.session_state.username))
                        conn.commit(); conn.close(); st.rerun()
                    else: st.error("Not enough gold!")
            else: st.success("🐉 Avatar: Data Dragon (Purchased)")

        with col_daily:
            st.markdown("### 📅 Daily Quest")
            today = time.strftime("%Y-%m-%d")
            if st.session_state.get('daily_quest_date') == today:
                st.success("✅ Quest Completed!")
                st.caption("Come back tomorrow.")
            else:
                count = st.session_state.get('daily_quest_count', 0)
                st.write(f"**Task:** Defeat 3 monsters.")
                st.write(f"**Progress:** {count} / 3")
                st.progress(min(count / 3, 1.0))
                if count >= 3:
                    if st.button("🎁 CLAIM REWARD"):
                        st.session_state.gold += 200
                        st.session_state.total_xp += 150
                        st.session_state.gold_history.append(st.session_state.gold)
                        st.session_state.daily_quest_date = today
                        st.balloons()
                        conn = sqlite3.connect('rpg_world.db'); c = conn.cursor()
                        c.execute("UPDATE users SET gold=?, total_xp=?, daily_quest_date=?, gold_history=? WHERE username=?", 
                                 (st.session_state.gold, st.session_state.total_xp, st.session_state.daily_quest_date, json.dumps(st.session_state.gold_history), st.session_state.username))
                        conn.commit(); conn.close(); st.rerun()

        with col_graph:
            st.markdown("### 📈 Wealth Tracker")
            if len(st.session_state.gold_history) > 1:
                df_gold = pd.DataFrame({"Gold": st.session_state.gold_history})
                st.line_chart(df_gold, use_container_width=True, color="#bd93f9")
            else:
                st.info("Earn or spend gold to unlock your economy chart!")

        st.divider()

        # --- ТВОЙ СТАРЫЙ БЛОК АНАЛИТИКИ И ФАЙЛОВ ВНИЗУ ---
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
    # === LABORATORY (WITH ACE EDITOR) ===
    with t_lab:
        st.title("💻 Development Arena")
        undone = [k for k, v in st.session_state.skills.items() if not v]
        
        if not undone:
            if 'victory_celebrated' not in st.session_state:
                st.balloons()
                st.session_state.victory_celebrated = True
                
            st.success("🎉 EPIC VICTORY! Main quest completed. Welcome to the Endgame.")
            
            st.markdown("## 🏰 The Infinite Tower")
            
            if 'tower_lvl' not in st.session_state: st.session_state.tower_lvl = 1
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
                            st.success("Floor cleared! +50 XP 🌟")
                            st.session_state.tower_lvl += 1
                            
                            # --- ФАРМ В БАШНЕ: Опыт, Золото, Дейлик и График ---
                            st.session_state.total_xp += 50
                            st.session_state.gold = st.session_state.get('gold', 0) + 25
                            st.session_state.daily_quest_count = st.session_state.get('daily_quest_count', 0) + 1
                            st.session_state.gold_history.append(st.session_state.gold)
                            
                            conn = sqlite3.connect('rpg_world.db')
                            c = conn.cursor()
                            c.execute("UPDATE users SET total_xp=?, gold=?, daily_quest_count=?, gold_history=? WHERE username=?", 
                                     (st.session_state.total_xp, st.session_state.gold, st.session_state.daily_quest_count, json.dumps(st.session_state.gold_history), st.session_state.username))
                            conn.commit()
                            conn.close()
                            
                            del st.session_state['tower_a']
                            st.rerun()
                        else:
                            play_sound("bonk.mp3")
                            st.error("Wrong logic. The floor guardian deflected your attack!")
                    except Exception as e:
                        play_sound("bonk.mp3")
                        st.error(f"Error: {e}")
            
            with col_term:
                st.markdown("### 📸 Share Your Glory")
                
                # Считаем ранг правильно
                conn = sqlite3.connect('rpg_world.db')
                df_r = pd.read_sql_query("SELECT username, total_xp FROM users ORDER BY total_xp DESC", conn)
                conn.close()
                try: pos = df_r[df_r['username'] == st.session_state.username].index[0] + 1
                except: pos = None
                
                # Получаем ПОЛНУЮ строку ранга, например "🌟 Legend"
                full_rank = get_rank_display(st.session_state.total_xp, pos)
                
                img_bytes = create_social_card(
                    st.session_state.display_name, 
                    st.session_state.avatar, 
                    st.session_state.total_xp, 
                    full_rank
                )
                
                st.download_button(
                    label="🔗 DOWNLOAD EPIC CARD",
                    data=img_bytes,
                    file_name=f"HeroCard_{st.session_state.username}.png",
                    mime="image/png",
                    use_container_width=True
                )
        else:
            # ВОТ ЭТА СТРОЧКА СОЗДАЕТ КОЛОНКИ (Без нее IDE будет выдавать ошибку!)
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
                    auto_update=True,
                    key=f"editor_{target}" # Тот самый фикс залипания
                )
                
                # Дальше идет твоя кнопка атаки
                if st.button("▶️ COMPILE & ATTACK", type="primary", width="stretch"):
                
                    old_stdout = sys.stdout
                    new_stdout = io.StringIO()
                    sys.stdout = new_stdout
                    
                    local_env = {'os': os, 'st': st}
                    error_msg = None
                    
                    if 'fail_count' not in st.session_state:
                        st.session_state.fail_count = 0

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
                        st.session_state.fail_count = 0 
                        play_sound("door.mp3") 
                        st.session_state.skills[target] = True
                        log_entry += f"\n✅ BUILD PASS: {target} resolved! Loot: {TASKS[target]['loot']}."
                        
                        # --- СЮЖЕТНЫЙ БОСС: Опыт, Золото, Дейлик и График ---
                        st.session_state.total_xp += 100
                        st.session_state.gold = st.session_state.get('gold', 0) + 50
                        st.session_state.daily_quest_count = st.session_state.get('daily_quest_count', 0) + 1
                        st.session_state.gold_history.append(st.session_state.gold)
                        
                        conn = sqlite3.connect('rpg_world.db')
                        c = conn.cursor()
                        c.execute("UPDATE users SET progress=?, total_xp=?, gold=?, daily_quest_count=?, gold_history=? WHERE username=?", 
                                 (json.dumps(st.session_state.skills), st.session_state.total_xp, st.session_state.gold, st.session_state.daily_quest_count, json.dumps(st.session_state.gold_history), st.session_state.username))
                        conn.commit()
                        conn.close()
                        
                    else: 
                        st.session_state.fail_count += 1
                        play_sound("bonk.mp3") 
                        
                        if error_msg: log_entry += f"\n💥 RUNTIME ERROR: {error_msg}"
                        else: log_entry += f"\n❌ ASSERTION FAILED: Logic incorrect."
                            
                        if st.session_state.fail_count >= 3 and "🪲 Упорный Багоискатель" not in st.session_state.achievements:
                            st.session_state.achievements.append("🪲 Упорный Багоискатель")
                            st.toast("🏆 Скрытое достижение: Упорный Багоискатель!", icon="🪲")
                            conn = sqlite3.connect('rpg_world.db')
                            c = conn.cursor()
                            c.execute("UPDATE users SET achievements=? WHERE username=?", (json.dumps(st.session_state.achievements), st.session_state.username))
                            conn.commit()
                            conn.close()
                        
                    st.session_state.battle_log = log_entry + "\n" + st.session_state.battle_log

            st.markdown("### 📜 Terminal Output")
            st.markdown(f"<div class='term-log'>{st.session_state.battle_log}</div>", unsafe_allow_html=True)

    # === MENTOR (GITHUB COPILOT STYLE) ===
    # === MENTOR (GITHUB COPILOT STYLE) ===
    with t_mentor:
        st.title("🦆 Copilot Duck")
        
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = [
                {"role": "assistant", "content": "Quack! I am your AI Copilot. Need help with your code or the tower Floors? Ask me about Variables, Lists, Loops, or any other topic!"}
            ]
            
        # Отрисовка всех сообщений
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): 
                st.write(msg["content"])
                
        # Ввод пользователя
        if prompt := st.chat_input("Ask Copilot Duck (e.g. 'help with loops')..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)
            
            p_lower = prompt.lower()
            reply = None
            
            # --- PRE-PROGRAMMED ANSWERS FOR THE 11 QUESTS (ENGLISH) ---
            if any(word in p_lower for word in ["variable", "var"]):
                reply = "Quack! 🦆 To create a variable, write its name, the `=` sign, and its value. For your task, just type: `x = 100`"
            elif any(word in p_lower for word in ["list", "array"]):
                reply = "Quack! 🦆 Lists are created using square brackets `[]`, with elements separated by commas. Create your list like this: `L = [1, 2, 3]`"
            elif any(word in p_lower for word in ["loop", "for", "while", "total"]):
                reply = "Quack! 🦆 You need to calculate the sum of numbers from 1 to 5 (1+2+3+4+5). You can use a loop, or simply write: `total = 15`"
            elif any(word in p_lower for word in ["condition", "if", "else"]):
                reply = "Quack! 🦆 In Python, you can write a one-line condition (ternary operator): `res = 'ok' if 5 > 0 else 'no'`"
            elif any(word in p_lower for word in ["exception", "error", "try", "catch"]):
                reply = "Quack! 🦆 Use a `try:` block (put `pass` inside or trigger an error like `1/0`), and below it an `except:` block where you set `err = True`"
            elif any(word in p_lower for word in ["function", "def"]):
                reply = "Quack! 🦆 Create a function using the `def` keyword: `def f():`. And inside (with an indent), use `return 'quack'`"
            elif any(word in p_lower for word in ["file", "open", "read", "write"]):
                reply = "Quack! 🦆 Use the built-in `open()` function. Pass it the filename `'test.txt'` and the write mode `'w'`. Save this into the variable `f`"
            elif any(word in p_lower for word in ["test", "assert"]):
                reply = "Quack! 🦆 The `assert` command checks if a statement is true. Just type: `assert 2 + 2 == 4`"
            elif any(word in p_lower for word in ["oop", "class", "object"]):
                reply = "Quack! 🦆 Write `class Hero:`, and on the next line (indented by 4 spaces) define a class variable: `hp = 100`"
            elif any(word in p_lower for word in ["gui", "ui", "streamlit", "interface"]):
                reply = "Quack! 🦆 Our game is built on a great library! Just create the variable: `ui = 'streamlit'`"
            elif any(word in p_lower for word in ["sql", "database", "db", "select"]):
                reply = "Quack! 🦆 To select all data from a table, you need the query `SELECT *`. Just assign the string `'SELECT *'` to the variable `q`!"
            
            # --- FALLBACK: ASK OPENROUTER AI ---
            if not reply:
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

# === 🏆 HALL OF FAME (ЗАЛ СЛАВЫ) ===
    with t_leader:
        st.title("🏆 Guild Hall of Fame")
        st.markdown("Топ-10 сильнейших магов сервера. Рейтинг строится по Total XP.")
        st.divider()
        
        # Запрашиваем из базы топ 10 игроков по XP (при равном XP выше тот, кто зарегался раньше)
        conn = sqlite3.connect('rpg_world.db')
        df_lb = pd.read_sql_query("SELECT display_name, avatar, total_xp, join_date FROM users ORDER BY total_xp DESC, join_date ASC LIMIT 10", conn)
        conn.close()
        
        # Отрисовываем красивый список
        for i, row in df_lb.iterrows():
            pos = i + 1
            # Получаем красивый бейдж ранга для каждого игрока в топе
            player_rank = get_rank_display(row['total_xp'], pos)
            
            # Эмодзи медалей для первых 3 мест
            medal = "🥇" if pos == 1 else "🥈" if pos == 2 else "🥉" if pos == 3 else f"**{pos}.**"
            
            # Красивая плашка игрока
            st.markdown(f"""
            <div style="background-color: rgba(255,255,255,0.05); padding: 10px 20px; border-radius: 8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; border-left: 4px solid {'#FFD700' if pos==1 else '#C0C0C0' if pos==2 else '#CD7F32' if pos==3 else '#444'};">
                <div style="font-size: 1.2em;">{medal} <span style="font-size: 1.5em; margin: 0 10px;">{row['avatar']}</span> <b>{row['display_name']}</b></div>
                <div style="text-align: right;">{player_rank}<br><span style="color: #888; font-size: 0.9em;">XP: {row['total_xp']}</span></div>
            </div>
            """, unsafe_allow_html=True)