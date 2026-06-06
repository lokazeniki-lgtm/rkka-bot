import discord
from discord.ext import commands
from discord import app_commands
import sqlite3, time, os, asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

TOKEN = os.getenv("DISCORD_TOKEN")

# --- НАСТРОЙКА DISCORD БОТА ---
# Используем полностью стандартные интенты БЕЗ привилегированных прав.
# Это на 100% уберет ошибку PrivilegedIntentsRequired!
intents = discord.Intents.default()

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

# Функция для безопасного получения роли из взаимодействия (Interaction)
def get_interaction_roles_str(interaction: discord.Interaction):
    # Проверяем, что команда вызвана на сервере, а не в ЛС
    if not interaction.guild or not interaction.user:
        return "Не на сервере"
    
    # Так как при вызове слэш-команды Дискорд сам передает нам объект пользователя со всеми его ролями,
    # мы можем прочитать их напрямую из interaction.user без включения Members Intent!
    member = interaction.user
    
    # Фильтруем роль @everyone
    roles = [role.name for role in member.roles if role.name != "@everyone"]
    
    if not roles:
        return "Нет ролей"
    
    # Показываем самую высокую по иерархии роль
    return member.top_role.name


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
    
    # Извлекаем роль прямо из контекста команды
    current_role = get_interaction_roles_str(interaction)
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
