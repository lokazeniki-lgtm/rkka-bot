import discord
from discord.ext import commands
from discord import app_commands
import sqlite3, time, os, asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

TOKEN = os.getenv("DISCORD_TOKEN")
# ВПИШИ СЮДА ID КАНАЛА ДЛЯ ЗАЯВОК
ADMIN_CHANNEL_ID = 1234567890123456789  

# --- РАНГИ РККА ---
RANKS = {
    1: "Красноармеец",
    2: "Ефрейтор",
    3: "Сержант",
    4: "Старшина",
    5: "Лейтенант",
    6: "Капитан",
    7: "Майор",
    8: "Полковник",
    9: "Подполковник",
    10: "Генерал-армии"
}

# --- НАСТРОЙКА DISCORD БОТА ---
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

def get_interaction_roles_str(interaction: discord.Interaction):
    if not interaction.guild or not interaction.user:
        return "Не на сервере"
    member = interaction.user
    roles = [role.name for role in member.roles if role.name != "@everyone"]
    if not roles:
        return "Нет ролей"
    return member.top_role.name


# ================= КОМАНДЫ БОТА =================

@bot.tree.command(name="add_visluga", description="[АДМИН] Выдать выслугу игроку")
@app_commands.describe(user="Выберите пользователя", amount="Сколько часов/дней выслуги выдать?")
@app_commands.default_permissions(administrator=True)
async def add_visluga(interaction: discord.Interaction, user: discord.Member, amount: int):
    conn = get_db()
    cursor = conn.cursor()
    
    # Проверяем, есть ли пользователь в базе, если нет - создаем
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, discord_name, service) VALUES (?, ?, ?)", 
                       (user.id, user.name, amount))
    else:
        cursor.execute("UPDATE users SET service = service + ? WHERE user_id=?", (amount, user.id))
        
    conn.commit()
    conn.close()
    
    await interaction.response.send_message(f"✅ Вы успешно добавили **{amount}** к выслуге игрока {user.mention}.", ephemeral=True)


@bot.tree.command(name="promote", description="Оставить заявку на повышение в РККА")
@app_commands.describe(
    rp_name="Ваше РП Имя (например: Иван Иванов)",
    game_nick="Ваш никнейм в игре (Ivan_Ivanov)",
    current_rank="Ваш текущий ранг (от 1 до 6)",
    desired_rank="Ранг, на который хотите повыситься (от 2 до 7)",
    proof="Скриншот с доказательствами (прикрепите файл)"
)
async def promote(interaction: discord.Interaction, rp_name: str, game_nick: str, current_rank: int, desired_rank: int, proof: discord.Attachment):
    
    # ПРОВЕРКА НА МАКСИМАЛЬНЫЙ РАНГ (7 ранг - Майор)
    if current_rank not in range(1, 8) or desired_rank not in range(2, 8):
        await interaction.response.send_message("❌ Ошибка: Через бота можно подать рапорт максимум на 7 ранг (Майор). Высшее командование назначается иначе.", ephemeral=True)
        return
        
    # Защита: нельзя подать заявку на ранг, который ниже или равен текущему
    if desired_rank <= current_rank:
        await interaction.response.send_message("❌ Ошибка: Желаемый ранг должен быть ВЫШЕ вашего текущего.", ephemeral=True)
        return
        
    # Формируем красивую заявку (Embed)
    embed = discord.Embed(title="🚨 Новая заявка на повышение 🚨", color=discord.Color.red())
    embed.add_field(name="Отправитель", value=interaction.user.mention, inline=False)
    embed.add_field(name="🎭 РП Имя", value=rp_name, inline=True)
    embed.add_field(name="🎮 Игровой Ник", value=game_nick, inline=True)
    embed.add_field(name="➖ Текущий ранг", value=f"{current_rank} — {RANKS[current_rank]}", inline=False)
    embed.add_field(name="➕ Желаемый ранг", value=f"{desired_rank} — {RANKS[desired_rank]}", inline=False)
    
    # Проверка скриншота
    if proof.content_type and proof.content_type.startswith("image/"):
        embed.set_image(url=proof.url)
    else:
        await interaction.response.send_message("❌ Пожалуйста, прикрепите картинку (скриншот).", ephemeral=True)
        return

    # Отправка заявки в специальный канал
    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    if admin_channel:
        await admin_channel.send(embed=embed)
        await interaction.response.send_message("✅ Ваша заявка успешно отправлена Высшему командованию!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Ошибка: Не настроен канал для отправки заявок. Проверьте ADMIN_CHANNEL_ID.", ephemeral=True)


# ================= СОБЫТИЯ И ЗАПУСК =================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Бот {bot.user} успешно запущен и готов к работе!")

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("ОШИБКА: Токен Discord не найден (проверьте os.getenv('DISCORD_TOKEN')).")
