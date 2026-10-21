import os
import json
import logging
import threading
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

import discord
import firebase_admin
from discord import app_commands
from firebase_admin import credentials, db

# ==========================================
# 1. FLASK WEB SERVER (Render keep-alive)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Dark City Verify Bot is Online!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()

# Web Server Start Korun
keep_alive()

# ==========================================
# 2. CONFIGURATION & ENVIRONMENT
# ==========================================
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_TOKEN", "").strip()

FIREBASE_URL = (
    "https://dark-city-premium-badea-default-rtdb.firebaseio.com/"
)

LICENSE_PATH = "Lisenc key"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ==========================================
# 3. FIREBASE CONNECTION (Render Friendly)
# ==========================================
if not firebase_admin._apps:
    firebase_json_env = os.getenv("FIREBASE_KEY_JSON")
    
    if firebase_json_env:
        try:
            cred_dict = json.loads(firebase_json_env)
            cred = credentials.Certificate(cred_dict)
            logging.info("Firebase initialized using Environment Variable.")
        except Exception as e:
            logging.error(f"Failed to load FIREBASE_KEY_JSON from env: {e}")
            cred = credentials.Certificate(str(BASE_DIR / "firebase-key.json"))
    else:
        cred = credentials.Certificate(str(BASE_DIR / "firebase-key.json"))
        logging.info("Firebase initialized using local firebase-key.json file.")

    firebase_admin.initialize_app(
        cred,
        {"databaseURL": FIREBASE_URL}
    )

licenses_ref = db.reference(LICENSE_PATH)
blacklist_ref = db.reference("Blacklist")

# ==========================================
# 4. LICENSE HELPERS
# ==========================================
def find_license(license_key):
    records = licenses_ref.get() or {}

    if not isinstance(records, dict):
        return None, None

    license_key = license_key.strip()

    for username, record in records.items():
        if not isinstance(record, dict):
            continue

        saved_key = str(record.get("key", "")).strip()

        if saved_key and saved_key == license_key:
            return username, record

    return None, None


def is_blacklisted(username):
    blacklist = blacklist_ref.get() or {}

    if isinstance(blacklist, dict):
        return username in blacklist

    if isinstance(blacklist, list):
        return username in blacklist

    return False


def get_user_ref(username):
    return licenses_ref.child(username)

# ==========================================
# 5. DISCORD CLIENT
# ==========================================
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ==========================================
# 6. VERIFY PANEL & MODALS
# ==========================================
