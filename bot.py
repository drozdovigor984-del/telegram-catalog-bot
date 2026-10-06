import html
import json
import os
import threading
from datetime import datetime

import telebot
from telebot import types

# ---------- Токен и ID владельца ----------
# На сервере они лежат в переменных BOT_TOKEN и OWNER_ID.
# На твоём компьютере берутся из файла config.py.

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    from config import TOKEN

OWNER_ID = os.environ.get("OWNER_ID")
if not OWNER_ID:
    try:
        from config import OWNER_ID
    except ImportError:
        OWNER_ID = None
OWNER_ID = int(OWNER_ID) if OWNER_ID else None

bot = telebot.TeleBot(TOKEN)


# ---------- Настройки (меняй под любого заказчика) ----------

SHOP_NAME = "Кофейня «Зерно»"
ADDRESS = "ул. Центральная, 5"
PHONE = "+7 900 000-00-00"
HOURS = "Ежедневно 8:00–21:00"
CURRENCY = "₽"

# Каталог: категории, а в них товары. Меняй названия, цены и описания.
CATALOG = [
    {
        "name": "☕ Кофе",
        "items": [
            {"name": "Эспрессо", "price": 150, "desc": "Классический крепкий кофе, 30 мл."},
            {"name": "Капучино", "price": 220, "desc": "Эспрессо с нежной молочной пенкой, 250 мл."},
            {"name": "Латте", "price": 240, "desc": "Много молока, мягкий вкус, 300 мл."},
            {"name": "Раф с ванилью", "price": 280, "desc": "Сливочный кофе с ванильным сиропом, 300 мл."},
        ],
    },
    {
        "name": "🥐 Выпечка",
        "items": [
            {"name": "Круассан", "price": 130, "desc": "Хрустящий, со сливочным маслом."},
            {"name": "Булочка с корицей", "price": 120, "desc": "Свежая, с сахарной глазурью."},
            {"name": "Сэндвич с ветчиной", "price": 210, "desc": "Ветчина, сыр, свежие овощи."},
        ],
    },
    {
        "name": "🍰 Десерты",
        "items": [
            {"name": "Чизкейк", "price": 260, "desc": "Нью-Йорк, с ягодным соусом."},
            {"name": "Тирамису", "price": 280, "desc": "Классический итальянский десерт."},
            {"name": "Макарон", "price": 90, "desc": "Французское миндальное печенье, на выбор вкусы."},
        ],
    },
]


# ---------- Корзины и заказы ----------

ORDERS_FILE = "orders.json"
lock = threading.Lock()
carts = {}  # user_id -> {"0|1": количество}. Корзина живёт, пока бот включён.


def load_orders():
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_orders(orders):
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)


def add_order(user, name, phone, comment, lines, total):
    with lock:
        orders = load_orders()
        order = {
            "id": max([o["id"] for o in orders], default=0) + 1,
            "user_id": user.id,
            "name": name,
            "phone": phone,
            "comment": comment,
            "items": lines,
            "total": total,
            "created": datetime.now().strftime("%d.%m.%Y %H:%M"),
        }
        orders.append(order)
        save_orders(orders)
        return order


def get_item(cat_index, item_index):
    return CATALOG[cat_index]["items"][item_index]


def cart_of(user_id):
    return carts.setdefault(user_id, {})


def cart_lines(user_id):
    """Возвращает список строк корзины и общую сумму."""
    lines = []
    total = 0
    for key, qty in cart_of(user_id).items():
        c, i = map(int, key.split("|"))
        item = get_item(c, i)
        lines.append({"key": key, "name": item["name"], "price": item["price"], "qty": qty})
        total += item["price"] * qty
    return lines, total


def cart_count(user_id):
    return sum(cart_of(user_id).values())


# ---------- Кнопки ----------

