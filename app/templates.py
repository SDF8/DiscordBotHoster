PING = '''import discord
from discord.ext import commands
import os

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")


if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN not found. Set it in the hoster.")
    else:
        bot.run(TOKEN)
'''

SLASH = '''import discord
from discord import app_commands
import os

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")


class PingBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)


client = PingBot()


@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")


@client.tree.command(name="ping", description="Checks the bot latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(client.latency * 1000)}ms")


if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN not found. Set it in the hoster.")
    else:
        client.run(TOKEN)
'''

MODERATION = '''import discord
from discord.ext import commands
import os

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
    await ctx.channel.purge(limit=amount)
    await ctx.send(f"Cleared {amount} messages.", delete_after=5)


if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN not found. Set it in the hoster.")
    else:
        bot.run(TOKEN)
'''

TEMPLATES = {
    "Ping command (basic)": PING,
    "Slash commands": SLASH,
    "Moderation clear": MODERATION,
}


def pretty_permissions():
    return [
        ("View Channels", 1 << 11),
        ("Send Messages", 1 << 12),
        ("Read Message History", 1 << 17),
        ("Add Reactions", 1 << 6),
        ("Embed Links", 1 << 15),
        ("Attach Files", 1 << 16),
        ("Manage Messages", 1 << 14),
        ("Use Slash Commands", 1 << 32),
        ("Manage Roles", 1 << 29),
        ("Manage Channels", 1 << 4),
        ("Manage Webhooks", 1 << 30),
        ("Administrator", 1 << 3),
    ]


def invite_url(token, selected_flags):
    client_id = ""
    part = token.split(".")[0] if token else ""
    if part.isdigit():
        client_id = part
    perm = 0
    for bit in selected_flags:
        perm |= bit
    scope = "bot"
    if perm & (1 << 3):
        scope = "bot applications.commands"
    if client_id:
        return f"https://discord.com/oauth2/authorize?client_id={client_id}&scope={scope}&permissions={perm}"
    return ""