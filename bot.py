import discord
from discord.ext import commands
from discord import app_commands
import sqlite3, time, os

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

conn = sqlite3.connect("rkka.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    discord_name TEXT,
    rp_name TEXT,
    game_nick TEXT,
    service INTEGER DEFAULT 0,
    last_up INTEGER DEFAULT 0
)
""")
conn.commit()

RANKS = {
    0: "Красноармеец",
    2: "Ефрейтор",
    4: "Сержант",
    8: "Старшина",
    16: "Старший лейтенант",
    32: "Капитан",
    64: "Полковник"
}

def get_rank(service):
    rank = "Красноармеец"
    for req, name in sorted(RANKS.items()):
        if service >= req:
            rank = name
    return rank

def get_user(uid):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    return cursor.fetchone()

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

@bot.tree.command(name="reg", description="Регистрация")
async def reg(interaction: discord.Interaction, rp_name: str, game_nick: str):
    if get_user(interaction.user.id):
        await interaction.response.send_message("Вы уже зарегистрированы.", ephemeral=True)
        return

    cursor.execute(
        "INSERT INTO users(user_id,discord_name,rp_name,game_nick) VALUES(?,?,?,?)",
        (interaction.user.id, str(interaction.user), rp_name, game_nick)
    )
    conn.commit()

    embed = discord.Embed(title="Регистрация завершена")
    embed.add_field(name="RP Имя", value=rp_name, inline=False)
    embed.add_field(name="Игровой ник", value=game_nick, inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="Статистика")
async def stats(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    if not user:
        await interaction.response.send_message("Сначала используйте /reg", ephemeral=True)
        return

    embed = discord.Embed(title="Личное дело")
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="RP Имя", value=user[2], inline=False)
    embed.add_field(name="Игровой ник", value=user[3], inline=False)
    embed.add_field(name="Выслуга", value=str(user[4]))
    embed.add_field(name="Звание", value=get_rank(user[4]))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="up", description="Получить 1 очко выслуги")
async def up(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    if not user:
        await interaction.response.send_message("Сначала используйте /reg", ephemeral=True)
        return

    now = int(time.time())
    last_up = user[5]
    cooldown = 43200

    if now - last_up < cooldown:
        left = cooldown - (now - last_up)
        h = left // 3600
        m = (left % 3600) // 60
        await interaction.response.send_message(
            f"Следующая выслуга через {h}ч {m}м",
            ephemeral=True
        )
        return

    service = user[4] + 1

    cursor.execute(
        "UPDATE users SET service=?, last_up=? WHERE user_id=?",
        (service, now, interaction.user.id)
    )
    conn.commit()

    await interaction.response.send_message(
        f"Вы получили 1 очко выслуги. Всего: {service}"
    )

@bot.tree.command(name="list", description="Список бойцов")
async def list_users(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Нет прав.", ephemeral=True)
        return

    cursor.execute("SELECT rp_name, game_nick, service FROM users ORDER BY service DESC")
    rows = cursor.fetchall()

    embed = discord.Embed(title="Реестр РККА")

    if not rows:
        embed.description = "Пусто."
    else:
        text = ""
        for i, row in enumerate(rows[:25], start=1):
            text += f"{i}. {row[0]} | {row[1]} | Выслуга: {row[2]}\\n"
        embed.description = text

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="addservice", description="Добавить выслугу")
@app_commands.default_permissions(administrator=True)
async def addservice(interaction: discord.Interaction, member: discord.Member, amount: int):
    user = get_user(member.id)
    if not user:
        await interaction.response.send_message("Игрок не зарегистрирован.", ephemeral=True)
        return

    cursor.execute(
        "UPDATE users SET service = service + ? WHERE user_id=?",
        (amount, member.id)
    )
    conn.commit()

    await interaction.response.send_message(f"Добавлено {amount} выслуги.")

@bot.tree.command(name="removeservice", description="Снять выслугу")
@app_commands.default_permissions(administrator=True)
async def removeservice(interaction: discord.Interaction, member: discord.Member, amount: int):
    user = get_user(member.id)
    if not user:
        await interaction.response.send_message("Игрок не зарегистрирован.", ephemeral=True)
        return

    new_service = max(0, user[4] - amount)

    cursor.execute(
        "UPDATE users SET service=? WHERE user_id=?",
        (new_service, member.id)
    )
    conn.commit()

    await interaction.response.send_message(f"Снято {amount} выслуги.")

bot.run(TOKEN)