def main_menu(user_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📋 Каталог", callback_data="catalog"))
    n = cart_count(user_id)
    cart_text = f"🛒 Корзина ({n})" if n else "🛒 Корзина"
    markup.add(types.InlineKeyboardButton(cart_text, callback_data="cart"))
    markup.add(types.InlineKeyboardButton("💬 Задать вопрос", callback_data="ask"))
    markup.add(types.InlineKeyboardButton("ℹ️ О нас и контакты", callback_data="about"))
    return markup


def back_to_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏠 Меню", callback_data="menu"))
    return markup


def show(call, text, markup):
    """Заменяет текст сообщения с кнопками на новый."""
    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=markup,
        )
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" not in str(e):
            raise


def notify_owner(text):
    if OWNER_ID:
        try:
            bot.send_message(OWNER_ID, text, parse_mode="HTML")
        except Exception as e:
            print("Не удалось отправить уведомление владельцу:", e)


def user_link(user_id, name):
    """Кликабельное имя клиента: владелец нажмёт и сразу откроет чат с ним."""
    return f'<a href="tg://user?id={user_id}">{html.escape(name)}</a>'


# ---------- Команды ----------

def send_menu(chat_id, user_id):
    bot.send_message(
        chat_id,
        f"Здравствуйте! 👋 Это бот — <b>{html.escape(SHOP_NAME)}</b>.\n\n"
        "Выберите товары в каталоге, добавьте в корзину и оформите заказ.",
        parse_mode="HTML",
        reply_markup=main_menu(user_id),
    )


@bot.message_handler(commands=["start"])
def start(message):
    send_menu(message.chat.id, message.from_user.id)


@bot.message_handler(commands=["id"])
def send_id(message):
    # Нужна, чтобы владелец узнал свой Telegram ID и вписал его в config.py
    bot.send_message(message.chat.id, f"Ваш Telegram ID: {message.from_user.id}")


@bot.message_handler(commands=["admin"])
def admin(message):
    if message.from_user.id != OWNER_ID:
        return
    orders = load_orders()[-10:]
    if not orders:
        bot.send_message(message.chat.id, "Заказов пока нет.")
        return
    lines = ["📋 <b>Последние заказы:</b>\n"]
    for o in reversed(orders):
        goods = ", ".join(f"{i['name']} ×{i['qty']}" for i in o["items"])
        lines.append(
            f"<b>№{o['id']}</b> · {o['created']}\n"
            f"{html.escape(o['name'])}, {html.escape(o['phone'])}\n"
            f"{html.escape(goods)}\n"
            f"Итого: {o['total']} {CURRENCY}\n"
        )
    bot.send_message(message.chat.id, "\n".join(lines), parse_mode="HTML")


# ---------- Оформление заказа (шаги, где клиент пишет текст) ----------

def is_command(message):
    """Если клиент во время оформления нажал /start или другую команду — прерываем."""
    return message.text and message.text.startswith("/")


def cancel_flow(message):
    bot.send_message(message.chat.id, "Оформление отменено.", reply_markup=types.ReplyKeyboardRemove())
    send_menu(message.chat.id, message.from_user.id)


def ask_name(message):
    if is_command(message):
        return cancel_flow(message)
    if not message.text or len(message.text.strip()) < 2:
        msg = bot.send_message(message.chat.id, "Напишите, пожалуйста, ваше имя текстом:")
        return bot.register_next_step_handler(msg, ask_name)
    name = message.text.strip()[:60]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📱 Отправить мой номер", request_contact=True))
    msg = bot.send_message(
        message.chat.id,
        "Оставьте номер телефона: нажмите кнопку ниже или напишите номер сообщением.",
        reply_markup=markup,
    )
    bot.register_next_step_handler(msg, ask_phone, name)


