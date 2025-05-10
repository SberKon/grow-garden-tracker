import json
import asyncio
import aiohttp
import logging
import os
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

# Constants
API_URL = "https://stock-tracker-iota-steel.vercel.app/api/garden"
TRACKABLE_ITEMS = {
    'SEEDS': ['Carrot', 'Strawberry', 'Blueberry', 'Orange Tulip', 'Tomato', 'Corn', 
              'Daffodil', 'Watermelon', 'Pumpkin', 'Apple', 'Bamboo', 'Coconut', 
              'Cactus', 'Dragon Fruit', 'Mango', 'Grape', 'Mushroom', 'Pepper'],
    'GEAR': ['Watering Can', 'Trowel', 'Basic Sprinkler', 'Advanced Sprinkler',
             'Godly Sprinkler', 'Lightning Rod', 'Master Sprinkler'],
    'EGG': ['Common Egg', 'Uncommon Egg', 'Rare Egg', 'Legendary Egg', 'Bug Egg']
}

class GardenBot:
    def __init__(self):
        self.last_stock = None
        self.users = self.load_users()
        self.admin_id = os.environ.get('ADMIN_ID')  # Get admin ID from environment
        if not self.admin_id:
            logging.warning("ADMIN_ID environment variable is not set")
        self.notification_messages = {}

    def load_users(self):
        try:
            with open('users.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_users(self):
        with open('users.json', 'w') as f:
            json.dump(self.users, f)

    def get_user_data(self, user_id):
        str_id = str(user_id)
        if str_id not in self.users:
            self.users[str_id] = {
                'tracking_enabled': True,
                'tracked_items': {category: [] for category in TRACKABLE_ITEMS}
            }
            self.save_users()
        return self.users[str_id]

    async def fetch_stock(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as response:
                return await response.json()

    def create_main_menu(self):
        user_data = self.get_user_data(self.current_user_id)
        tracking_status = "🟢 Tracking ON" if user_data['tracking_enabled'] else "🔴 Tracking OFF"
        
        keyboard = [
            [InlineKeyboardButton("🔍 View Current Stock", callback_data="view_stock")],
            [InlineKeyboardButton("⚙️ Configure Tracking", callback_data="config_tracking")],
            [InlineKeyboardButton(tracking_status, callback_data="toggle_tracking")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_stock_view(self, stock_data):
        timestamp = stock_data.get('timestamp', 'unknown time')
        text = ""
        
        # Add warning if stock might be outdated
        current_minute = datetime.now().minute
        is_update_time = current_minute % 5 == 0 or current_minute % 30 == 0
        
        if is_update_time:
            text += "⚠️ WARNING: Stock data might be outdated!\n\n"
        
        text += f"Current Stock (from {timestamp}):\n\n"
        for section in stock_data['data']:
            text += f"📦 {section['section']}:\n"
            for item in section['items']:
                text += f"• {item['name']} - {item['quantity']}\n"
            text += "\n"
        
        keyboard = [[InlineKeyboardButton("« Back", callback_data="main_menu"),
                    InlineKeyboardButton("↻ Refresh", callback_data="view_stock")]]
        return text, InlineKeyboardMarkup(keyboard)

    def create_tracking_menu(self, category):
        user_data = self.get_user_data(self.current_user_id)
        keyboard = []
        current_row = []
        
        # Add items in rows of 2
        for item in TRACKABLE_ITEMS[category]:
            status = "✅" if item in user_data['tracked_items'][category] else "❌"
            current_row.append(InlineKeyboardButton(
                f"{status} {item}",
                callback_data=f"track_{category}_{item}"
            ))
            
            if len(current_row) == 2:  # When row has 2 items
                keyboard.append(current_row)
                current_row = []
        
        # Add remaining items if any
        if current_row:
            keyboard.append(current_row)
        
        # Add category navigation row with ←→ arrows
        categories = list(TRACKABLE_ITEMS.keys())
        current_idx = categories.index(category)
        prev_category = categories[(current_idx - 1) % len(categories)]
        next_category = categories[(current_idx + 1) % len(categories)]
        
        keyboard.append([ 
            InlineKeyboardButton("←", callback_data=f"category_{prev_category}"),
            InlineKeyboardButton(f"{category}", callback_data="none"),
            InlineKeyboardButton("→", callback_data=f"category_{next_category}")
        ])
        
        keyboard.append([InlineKeyboardButton("« Back", callback_data="main_menu")])
        return InlineKeyboardMarkup(keyboard)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.current_user_id = update.effective_user.id
        await update.message.reply_text(
            "Welcome to Garden Stock Tracker! 🌱\n\n"
            "Features:\n"
            "• View current stock items\n"
            "• Track specific items\n"
            "• Get notifications when tracked items appear\n"
            "• Toggle tracking on/off\n\n"
            "Use /menu to start tracking!"
        )

    async def menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.current_user_id = update.effective_user.id
        await update.message.reply_text(
            "━━━━━ MENU ━━━━━\n\n"
            "Choose an option:",
            reply_markup=self.create_main_menu()
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        self.current_user_id = query.from_user.id
        await query.answer()

        if query.data == "none":
            return

        if query.data == "main_menu":
            await query.edit_message_text(
                "━━━━━ MENU ━━━━━\n\n"
                "Choose an option:",
                reply_markup=self.create_main_menu()
            )
            return

        if query.data == "view_stock":
            if self.last_stock:
                text, markup = self.create_stock_view(self.last_stock)
                await query.edit_message_text(
                    "━━━━━━ STOCK ━━━━━━\n\n" + text,
                    reply_markup=markup
                )
            else:
                await query.edit_message_text(
                    "Loading stock data...",
                    reply_markup=self.create_main_menu()
                )

        elif query.data == "config_tracking":
            await query.edit_message_text(
                "━━━━  TRAKING SETTINGS  ━━━━\n\n"
                "Choose your items:",
                reply_markup=self.create_tracking_menu("SEEDS")
            )

        elif query.data.startswith("category_"):
            category = query.data.split("_")[1]
            await query.edit_message_text(
                "━━━━  TRAKING SETTINGS  ━━━━\n\n"
                "Choose your items:",
                reply_markup=self.create_tracking_menu(category)
            )

        elif query.data.startswith("track_"):
            _, category, item = query.data.split("_", 2)
            user_data = self.get_user_data(self.current_user_id)
            if item in user_data['tracked_items'][category]:
                user_data['tracked_items'][category].remove(item)
            else:
                user_data['tracked_items'][category].append(item)
            self.save_users()
            await query.edit_message_text(
                "━━━━  TRAKING SETTINGS  ━━━━\n\n"
                "Choose your items:",
                reply_markup=self.create_tracking_menu(category)
            )

        elif query.data == "toggle_tracking":
            user_data = self.get_user_data(self.current_user_id)
            was_enabled = user_data['tracking_enabled']
            user_data['tracking_enabled'] = not was_enabled
            self.save_users()

            # Якщо трекінг включили і є збережений сток
            if not was_enabled and user_data['tracking_enabled'] and self.last_stock:
                # Збираємо всі доступні предмети
                available_items = []
                for section in self.last_stock['data']:
                    category = section['section'].split()[0]
                    tracked_items = user_data['tracked_items'][category]
                    
                    for item in section['items']:
                        if item['name'] in tracked_items:
                            available_items.append({
                                'name': item['name'],
                                'category': category,
                                'quantity': item['quantity']
                            })
                
                # Відправляємо повідомлення по одному з невеликою затримкою
                if available_items:
                    await context.bot.send_message(
                        chat_id=query.from_user.id,
                        text="🔔 Currently available tracked items:"
                    )
                    
                    for item in available_items:
                        await context.bot.send_message(
                            chat_id=query.from_user.id,
                            text=f"✅ {item['name']} in {item['category']} - {item['quantity']} (currently available)"
                        )
                        await asyncio.sleep(0.1)  # Зменшена затримка

            # Оновлюємо меню
            await query.edit_message_text(
                "━━━━━ MENU ━━━━━\n\n"
                "Choose an option:",
                reply_markup=self.create_main_menu()
            )

    async def check_stock_updates(self, context: Application):
        while True:
            try:
                now = datetime.now()
                current_minute = now.minute
                
                # Перевірка чи це час оновлення (кожні 5 хвилин)
                if current_minute % 5 == 0 and now.second == 0:
                    logging.info(f"Scheduled update check at {now.strftime('%H:%M:%S')}")
                    
                    # Робимо 3 спроби перевірки з інтервалом 30 секунд
                    for attempt in range(3):
                        await asyncio.sleep(30)
                        check_time = datetime.now()
                        logging.info(f"Update attempt {attempt + 1} at {check_time.strftime('%H:%M:%S')}")
                        
                        new_stock = await self.fetch_stock()
                        
                        # Якщо це перший запуск - зберігаємо сток і чекаємо наступного оновлення
                        if self.last_stock is None:
                            self.last_stock = new_stock
                            logging.info("First run - saving initial stock")
                            break
                            
                        # Порівнюємо весь сток цілком
                        if new_stock != self.last_stock:
                            logging.info("Stock update detected")
                            # Перевіряємо чи змінився timestamp
                            if new_stock.get('timestamp') != self.last_stock.get('timestamp'):
                                await self.process_stock_update(new_stock, context, check_time)
                                self.last_stock = new_stock
                                break
                            else:
                                logging.info("Same timestamp, ignoring update")
                        
                        if attempt < 2:
                            logging.info("No changes, waiting for next attempt")
                        else:
                            logging.info("No changes after all attempts")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logging.error(f"Error in stock update: {e}")
                await asyncio.sleep(60)

    async def process_stock_update(self, new_stock, context: Application, update_time):
        if not self.last_stock:
            self.last_stock = new_stock
            return

        current_minute = update_time.minute
        is_egg_update = current_minute in [0, 30]  # Перевіряємо чи це точний час для EGG

        # Для кожного користувача
        for user_id, user_data in self.users.items():
            if not user_data['tracking_enabled']:
                continue

            str_user_id = str(user_id)
            
            # Видаляємо старі повідомлення для SEEDS і GEAR
            if str_user_id in self.notification_messages:
                for msg_id in self.notification_messages[str_user_id].get('seeds_gear', []):
                    try:
                        await context.bot.delete_message(chat_id=user_id, message_id=msg_id)
                    except Exception:
                        pass  # Ігноруємо помилки при видаленні
                # Очищаємо список повідомлень для SEEDS і GEAR
                self.notification_messages[str_user_id]['seeds_gear'] = []

            # Видаляємо старі повідомлення для EGG якщо це час оновлення EGG
            if is_egg_update and str_user_id in self.notification_messages:
                for msg_id in self.notification_messages[str_user_id].get('egg', []):
                    try:
                        await context.bot.delete_message(chat_id=user_id, message_id=msg_id)
                    except Exception:
                        pass
                # Очищаємо список повідомлень для EGG
                self.notification_messages[str_user_id]['egg'] = []

            # Ініціалізуємо структуру для нових повідомлень
            if str_user_id not in self.notification_messages:
                self.notification_messages[str_user_id] = {'seeds_gear': [], 'egg': []}

            # Відправляємо нові повідомлення
            for section in new_stock['data']:
                category = section['section'].split()[0]
                
                # Пропускаємо EGG якщо це не час оновлення
                if category == 'EGG' and not is_egg_update:
                    continue
                
                tracked_items = user_data['tracked_items'][category]
                if not tracked_items:
                    continue

                for item in section['items']:
                    if item['name'] in tracked_items:
                        try:
                            message = await context.bot.send_message(
                                chat_id=user_id,
                                text=f"✅ {item['name']} in {category} - {item['quantity']}"
                            )
                            # Зберігаємо ID повідомлення
                            if category == 'EGG':
                                self.notification_messages[str_user_id]['egg'].append(message.message_id)
                            else:
                                self.notification_messages[str_user_id]['seeds_gear'].append(message.message_id)
                            
                            await asyncio.sleep(0.1)  # Зменшена затримка
                        except Exception as e:
                            logging.error(f"Failed to send notification: {e}")

    async def force_save_stock(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to force save current stock"""
        user_id = str(update.effective_user.id)
        
        if user_id != self.admin_id:
            await update.message.reply_text("⛔ Access denied")
            return
            
        try:
            new_stock = await self.fetch_stock()
            self.last_stock = new_stock
            await update.message.reply_text(
                f"✅ Stock saved successfully!\n"
                f"Timestamp: {new_stock.get('timestamp', 'unknown')}"
            )
            logging.info(f"Stock forcefully saved by admin at {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
            logging.error(f"Error in force_save_stock: {e}")

def main():
    bot = GardenBot()
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
    
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("menu", bot.menu))
    application.add_handler(CommandHandler("save_stock", bot.force_save_stock))  # New handler
    application.add_handler(CallbackQueryHandler(bot.button_handler))
    
    # Start the stock update loop
    application.job_queue.run_once(
        lambda ctx: asyncio.create_task(bot.check_stock_updates(ctx)),
        when=0
    )

    application.run_polling()

if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    main()