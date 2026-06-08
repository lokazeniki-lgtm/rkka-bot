import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "ТВОЙ_ТОКЕН_БОТА"
ADMIN_IDS = [123456789, 987654321]  # Впиши сюда Telegram ID администраторов/лидеров

# Справочник рангов РККА
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

# Машина состояний для заявки на повышение
class PromotionForm(StatesGroup):
    rp_name = State()
    game_nickname = State()
    current_rank = State()
    desired_rank = State()
    proofs = State()

router = Router()

# ================= КОМАНДЫ АДМИНИСТРАТОРОВ =================

@router.message(Command("add_visluga"))
async def add_visluga_command(message: Message, command: CommandObject):
    """Команда для выдачи выслуги. Формат: /add_visluga [ID_игрока] [Кол-во часов/дней]"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав для использования этой команды.")
        return

    # Проверка правильности аргументов
    if not command.args:
        await message.answer("⚠️ Использование: `/add_visluga <ID_игрока> <значение>`", parse_mode="Markdown")
        return

    args = command.args.split()
    if len(args) < 2:
        await message.answer("⚠️ Ошибка. Укажите ID игрока и значение выслуги.")
        return

    player_id = args[0]
    visluga_value = args[1]

    # ТУТ ДОЛЖНА БЫТЬ ЛОГИКА ТВОЕЙ БАЗЫ ДАННЫХ (SQLite, MySQL, PostgreSQL)
    # db.update_visluga(player_id, visluga_value)

    await message.answer(f"✅ Вы успешно выдали выслугу ({visluga_value}) игроку с ID {player_id}.")

# ================= СИСТЕМА ПОВЫШЕНИЙ =================

@router.message(Command("promote_request"))
async def start_promotion_request(message: Message, state: FSMContext):
    """Начало подачи заявки на повышение"""
    await message.answer("📝 Начинаем оформление заявки на повышение.\n\nВведите ваше **РП Имя** (например, Иван Иванов):", parse_mode="Markdown")
    await state.set_state(PromotionForm.rp_name)

@router.message(PromotionForm.rp_name)
async def process_rp_name(message: Message, state: FSMContext):
    await state.update_data(rp_name=message.text)
    await message.answer("👤 Теперь введите ваш **Никнейм в игре** (например, Ivan_Ivanov):", parse_mode="Markdown")
    await state.set_state(PromotionForm.game_nickname)

@router.message(PromotionForm.game_nickname)
async def process_game_nickname(message: Message, state: FSMContext):
    await state.update_data(game_nickname=message.text)
    
    # Формируем список рангов для подсказки
    ranks_text = "\n".join([f"{num} - {name}" for num, name in RANKS.items()])
    await message.answer(f"🎖 Укажите ваш **ТЕКУЩИЙ ранг** (цифрой от 1 до 9):\n\nДоступные ранги:\n{ranks_text}", parse_mode="Markdown")
    await state.set_state(PromotionForm.current_rank)

@router.message(PromotionForm.current_rank)
async def process_current_rank(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) not in RANKS:
        await message.answer("⚠️ Пожалуйста, введите корректный номер ранга (цифру).")
        return
    
    await state.update_data(current_rank=int(message.text))
    await message.answer("🎯 Укажите ранг, **НА КОТОРЫЙ вы хотите повыситься** (цифрой):", parse_mode="Markdown")
    await state.set_state(PromotionForm.desired_rank)

@router.message(PromotionForm.desired_rank)
async def process_desired_rank(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) not in RANKS:
        await message.answer("⚠️ Пожалуйста, введите корректный номер ранга (цифру).")
        return
    
    await state.update_data(desired_rank=int(message.text))
    await message.answer("📸 Отлично! Теперь **отправьте скриншот** (доказательства работы) в этот чат.\n\n*Если скриншотов несколько, объедините их в коллаж или отправьте ссылку на Imgur/Япикс текстом.*", parse_mode="Markdown")
    await state.set_state(PromotionForm.proofs)

@router.message(PromotionForm.proofs, F.photo | F.text)
async def process_proofs(message: Message, state: FSMContext, bot: Bot):
    user_data = await state.get_data()
    
    # Сбор данных
    rp_name = user_data['rp_name']
    game_nickname = user_data['game_nickname']
    current_rank_num = user_data['current_rank']
    desired_rank_num = user_data['desired_rank']
    
    current_rank_name = RANKS[current_rank_num]
    desired_rank_name = RANKS[desired_rank_num]

    # Формируем текст заявки
    report_text = (
        f"🚨 **НОВАЯ ЗАЯВКА НА ПОВЫШЕНИЕ** 🚨\n\n"
        f"👤 **Отправитель:** {message.from_user.full_name} (@{message.from_user.username})\n"
        f"🎭 **РП Имя:** {rp_name}\n"
        f"🎮 **Игровой Ник:** {game_nickname}\n"
        f"➖ **Текущий ранг:** {current_rank_num} ({current_rank_name})\n"
        f"➕ **Желаемый ранг:** {desired_rank_num} ({desired_rank_name})\n"
    )

    # Отправляем заявку всем администраторам
    for admin_id in ADMIN_IDS:
        try:
            if message.photo:
                # Если отправили фото, пересылаем фото с подписью
                photo_id = message.photo[-1].file_id
                await bot.send_photo(chat_id=admin_id, photo=photo_id, caption=report_text, parse_mode="Markdown")
            else:
                # Если отправили ссылку (текстом)
                report_text += f"\n🔗 **Доказательства:** {message.text}"
                await bot.send_message(chat_id=admin_id, text=report_text, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")

    await message.answer("✅ Ваша заявка успешно отправлена Высшему командованию! Ожидайте проверки.")
    await state.clear()


# ================= ЗАПУСК БОТА =================
async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    print("Бот РККА успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
