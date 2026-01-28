import os
import asyncio
from dotenv import load_dotenv

import discord
from discord import app_commands
from fastapi import FastAPI
import uvicorn
import aiosqlite

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
PORT = int(os.getenv("PORT", "3000"))
DB_PATH = os.getenv("DATABASE_PATH", "dev.db")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

app = FastAPI()

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS delivery (
                id TEXT PRIMARY KEY
            )
        """)
        await db.commit()

async def set_channel(guild_id: str, channel_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_config (guild_id, channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id
        """, (guild_id, channel_id))
        await db.commit()

async def get_channel(guild_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT channel_id FROM guild_config WHERE guild_id=?", (guild_id,))
        row = await cur.fetchone()
        return row[0] if row else None

@tree.command(name="status", description="Show current bot configuration.")
async def status(interaction: discord.Interaction):
    if not interaction.guild_id:
        return await interaction.response.send_message("Use this inside a server.", ephemeral=True)

    ch = await get_channel(str(interaction.guild_id))
    if not ch:
        return await interaction.response.send_message("No channel set. Use /setchannel.", ephemeral=True)

    await interaction.response.send_message(f"✅ Pipeline bot alive bossmen!. Posting updates to <#{ch}>", ephemeral=True)

@tree.command(name="setchannel", description="Set the channel for GitHub updates.")
@app_commands.checks.has_permissions(manage_guild=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild_id:
        return await interaction.response.send_message("Use this inside a server.", ephemeral=True)

    await set_channel(str(interaction.guild_id), str(channel.id))
    await interaction.response.send_message(f"✅ Updates will post in {channel.mention}", ephemeral=True)

@setchannel.error
async def setchannel_error(interaction: discord.Interaction, _error: app_commands.AppCommandError):
    # Most common: missing permissions
    if interaction.response.is_done():
        return
    await interaction.response.send_message("You need **Manage Server** permission to run this.", ephemeral=True)

@app.get("/health")
async def health():
    return {"ok": True, "service": "pipeline-bot"}

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")

@client.event
async def on_ready():
    await init_db()
    await tree.sync()
    print(f"✅ Logged in as {client.user} and commands synced.")

async def main():
    # Run FastAPI alongside the Discord client
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, run_api)

    if not DISCORD_TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN in .env")
    await client.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