def ask_phone(message, name):
    if is_command(message):
        return cancel_flow(message)
    if message.contact:
        phone = message.contact.phone_number
        if not phone.startswith("+"):
            phone = "+" + phone  # Telegram присылает номер без плюса
    else:
        phone = (message.text or "").strip()
    digits = [ch for ch in phone if ch.isdigit()]
    if len(digits) < 7:
        msg = bot.send_message(message.chat.id, "Не похоже на номер. Напишите его ещё раз, например +7 900 123-45-67:")
        return bot.register_next_step_handler(msg, ask_phone, name)
    msg = bot.send_message(
        message.chat.id,
        "Комментарий к заказу (адрес, удобное время и т.д.). Если не нужен, напишите «-».",
        reply_markup=types.ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, finish_order, name, phone)


def finish_order(message, name, phone):
    if is_command(message):
        return cancel_flow(message)
    comment = (message.text or "-").strip()[:300]
    user = message.from_user
    lines, total = cart_lines(user.id)
    if not lines:
        bot.send_message(message.chat.id, "Корзина пуста, заказ не создан.")
        return send_menu(message.chat.id, user.id)

    order = add_order(user, name, phone, comment, lines, total)
    carts[user.id] = {}

    goods = "\n".join(f"• {l['name']} × {l['qty']} = {l['price'] * l['qty']} {CURRENCY}" for l in lines)
    bot.send_message(
        message.chat.id,
        f"✅ <b>Заказ №{order['id']} принят!</b>\n\n{html.escape(goods)}\n\n"
        f"Итого: <b>{total} {CURRENCY}</b>\n\n"
        f"Мы свяжемся с вами по номеру {html.escape(phone)}.\n"
        f"📍 {html.escape(ADDRESS)}",
        parse_mode="HTML",
        reply_markup=back_to_menu(),
    )
    notify_owner(
        f"🔔 <b>Новый заказ №{order['id']}</b>\n"
        f"{user_link(user.id, name)}, {html.escape(phone)}\n\n"
        f"{html.escape(goods)}\n\n"
        f"Итого: {total} {CURRENCY}\n"
        f"Комментарий: {html.escape(comment)}"
    )


def receive_question(message):
    if is_command(message):
        return cancel_flow(message)
    if not message.text:
        msg = bot.send_message(message.chat.id, "Напишите вопрос текстом:")
        return bot.register_next_step_handler(msg, receive_question)
    user = message.from_user
    bot.send_message(
        message.chat.id,
        "✅ Спасибо! Мы получили ваш вопрос и скоро ответим.",
        reply_markup=back_to_menu(),
    )
    notify_owner(
        f"📩 <b>Вопрос от клиента</b>\n{user_link(user.id, user.first_name or 'Клиент')}\n\n"
        f"{html.escape(message.text[:1000])}"
    )


# ---------- Нажатия на кнопки ----------

