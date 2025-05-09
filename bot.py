import asyncio
import json
import aiohttp
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

API_URL = "https://stock-tracker-iota-steel.vercel.app/api/garden"
DATA_FILE = "bot_data.json"
POLL_INTERVALS = {
    "SEEDS": 5 * 60,
    "GEAR": 5 * 60,
    "EGG":  30 * 60,
}

ITEM_CATEGORIES = {
    'SEEDS': [
        'Carrot', 'Strawberry', 'Blueberry', 'Orange Tulip', 'Tomato',
        'Corn', 'Daffodil', 'Watermelon', 'Pumpkin', 'Apple', 'Bamboo',
        'Coconut', 'Cactus', 'Dragon Fruit', 'Mango', 'Grape', 'Mushroom', 'Pepper'
    ],
    'GEAR': [
        'Watering Can', 'Trowel', 'Basic Sprinkler', 'Advanced Sprinkler',
        'Godly Sprinkler', 'Lightning Rod', 'Master Sprinkler'
    ],
    'EGG': [
        'Common Egg', 'Uncommon Egg', 'Rare Egg', 'Legendary Egg', 'Bug Egg'
    ]
}

bot = Bot(token="YOUR_TOKEN_HERE")
dp = Dispatcher(bot)

# --- Утиліти для JSON-збереження ---
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"users": {}, "last_stock": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data_store = load_data()

# --- Меню ---
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("🔍 Подивитись сток зараз")
main_kb.add("⚙️ Настроїти трекінг", "🚫 Увімкнути/Вимкнути трекінг")

back_button = KeyboardButton("⬅️ Назад")
refresh_button = KeyboardButton("🔄 Оновити")

def get_stock_markup():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for sec in ["GEAR STOCK", "EGG STOCK", "SEEDS STOCK"]:
        kb.add(sec)
    kb.add(back_button, refresh_button)
    return kb

def get_tracking_markup(category, user_prefs):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for item in ITEM_CATEGORIES[category]:
        symbol = "✅" if user_prefs.get(category, {}).get(item) else "❌"
        kb.insert(f"{symbol} {item}")
    kb.add("⬅️ Назад")
    return kb

# --- API Fetch ---
async def fetch_stock():
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL) as resp:
            return await resp.json()

# --- Перевірка оновлення ---
async def check_updates_for(section):
    while True:
        payload = await fetch_stock()
        new_data = next(sec for sec in payload["data"] if sec["section"].startswith(section))
        prev_data = data_store["last_stock"].get(section)

        if prev_data != new_data["items"]:
            # справжнє оновлення
            data_store["last_stock"][section] = new_data["items"]
            save_data(data_store)

            # розіслати юзерам
            for user_id, prefs in data_store["users"].items():
                if prefs.get("enabled") and prefs.get(section):
                    for it in new_data["items"]:
                        name, qty = it["name"], it["quantity"]
                        if prefs[section].get(name):
                            await bot.send_message(
                                user_id,
                                f"✅ **{name}** в {section.split()[0]} стоку: {qty}",
                                parse_mode="Markdown"
                            )
        await asyncio.sleep(POLL_INTERVALS[section])

# --- Хендлери ---
@dp.message_handler(commands=["start"])
async def cmd_start(msg: types.Message):
    uid = str(msg.from_user.id)
    if uid not in data_store["users"]:
        data_store["users"][uid] = {"enabled": True}
        save_data(data_store)
    await msg.answer("Вітаю! Виберіть опцію:", reply_markup=main_kb)

@dp.message_handler(commands=["status"])
async def cmd_status(msg: types.Message):
    last = data_store.get("last_stock", {})
    if not last:
        await msg.answer("Ще немає збереженого стоку.")
    else:
        txt = "\n".join(
            f"{sec}: {len(items)} позицій (останнє оновлення в пам'яті)"
            for sec, items in last.items()
        )
        await msg.answer(txt)

@dp.message_handler(lambda m: m.text == "🔍 Подивитись сток зараз")
async def show_stock(msg: types.Message):
    payload = await fetch_stock()
    if payload["data"] == list(map(lambda x: {"section": x["section"], "items": data_store["last_stock"].get(x["section"].split()[0], [])}, payload["data"])):
        await msg.answer(f"Сток ще не оновлено (останнє оновлення: {payload['timestamp']})")
    else:
        txt = []
        for sec in payload["data"]:
            txt.append(f"📦 *{sec['section']}*:\n" +
                       "\n".join(f"- {it['name']}: {it['quantity']}" for it in sec["items"]))
        await msg.answer("\n\n".join(txt), parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🚫 Увімкнути/Вимкнути трекінг")
async def toggle_all(msg: types.Message):
    uid = str(msg.from_user.id)
    user = data_store["users"][uid]
    user["enabled"] = not user.get("enabled", True)
    save_data(data_store)
    status = "ввімкнено" if user["enabled"] else "вимкнено"
    await msg.answer(f"Трекінг {status}.", reply_markup=main_kb)

@dp.message_handler(lambda m: m.text == "⚙️ Настроїти трекінг")
async def config_start(msg: types.Message):
    uid = str(msg.from_user.id)
    data_store["users"].setdefault(uid, {"enabled": True})
    save_data(data_store)
    # Починаємо з першої категорії
    await msg.answer("Оберіть категорію:", reply_markup=get_tracking_markup("SEEDS", data_store["users"][uid]))

@dp.message_handler(lambda m: m.text and (m.text.startswith("✅") or m.text.startswith("❌")))
async def config_toggle_item(msg: types.Message):
    uid = str(msg.from_user.id)
    text = msg.text[2:].strip()
    # Визначимо секцію за активним меню (можна зберігати останню в сесії; для простоти — за списком)
    for cat in ITEM_CATEGORIES:
        if text in ITEM_CATEGORIES[cat]:
            prefs = data_store["users"][uid].setdefault(cat, {})
            prefs[text] = not prefs.get(text, False)
            save_data(data_store)
            await msg.answer(f"{'Відстежується' if prefs[text] else 'Відстеження зупинено'}: {text}",
                             reply_markup=get_tracking_markup(cat, data_store["users"][uid]))
            return

@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def go_back(msg: types.Message):
    await msg.answer("Головне меню:", reply_markup=main_kb)

# --- Старт фонових тасків ---
async def on_startup(dp):
    for section in POLL_INTERVALS:
        asyncio.create_task(check_updates_for(section))

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)