import os
import asyncio
import json
import logging

import aiohttp
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ——— Налаштування логування ———
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ——— Конфіг ———
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

# ——— Ініціалізація бота ———
bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher(bot)

# ——— Утиліти для JSON-збереження ———
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.info("Не знайдено %s — буде створено новий.", DATA_FILE)
        return {"users": {}, "last_stock": {}}
    except json.JSONDecodeError as e:
        logger.error("Помилка розбору %s: %s", DATA_FILE, e)
        return {"users": {}, "last_stock": {}}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Не вдалось зберегти %s: %s", DATA_FILE, e)

data_store = load_data()

# ——— Меню ———
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

# ——— Запит до API ———
async def fetch_stock():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, timeout=10) as resp:
                return await resp.json()
    except Exception as e:
        logger.error("fetch_stock помилка: %s", e)
        return None

# ——— Фонова перевірка оновлень ———
async def check_updates_for(section):
    while True:
        payload = await fetch_stock()
        if not payload:
            await asyncio.sleep(60)
            continue

        try:
            new_section = next(sec for sec in payload["data"] if sec["section"].startswith(section))
        except StopIteration:
            logger.error("Не знайдено секцію %s в API", section)
            await asyncio.sleep(60)
            continue

        prev_items = data_store["last_stock"].get(section)
        if prev_items != new_section["items"]:
            logger.info("Оновлення %s: %s → %s", section, prev_items, new_section["items"])
            data_store["last_stock"][section] = new_section["items"]
            save_data(data_store)

            # Розсилка повідомлень юзерам
            for user_id, prefs in data_store["users"].items():
                if prefs.get("enabled") and prefs.get(section):
                    for it in new_section["items"]:
                        if prefs[section].get(it["name"]):
                            await bot.send_message(
                                user_id,
                                f"✅ **{it['name']}** в {section.split()[0]} стоку: {it['quantity']}",
                                parse_mode="Markdown"
                            )
        await asyncio.sleep(POLL_INTERVALS[section])

# ——— Хендлери команд і меню ———
@dp.message_handler(commands=["start"])
async def cmd_start(msg: types.Message):
    uid = str(msg.from_user.id)
    data_store["users"].setdefault(uid, {"enabled": True})
    save_data(data_store)
    await msg.answer("Вітаю! Виберіть опцію:", reply_markup=main_kb)

@dp.message_handler(commands=["status"])
async def cmd_status(msg: types.Message):
    last = data_store.get("last_stock", {})
    if not last:
        await msg.answer("Ще немає збереженого стоку.")
    else:
        txt = "\n".join(
            f"{sec}: {len(items)} позицій" for sec, items in last.items()
        )
        await msg.answer(txt)

@dp.message_handler(lambda m: m.text == "🔍 Подивитись сток зараз")
async def show_stock(msg: types.Message):
    payload = await fetch_stock()
    if not payload:
        await msg.answer("Не вдалося отримати дані зі API.")
        return

    # Перевірка, чи є нові дані
    snapshot = [
        {"section": x["section"], "items": data_store["last_stock"].get(x["section"].split()[0], [])}
        for x in payload["data"]
    ]
    if payload["data"] == snapshot:
        await msg.answer(f"Сток ще не оновлено (останнє оновлення: {payload['timestamp']})")
    else:
        txt = []
        for sec in payload["data"]:
            txt.append(f"📦 *{sec['section']}*:\n" + "\n".join(f"- {it['name']}: {it['quantity']}" for it in sec["items"]))
        await msg.answer("\n\n".join(txt), parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🚫 Увімкнути/Вимкнути трекінг")
async def toggle_all(msg: types.Message):
    uid = str(msg.from_user.id)
    user = data_store["users"].setdefault(uid, {"enabled": True})
    user["enabled"] = not user.get("enabled", True)
    save_data(data_store)
    status = "увімкнено" if user["enabled"] else "вимкнено"
    await msg.answer(f"Трекінг {status}.", reply_markup=main_kb)

@dp.message_handler(lambda m: m.text == "⚙️ Настроїти трекінг")
async def config_start(msg: types.Message):
    uid = str(msg.from_user.id)
    data_store["users"].setdefault(uid, {"enabled": True})
    save_data(data_store)
    await msg.answer("Оберіть категорію:", reply_markup=get_tracking_markup("SEEDS", data_store["users"][uid]))

@dp.message_handler(lambda m: m.text and (m.text.startswith("✅") or m.text.startswith("❌")))
async def config_toggle_item(msg: types.Message):
    uid = str(msg.from_user.id)
    item_name = msg.text[2:].strip()
    for cat in ITEM_CATEGORIES:
        if item_name in ITEM_CATEGORIES[cat]:
            prefs = data_store["users"][uid].setdefault(cat, {})
            prefs[item_name] = not prefs.get(item_name, False)
            save_data(data_store)
            state = "Відстежується" if prefs[item_name] else "Відстеження зупинено"
            await msg.answer(f"{state}: {item_name}", reply_markup=get_tracking_markup(cat, data_store["users"][uid]))
            return

@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def go_back(msg: types.Message):
    await msg.answer("Головне меню:", reply_markup=main_kb)

# ——— Старт фонових тасків при запуску ———
async def on_startup(dp):
    logger.info("Бот стартує, запускаю фонові перевірки…")
    for section in POLL_INTERVALS:
        asyncio.create_task(check_updates_for(section))
        logger.info("  – %s", section)

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)
