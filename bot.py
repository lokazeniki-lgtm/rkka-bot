import discord
from discord.ext import commands
from discord import app_commands
import sqlite3, time, os, asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

TOKEN = os.getenv("DISCORD_TOKEN")

# --- НАСТРОЙКА DISCORD БОТА ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- НАСТРОЙКА FASTAPI (API) ---
app = FastAPI(title="RKKA Bot API")

# Подключение к БД
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

RANKS = {
    0: "Красноармеец", 2: "Ефрейтор", 4: "Сержант", 
    8: "Старшина", 16: "Старший лейтенант", 32: "Капитан", 64: "Полковник"
}

def get_rank(service):
    rank = "Красноармеец"
    for req, name in sorted(RANKS.items()):
        if service >= req:
            rank = name
    return rank

def get_user_db(uid):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    user = cursor.fetchone()
    conn.close()
    return user

# --- МАРШРУТЫ API (ENDPOINTS) ---

@app.get("/")
def read_root():
    return {"status": "online", "message": "RKKA API работает"}

@app.get("/users")
def get_all_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, rp_name, game_nick, service FROM users")
    rows = cursor.fetchall()
    conn.close()
    
    users_list = []
    for row in rows:
        users_list.append({
            "user_id": row[0],
            "rp_name": row[1],
            "game_nick": row[2],
            "service": row[3],
            "rank": get_rank(row[3])
        })
    return {"users": users_list}

# Схема данных для отправки POST-запроса в API
class ServiceUpdate(BaseModel):
    user_id: int
    amount: int

@app.post("/add_service")
def api_add_service(data: ServiceUpdate):
    user = get_user_db(data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET service = service + ? WHERE user_id=?", (data.amount, data.user_id))
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Добавлено {data.amount} выслуги пользователю {data.user_id}"}


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
    embed.add_field(name="Выслуга", value=str(user[4]))
    embed.add_field(name="Звание", value=get_rank(user[4]))
    await interaction.response.send_message(embed=embed)

# --- ЗАПУСК БОТА И API ОДНОВРЕМЕННО ---

async def main():
    # Запускаем веб-сервер API на порту, который выдаст Railway (по умолчанию 8080)
    port = int(os.getenv("PORT", 8080))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    
    # Создаем параллельные задачи для бота и для API сервера
    await asyncio.gather(
        server.serve(),
        bot.start(TOKEN)
    )

if __name__ == "__main__":
    asyncio.run(main())
