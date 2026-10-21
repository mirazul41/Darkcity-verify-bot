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
class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="dark_city_verify_btn"
    )
    async def verify_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(VerifyModal())

    @discord.ui.button(
        label="Reset Your SID",
        style=discord.ButtonStyle.danger,
        emoji="🔄",
        custom_id="dark_city_reset_btn"
    )
    async def reset_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(ResetSIDModal())

    @discord.ui.button(
        label="Get Your SID",
        style=discord.ButtonStyle.secondary,
        emoji="💻",
        custom_id="dark_city_get_sid_btn"
    )
    async def get_sid_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        embed = discord.Embed(
            title="🖥️ How to Get Your PC SID",
            description="Follow these steps to find your Windows SID:\n\n"
                        "1. Press `Win + R` and type `cmd`.\n"
                        "2. Enter this command:\n"
                        "```cmd\nwhoami /user\n```\n"
                        "3. Copy the SID shown in the `SID` column and use it in verification.",
            color=discord.Color.from_rgb(252, 3, 119)
        )
        embed.set_footer(text="DARK CITY // PREMIUM ACCESS")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class VerifyModal(discord.ui.Modal, title="Verify License"):
    license_key = discord.ui.TextInput(
        label="License Key",
        placeholder="Enter your license key",
        required=True,
        max_length=200
    )

    sid = discord.ui.TextInput(
        label="PC SID",
        placeholder="Enter your PC SID",
        required=True,
        max_length=300
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            key = self.license_key.value.strip()
            pc_sid = self.sid.value.strip()

            if not key or not pc_sid:
                await interaction.followup.send(
                    "❌ License Key and PC SID are required.",
                    ephemeral=True
                )
                return

            username, record = find_license(key)

            if username is None:
                await interaction.followup.send(
                    "❌ Invalid License Key.",
                    ephemeral=True
                )
                return

            if is_blacklisted(username):
                await interaction.followup.send(
                    "⛔ This license is blacklisted.",
                    ephemeral=True
                )
                return

            record_ref = get_user_ref(username)
            saved_sid = str(record.get("SID", "")).strip()
            linked_discord_id = str(record.get("discord_id", "")).strip()
            current_discord_id = str(interaction.user.id)

            if not saved_sid:
                if linked_discord_id and linked_discord_id != current_discord_id:
                    await interaction.followup.send(
                        "❌ This license belongs to another Discord account.",
                        ephemeral=True
                    )
                    return

                record_ref.update({
                    "SID": pc_sid,
                    "discord_id": current_discord_id
                })

                logging.info(
                    "License verified: username=%s discord_id=%s",
                    username, current_discord_id
                )

                await interaction.followup.send(
                    "✅ License verified successfully!",
                    ephemeral=True
                )
                return

            if saved_sid == pc_sid:
                if linked_discord_id and linked_discord_id != current_discord_id:
                    await interaction.followup.send(
                        "❌ This license is linked to another Discord account.",
                        ephemeral=True
                    )
                    return

                if not linked_discord_id:
                    record_ref.update({"discord_id": current_discord_id})

                await interaction.followup.send(
                    "✅ This PC is already verified!",
                    ephemeral=True
                )
                return

            await interaction.followup.send(
                "❌ SID mismatch. Use Reset Your SID if you changed your PC.",
                ephemeral=True
            )

        except Exception:
            logging.exception("License verification failed")
            await interaction.followup.send(
                "⚠️ Server error during verification. Please contact support.",
                ephemeral=True
            )


class ResetSIDModal(discord.ui.Modal, title="Reset Your SID"):
    license_key = discord.ui.TextInput(
        label="License Key",
        placeholder="Enter your license key",
        required=True,
        max_length=200
    )

    new_sid = discord.ui.TextInput(
        label="New PC SID",
        placeholder="Enter your new PC SID",
        required=True,
        max_length=300
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            key = self.license_key.value.strip()
            pc_sid = self.new_sid.value.strip()

            if not key or not pc_sid:
                await interaction.followup.send(
                    "❌ License Key and new PC SID are required.",
                    ephemeral=True
                )
                return

            username, record = find_license(key)

            if username is None:
                await interaction.followup.send(
                    "❌ Invalid License Key.",
                    ephemeral=True
                )
                return

            if is_blacklisted(username):
                await interaction.followup.send(
                    "⛔ This license is blacklisted.",
                    ephemeral=True
                )
                return

            record_ref = get_user_ref(username)
            saved_sid = str(record.get("SID", "")).strip()
            linked_discord_id = str(record.get("discord_id", "")).strip()
            current_discord_id = str(interaction.user.id)

            if not saved_sid or not linked_discord_id:
                await interaction.followup.send(
                    "❌ This license has not been linked yet. Verify first or contact support.",
                    ephemeral=True
                )
                return

            if linked_discord_id != current_discord_id:
                await interaction.followup.send(
                    "❌ Only the Discord account linked to this license can reset its SID.",
                    ephemeral=True
                )
                return

            if saved_sid == pc_sid:
                await interaction.followup.send(
                    "ℹ️ This is already your current SID.",
                    ephemeral=True
                )
                return

            record_ref.update({"SID": pc_sid})

            logging.info(
                "SID reset: username=%s discord_id=%s",
                username, current_discord_id
            )

            await interaction.followup.send(
                "✅ SID reset successfully!",
                ephemeral=True
            )

        except Exception:
            logging.exception("SID reset failed")
            await interaction.followup.send(
                "⚠️ SID reset failed due to a server error. Please contact support.",
                ephemeral=True
            )

# ==========================================
# 7. SLASH COMMANDS
# ==========================================
@tree.command(
    name="verify",
    description="Open Dark City License Verification"
)
async def verify(interaction: discord.Interaction):
    try:
        # বক্সটি বড় দেখানোর জন্য অতিরিক্ত লাইন ব্রেক (spacing) যোগ করা হলো
        embed = discord.Embed(
            title="DARK CITY PREMIUM ACCESS",
            description="Your setup. Your license. Your entry.\n"
                        "─────────────────────────────────────────────\n\n"
                        " **LICENSE KEY AUTHENTICATION SYSTEM**\n\n"
                        "• Need Your PC SID\n"
                        "• License Key provided by us\n"
                        "─────────────────────────────────────────────",
            color=discord.Color.from_rgb(252, 3, 119)
        )
        embed.set_footer(text="Verify and enjoy our premium panel")

        await interaction.response.send_message(
            embed=embed,
            view=VerifyView(),
            ephemeral=True
        )
    except Exception:
        logging.exception("/verify command failed")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "⚠️ Could not open the verification panel. Please try again.",
                ephemeral=True
            )
# ==========================================
# 8. BOT STARTUP
# ==========================================
@client.event
async def on_ready():
    try:
        client.add_view(VerifyView())
        
        synced = await tree.sync()
        logging.info("Logged in as %s", client.user)
        logging.info("Synced %s slash command(s)", len(synced))
        logging.info("Dark City Verify is online!")
    except Exception:
        logging.exception("Failed during startup sync")


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError(
            "DISCORD_BOT_TOKEN or DISCORD_TOKEN is missing. Set it before starting the bot."
        )

    client.run(TOKEN)
