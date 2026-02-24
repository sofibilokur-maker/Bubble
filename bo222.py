import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

TOKEN = "8068379904:AAF8V6g-uaPNWmCqHGwnDJhpcsjPuoN9VBQ"
ADMIN_IDS = [717754752, 1069902248]

bot = Bot(token=TOKEN)
dp = Dispatcher()


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Замовити лабораторну")],
        [KeyboardButton(text="💰 Ціни")]
    ],
    resize_keyboard=True
)


start_inline = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Розпочати", callback_data="go_start")]
    ]
)



class OrderState(StatesGroup):
    subject = State()
    topic = State()
    deadline = State()
    files = State()

paused_users = set()

order_files: dict[int, list] = {}




@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    paused_users.discard(message.from_user.id)
    await state.clear()
    await message.answer(
        "👋 Вітаю! Я бот для замовлення лабораторних робіт.\n\n"
        "Натисніть кнопку нижче, щоб почати:",
        reply_markup=start_inline
    )

@dp.callback_query(lambda c: c.data == "go_start")
async def go_start_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Оберіть дію з меню нижче 👇",
        reply_markup=main_keyboard
    )
    await callback.answer()




@dp.message(lambda message: message.text == "📚 Замовити лабораторну")
async def order_start(message: types.Message, state: FSMContext):
    if message.from_user.id in paused_users:
        await message.answer("❗ Замовлення завершено. Натисніть /start для нового замовлення.")
        return
    await message.answer("📘 Напишіть предмет:")
    await state.set_state(OrderState.subject)

@dp.message(OrderState.subject)
async def get_subject(message: types.Message, state: FSMContext):
    await state.update_data(subject=message.text)
    await message.answer("📑 Напишіть тему лабораторної:")
    await state.set_state(OrderState.topic)

@dp.message(OrderState.topic)
async def get_topic(message: types.Message, state: FSMContext):
    await state.update_data(topic=message.text)
    await message.answer("⏳ Вкажіть дедлайн:")
    await state.set_state(OrderState.deadline)

@dp.message(OrderState.deadline)
async def get_deadline(message: types.Message, state: FSMContext):
    await state.update_data(deadline=message.text)
    order_files[message.from_user.id] = []
    await message.answer(
        "📎 Надішліть файли (PDF, PNG, DOCX, DOC).\n"
        "Можна надіслати кілька файлів.\n\n"
        "Коли всі файли надіслані — напишіть /done"
    )
    await state.set_state(OrderState.files)


@dp.message(OrderState.files)
async def get_files(message: types.Message, state: FSMContext):
    user_id = message.from_user.id


    if message.text and message.text.strip().lower() == "/done":
        files = order_files.get(user_id, [])
        if not files:
            await message.answer("❗ Ви не надіслали жодного файлу. Надішліть хоча б один файл.")
            return
        await finalize_order(message, state)
        return

    os.makedirs("uploads", exist_ok=True)
    allowed_extensions = [".pdf", ".png", ".docx", ".doc"]
    saved = False

    if message.document:
        file_name = message.document.file_name.lower()
        if not any(file_name.endswith(ext) for ext in allowed_extensions):
            await message.answer("❗ Дозволені лише PDF, PNG, DOCX, DOC файли. Надішліть інший файл або /done")
            return
        file_path = os.path.join("uploads", f"{user_id}_{message.document.file_name}")
        await message.document.download(destination=file_path)
        order_files.setdefault(user_id, []).append((file_path, message.document.file_name))
        saved = True

    elif message.photo:
        file_name = f"{user_id}_photo_{len(order_files.get(user_id, []))}.png"
        file_path = os.path.join("uploads", file_name)
        await message.photo[-1].download(destination=file_path)
        order_files.setdefault(user_id, []).append((file_path, file_name))
        saved = True

    else:
        await message.answer("❗ Надішліть файл документом або фото (PDF, PNG, DOCX, DOC), або /done щоб завершити.")
        return

    if saved:
        count = len(order_files.get(user_id, []))
        await message.answer(f"✅ Файл прийнято ({count} шт.). Надішліть ще або напишіть /done")


async def finalize_order(message: types.Message, state: FSMContext):

    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or "Без username"
    files = order_files.get(user_id, [])

    file_names_str = ", ".join([name for _, name in files]) if files else "—"

    # Запис в orders.txt
    with open("orders.txt", "a", encoding="utf-8") as f:
        f.write(
            f"User ID: {user_id}\n"
            f"Username: @{username}\n"
            f"Subject: {data.get('subject')}\n"
            f"Topic: {data.get('topic')}\n"
            f"Deadline: {data.get('deadline')}\n"
            f"Files: {file_names_str}\n"
            f"-------------------------\n"
        )


    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"🔔 <b>Нове замовлення!</b>\n\n"
            f"👤 @{username} (ID: {user_id})\n"
            f"📘 Предмет: {data.get('subject')}\n"
            f"📑 Тема: {data.get('topic')}\n"
            f"⏳ Дедлайн: {data.get('deadline')}\n"
            f"📎 Файлів: {len(files)}",
            parse_mode="HTML"
        )

        for file_path, file_name in files:
            try:
                await bot.send_document(admin_id, FSInputFile(file_path), caption=f"📄 {file_name}")
            except Exception as e:
                await bot.send_message(admin_id, f"⚠️ Не вдалося надіслати файл: {file_name}\n{e}")

    # Відповідь користувачу
    await message.answer(
        "✅ Замовлення прийнято! Ми зв'яжемося з вами після обробки.\n"
        "Для нового замовлення натисніть /start.",
        reply_markup=main_keyboard
    )

    # Очищення
    order_files.pop(user_id, None)
    await state.clear()
    paused_users.add(user_id)




@dp.message(lambda message: message.text == "💰 Ціни")
async def prices(message: types.Message):
    try:
        photo = FSInputFile("prices.jpg")
        await message.answer_photo(photo, caption="💰 Наші ціни на лабораторні роботи")
    except FileNotFoundError:
        await message.answer("⚠️ Зображення з цінами поки недоступне. Зверніться до адміністратора.")




async def main():
    print(" Бот запущено...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())