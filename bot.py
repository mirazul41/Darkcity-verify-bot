
# ==========================================
# 6. VERIFY PANEL & MODALS
# ==========================================
class VerifyView(discord.ui.View):
    def __init__(self):
        # Bot restart holeo jeno button kaj kore tar jonno timeout=None
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify License",
        style=discord.ButtonStyle.primary,
        emoji="⚡",
        custom_id="dark_city_verify_btn",
        row=0
    )
    async def verify_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(VerifyModal())

    @discord.ui.button(
        label="Reset Your SID",
        style=discord.ButtonStyle.primary,
        emoji="🔄",
        custom_id="dark_city_reset_btn",
        row=1
    )
    async def reset_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(ResetSIDModal())

    @discord.ui.button(
        label="Get SID",
        style=discord.ButtonStyle.primary,
        emoji="🖥️",
        custom_id="dark_city_get_sid_btn",
        row=2
    )
    async def get_sid_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        sid_embed = discord.Embed(
            title="🖥️ HOW TO GET YOUR SID",
            description=(
                "Follow these steps on the PC you want to verify.\n\n"
                "**1.** Press `Win + R`, type `cmd`, then press Enter.\n"
                "**2.** Run this command:\n"
                "```cmd\nwhoami /user\n```"
                "**3.** Copy the SID shown in the `SID` column."
            ),
            color=discord.Color.from_rgb(18, 60, 117)
        )
        sid_embed.set_footer(
            text="DARK CITY // PREMIUM ACCESS"
        )
        await interaction.response.send_message(
            embed=sid_embed,
            ephemeral=True
        )


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

            # First verification: claim the license
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

            # Same PC SID
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

            # Different PC SID
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
