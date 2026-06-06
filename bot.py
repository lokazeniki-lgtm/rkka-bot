import discord
from discord.ext import commands
from discord import app_commands
import sqlite3, time, os, asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

TOKEN = os.getenv("DISCORD_TOKEN")

# --- НАСТРОЙКА DISCORD БОТА ---
# Включаем intents для работы с пользователями на сервере
intents = discord.Intents.default()
intents.members = True  # КРИТИЧЕСКИ ВАЖНО: разрешает боту видеть роли участников

bot = commands.Bot(command_prefix="!", intents=intents)

# --- НАСТРОЙКА FASTAPI (API) ---
app = FastAPI(title="RKKA Bot API")

def get_db():
    conn = sqlite3.connect("rkka.db")
    return conn

# Инициализация БД
conn = get_db()
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
conn.close()

def get_user_db(uid):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    user = cursor.fetchone()
    conn.close()
    return user

# Функция для получения названия роли/ролей пользователя в Discord
def get_user_roles_str(member: discord.Member):
    if not isinstance(member, discord.Member):
        return "Не на сервере"
    
    # Фильтруем роль @everyone (она есть у всех)
    roles = [role.name for role in member.roles if role.name != "@everyone"]
    
    if not roles:
        return "Нет ролей"
    
    # Вариант 1: Показывает самую высокую роль по иерархии Дискорда
    return member.top_role.name
    
    # Вариант 2: Если хочешь показывать ВСЕ роли через запятую, 
    # закомментируй строку выше (поставь # перед return member.top_role.name) 
    # и раскомментируй строку ниже (убери # перед return):
    # return ", ".join(roles)


# --- МАРШРУТЫ API (ENDPOINTS) ---

@app.get("/")
def read_root():
    return {"status": "online", "message": "RKKA API работает"}

# --- КОМАНДЫ ДИСКОРД БОТА ---

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

@bot.tree.command(name="reg", description="Регистрация")
async def reg(interaction: discord.Interaction, rp_name: str, game_nick: str):
    if get_user_db(interaction.user.id):
        await interaction.response.send_message("Вы уже зарегистрированы.", ephemeral=True)
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users(user_id,discord_name,rp_name,game_nick) VALUES(?,?,?,?)",
        (interaction.user.id, str(interaction.user), rp_name, game_nick)
    )
    conn.commit()
    conn.close()

    embed = discord.Embed(title="Регистрация завершена")
    embed.add_field(name="RP Имя", value=rp_name, inline=False)
    embed.add_field(name="Игровой ник", value=game_nick, inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="Статистика")
async def stats(interaction: discord.Interaction):
    user = get_user_db(interaction.user.id)
    if not user:
        await interaction.response.send_message("Сначала используйте /reg", ephemeral=True)
        return

    embed = discord.Embed(title="Личное дело")
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="RP Имя", value=user[2], inline=False)
    embed.add_field(name="Игровой ник", value=user[3], inline=False)
    embed.add_field(name="Выслуга", value=str(user[4]), inline=True)
    
    # Получаем актуальную роль из Дискорда в реальном времени
    current_role = get_user_roles_str(interaction.user)
    embed.add_field(name="Звание (Роль)", value=current_role, inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="up", description="Получить 1 очко выслуги")
async def up(interaction: discord.Interaction):
    user = get_user_db(interaction.user.id)
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

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET service=?, last_up=? WHERE user_id=?",
        (service, now, interaction.user.id)
    )
    conn.commit()
    conn.close()

    await interaction.response.send_message(
        f"Вы получили 1 очко выслуги. Всего: {service}"
    )

# --- ЗАПУСК БОТА И API ОДНОВРЕМЕННО ---
async def main():
    port = int(os.getenv("PORT", 8080))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    
    await asyncio.gather(
        server.serve(),
        bot.start(TOKEN)
    )

if __name__ == "__main__":
    asyncio.run(main())