def cart_markup(user_id):
    lines, total = cart_lines(user_id)
    markup = types.InlineKeyboardMarkup()
    for l in lines:
        markup.row(
            types.InlineKeyboardButton("➖", callback_data=f"dec|{l['key']}"),
            types.InlineKeyboardButton(f"{l['name']} × {l['qty']}", callback_data="noop"),
            types.InlineKeyboardButton("➕", callback_data=f"inc|{l['key']}"),
        )
    markup.add(types.InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout"))
    markup.add(types.InlineKeyboardButton("🗑 Очистить", callback_data="clear"),
               types.InlineKeyboardButton("📋 Каталог", callback_data="catalog"))
    return markup


def show_cart(call):
    user_id = call.from_user.id
    lines, total = cart_lines(user_id)
    if not lines:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📋 Каталог", callback_data="catalog"))
        markup.add(types.InlineKeyboardButton("🏠 Меню", callback_data="menu"))
        show(call, "🛒 Корзина пуста.", markup)
        return
    text = "🛒 <b>Ваша корзина</b>\n\n"
    text += "\n".join(f"• {html.escape(l['name'])} × {l['qty']} = {l['price'] * l['qty']} {CURRENCY}" for l in lines)
    text += f"\n\nИтого: <b>{total} {CURRENCY}</b>"
    show(call, text, cart_markup(user_id))


def show_item(call, c, i):
    item = get_item(c, i)
    in_cart = cart_of(call.from_user.id).get(f"{c}|{i}", 0)
    add_text = f"➕ В корзину (сейчас: {in_cart})" if in_cart else "➕ В корзину"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(add_text, callback_data=f"add|{c}|{i}"))
    n = cart_count(call.from_user.id)
    markup.add(types.InlineKeyboardButton(f"🛒 Корзина ({n})" if n else "🛒 Корзина", callback_data="cart"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"cat|{c}"))
    show(call,
         f"<b>{html.escape(item['name'])}</b>\n{html.escape(item['desc'])}\n\n💰 {item['price']} {CURRENCY}",
         markup)


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data
    user = call.from_user
    toast = None  # короткое всплывающее сообщение для клиента

    if data == "menu":
        show(call, "Выберите действие:", main_menu(user.id))

    elif data == "noop":
        pass

    elif data == "about":
        text = (f"<b>{html.escape(SHOP_NAME)}</b>\n📍 {html.escape(ADDRESS)}\n"
                f"📞 {html.escape(PHONE)}\n🕙 {html.escape(HOURS)}")
        show(call, text, back_to_menu())

    # Список категорий
    elif data == "catalog":
        markup = types.InlineKeyboardMarkup()
        for c, cat in enumerate(CATALOG):
            markup.add(types.InlineKeyboardButton(cat["name"], callback_data=f"cat|{c}"))
        n = cart_count(user.id)
        markup.add(types.InlineKeyboardButton(f"🛒 Корзина ({n})" if n else "🛒 Корзина", callback_data="cart"))
        markup.add(types.InlineKeyboardButton("🏠 Меню", callback_data="menu"))
        show(call, "Выберите категорию:", markup)

    # Товары категории
    elif data.startswith("cat|"):
        c = int(data.split("|")[1])
        markup = types.InlineKeyboardMarkup()
        for i, item in enumerate(CATALOG[c]["items"]):
            markup.add(types.InlineKeyboardButton(
                f"{item['name']} — {item['price']} {CURRENCY}", callback_data=f"item|{c}|{i}"))
        markup.add(types.InlineKeyboardButton("⬅️ Категории", callback_data="catalog"))
        show(call, f"<b>{html.escape(CATALOG[c]['name'])}</b>\nВыберите товар:", markup)

    # Карточка товара
    elif data.startswith("item|"):
        _, c, i = data.split("|")
        show_item(call, int(c), int(i))

    # Добавить в корзину
    elif data.startswith("add|"):
        _, c, i = data.split("|")
        cart = cart_of(user.id)
        key = f"{c}|{i}"
        cart[key] = cart.get(key, 0) + 1
        toast = "Добавлено в корзину ✅"
        show_item(call, int(c), int(i))

    elif data == "cart":
        show_cart(call)

    # Изменить количество в корзине
    elif data.startswith("inc|") or data.startswith("dec|"):
        action, c, i = data.split("|")
        cart = cart_of(user.id)
        key = f"{c}|{i}"
        if key in cart:
            cart[key] += 1 if action == "inc" else -1
            if cart[key] <= 0:
                del cart[key]
        show_cart(call)

    elif data == "clear":
        carts[user.id] = {}
        toast = "Корзина очищена"
        show_cart(call)

    # Начало оформления заказа
    elif data == "checkout":
        if not cart_count(user.id):
            toast = "Корзина пуста"
        else:
            msg = bot.send_message(call.message.chat.id, "Как вас зовут?")
            bot.register_next_step_handler(msg, ask_name)

    # Вопрос владельцу
    elif data == "ask":
        msg = bot.send_message(call.message.chat.id, "Напишите ваш вопрос одним сообщением:")
        bot.register_next_step_handler(msg, receive_question)

    bot.answer_callback_query(call.id, toast)


# ---------- Запуск ----------

if __name__ == "__main__":
    print("Бот-каталог запущен. Нажми Ctrl+C, чтобы остановить.")
    bot.infinity_polling()
