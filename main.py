import os
import random
import asyncio
import aiohttp
import sqlite3
import shutil
import re
import urllib.parse
from pyrogram import Client, filters, types, errors
from pyrogram.errors import SessionPasswordNeeded
from pyrogram.raw import functions, types as raw_types
from pyrogram.errors import RPCError, UserIsBlocked, FloodWait

# --- CONFIGURATION ---
API_ID = 20898349
API_HASH = "9fdb830d1e435b785f536247f49e7d87"
BOT_TOKEN = "8281283287:AAE1Msn2RZKYd1pLS0ZJTyg1wRrfBzObCdg"
ADMIN_IDS = [7450385463, 7563727739, 7875411241]
MERCHANT_KEY = "SDJ6hB8zbfDd6K" # Updated as per your BJS code
LOG_CHANNEL_ID = -1002635720348
DEPOSIT_LOG_ID = -1003798769331 # Admin Log Channel ID
SPAM_APPROVAL = {}

bot = Client("TG_AXX_BOT", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
login_data = {}
user_deposits = {} # Temporary store for UTR and Message IDs

# ================= DATABASE SETUP =================
def get_db():
    return sqlite3.connect("database.db", timeout=30, check_same_thread=False)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0,
        total_spent REAL DEFAULT 0,
        total_deposited REAL DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    session_name TEXT,
    status INTEGER DEFAULT 0,
    country TEXT,
    price REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    password TEXT,
    last_otp TEXT
)""")
    cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("""
CREATE TABLE IF NOT EXISTS country_prices (
    country TEXT PRIMARY KEY,
    price REAL
)
""")
    cur.execute("CREATE TABLE IF NOT EXISTS business_stats (key TEXT PRIMARY KEY, value REAL)")
    cur.execute("INSERT OR IGNORE INTO settings VALUES ('price','100')")
    cur.execute("INSERT OR IGNORE INTO business_stats VALUES ('total_sold',0), ('total_revenue',0), ('total_deposited',0)")
    conn.commit()
    conn.close()

init_db()
BASE_SESSION_DIR = "sessions"
os.makedirs(BASE_SESSION_DIR, exist_ok=True)

# --- DATABASE HELPERS ---
def get_user_data(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT balance, total_spent, total_deposited FROM users WHERE id=?", (user_id,))
    res = cur.fetchone()
    if not res:
        print(f"[GET] Creating user {user_id} on first access")
        cur.execute("INSERT INTO users (id, balance, total_spent, total_deposited) VALUES (?, 0, 0, 0)", (user_id,))
        conn.commit()
        res = (0, 0, 0)
    conn.close()
    return res
def update_user_stats(user_id, balance_delta=0, spent_delta=0, deposit_delta=0):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + ?, total_spent = total_spent + ?, total_deposited = total_deposited + ? WHERE id = ?", (balance_delta, spent_delta, deposit_delta, user_id))
    conn.commit()
    conn.close()

def update_biz_stats(key, amount):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE business_stats SET value = value + ? WHERE key=?", (amount, key))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cur.fetchone()
    conn.close()
    return res[0] if res else "100"

def get_country_price(country):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT price FROM country_prices WHERE country=?", (country,))
    row = cur.fetchone()
    conn.close()
    if row:
        return float(row[0])
    return float(get_setting("price"))  # default fallback


def set_country_price(country, price):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO country_prices (country, price)
    VALUES (?, ?)
    ON CONFLICT(country) DO UPDATE SET price=excluded.price
    """, (country, price))
    conn.commit()
    conn.close()

# --- USER HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_h(c, m):
    get_user_data(m.from_user.id)
    kb = types.ReplyKeyboardMarkup([["🛒 Buy Account", "👤 Profile"], ["💰 Deposit", "📊 My Stats"], ["☎️ Support"]], resize_keyboard=True)
    await m.reply("**👋 Welcome To TG-Kiиg Robot!\n\nThe Most Trusted Place For Telegram Accounts.**", reply_markup=kb)

# --- SUPPORT HANDLER ---
@bot.on_message(filters.regex("☎️ Support") & filters.private)
async def support_h(c, m):
    support_text = (
        "**🟢 TG-Kiиg Support & Relevant Information**\n\n"
        "**⚠️ All Purchases Made Via @sxyaru Are Final — No Refunds Or Replacements Will Be Provided Under Any Circumstances.**"
    )

    # Inline button for one-click contact
    kb = types.InlineKeyboardMarkup([[
        types.InlineKeyboardButton("💬 Support", url="https://t.me/sxyaru")
    ]])

    await m.reply(support_text, reply_markup=kb)

# --- NEW DYNAMIC DEPOSIT SYSTEM (BJS CONVERTED) ---
@bot.on_message(filters.regex("💰 Deposit") & filters.private)
async def deposit_init(c, m):
    uid = m.from_user.id

    # Delete old QR if exists
    old_data = user_deposits.get(uid)
    if old_data and "msg_id" in old_data:
        try:
            await bot.delete_messages(uid, old_data["msg_id"])
        except:
            pass

    upi_id = "nikhil-bby@fam"
    pn = "TGKingRobot"
    tn = "Deposit in TGKingRobot"

    upi_link = f"upi://pay?pa={upi_id}&pn={pn}&tn={urllib.parse.quote(tn)}&am=0&cu=INR"
    qr_image = f"https://api.qrserver.com/v1/create-qr-code/?size=350x350&margin=20&data={urllib.parse.quote(upi_link)}"

    text = (
        "**💰 Deposit Money**\n\n"
        f"**UPI ID:** `{upi_id}`\n"
        f"**Name:** {pn}\n\n"
        "Send **any amount** you want.\n\n"
        "**After successful payment, send screenshot here**\n"
        "(proof from GPay, PhonePe, Paytm etc.)\n\n"
        "Admin will verify and add balance soon."
    )

    sent_msg = await m.reply_photo(
        photo=qr_image,
        caption=text
    )

    user_deposits[uid] = {"msg_id": sent_msg.id}
#ADD_BALANCE
@bot.on_message(filters.command("add") & filters.private)
async def add_balance(c, m):
    if m.from_user.id not in ADMIN_IDS:
        return await m.reply("❌ You are not authorized.")

    try:
        parts = m.text.split()
        if len(parts) != 3:
            return await m.reply("Usage: `/add USER_ID AMOUNT`\nExample: `/add 7450385463 500`")

        target_id = int(parts[1])
        amount = float(parts[2])

        conn = get_db()
        cur = conn.cursor()

        # Check if user exists
        cur.execute("SELECT id FROM users WHERE id = ?", (target_id,))
        if not cur.fetchone():
            print(f"[ADD] Creating new user {target_id}")
            cur.execute(
                "INSERT INTO users (id, balance, total_spent, total_deposited) VALUES (?, ?, ?, ?)",
                (target_id, 0, 0, 0)
            )

        # Update balance
        cur.execute(
            "UPDATE users SET balance = balance + ?, total_deposited = total_deposited + ? WHERE id = ?",
            (amount, amount, target_id)
        )

        rows_affected = cur.rowcount
        print(f"[ADD] Rows updated for user {target_id}: {rows_affected}")

        conn.commit()
        conn.close()

        if rows_affected == 0:
            return await m.reply(f"⚠️ No user found with ID {target_id} — please ask them to start the bot first (/start)")

        # Optional: update business stats
        update_biz_stats("total_deposited", amount)

        await m.reply(f"✅ Successfully added ₹{amount} to user ID {target_id}")

        # Notify user
        try:
            await bot.send_message(
                target_id,
                f"🎉 **Deposit Successful!**\n\n"
                f"₹{amount} has been added to your balance.\n"
                "You can now use it to buy accounts."
            )
        except:
            await m.reply(f"⚠️ Could not notify user {target_id} (they may have blocked the bot)")

    except ValueError:
        await m.reply("❌ Invalid format. User ID and amount must be numbers.")
    except Exception as e:
        await m.reply(f"Error: {str(e)}")

#VERIFY
@bot.on_message(filters.photo & filters.private)
async def handle_screenshot(c, m):
    uid = m.from_user.id

    # Optional check if user is in deposit flow
    if uid not in user_deposits:
        return await m.reply("Please click 💰 Deposit first to start payment process.")

    username = f"@{m.from_user.username}" if m.from_user.username else "No username"

    caption = (
        f"💸 **New Deposit Screenshot**\n\n"
        f"👤 **User:** {m.from_user.first_name}\n"
        f"🆔 **User ID:** `{uid}`\n"
        f"🔗 **Username:** {username}\n\n"
        "Reply to this message with:\n"
        f"`/add {uid} AMOUNT`   → to add balance\n"
        f"`/reject {uid}`       → to reject"
    )

    # Forward the photo first
    forwarded_msg = await m.forward(ADMIN_ID)

    # Then send the caption as a reply to the forwarded message
    await bot.send_message(
        ADMIN_ID,
        caption,
        reply_to_message_id=forwarded_msg.id
    )

    # Tell user it's received
    await m.reply(
        "✅ **Screenshot received!**\n"
        "Your payment proof has been sent to admin.\n"
        "Please wait, balance will be added after verification (usually within few minutes)."
    )

    # Optional: store forwarded message ID
    user_deposits[uid]["proof_msg_id"] = forwarded_msg.id
@bot.on_callback_query(filters.regex(r"^check_pay_"))
async def verify_payment(c, q):
    uid = q.from_user.id
    utr = q.data.split("_")[2]

    # Projectoid API URL
    url = f"https://api.projectoid.in/v2/ledger/paytm/?MERCHANT_KEY={MERCHANT_KEY}&TRANSACTION={utr}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()

            # API Response handling (BJS logic)
            res_data = data.get("result", {})
            status = res_data.get("STATUS")

            if status == "TXN_SUCCESS":
                amount = float(res_data.get("TXNAMOUNT", 0))
                order_id = res_data.get("ORDERID", "N/A")

                # Check if already processed (Double protection)
                if user_deposits.get(uid, {}).get("done"):
                    return await q.answer("**⚠️ Deposit Already Credited!**", show_alert=True)

                # Update Database
                bal_before, _, _ = get_user_data(uid)
                update_user_stats(uid, balance_delta=amount, deposit_delta=amount)
                update_biz_stats("total_deposited", amount)

                # Mark as done in temp session
                user_deposits[uid]["done"] = True

                # Delete QR Message
                try:
                    await bot.delete_messages(uid, q.message.id)
                except: pass

                # Success Message to User
                await bot.send_message(
                    uid,
                    f"✅ `₹{amount:.2f}` **Has Been Added To Your Balance!**\n"
                    f"💰 **Old Balance:** `₹{bal_before:.2f}`\n"
                    f"💸 **New Balance:** `₹{bal_before + amount:.2f}`"
                )

                # Admin Log
                username = f"@{q.from_user.username}" if q.from_user.username else "No Username"
                log_text = (
                    f"💸 **New Deposit Received!**\n\n"
                    f"👤 **Name:** **{q.from_user.first_name}**\n"
                    f"🆔 **User ID:** `{uid}`\n"
                    f"🔗 **Username:** **{username}**\n\n"
                    f"💰 **Old Balance:** `₹{bal_before:.2f}`\n"
                    f"➕ **Added:** `₹{amount:.2f}`\n"
                    f"💸 **New Balance:** `₹{bal_before + amount:.2f}`\n"
                    f"📌 **TXN ID:** `{order_id}`"
                )
                await bot.send_message(ADMIN_ID, log_text)

            else:
                await q.answer("❌ Payment Not Detected! Please Do Payment First.", show_alert=True)

# --- RE-INTEGRATING PROFILE & STATS ---
@bot.on_message(filters.regex("👤 Profile") & filters.private)
async def profile_h(c, m):
    uid = m.from_user.id
    data = get_user_data(uid)
    print(f"[PROFILE] User {uid} balance from DB: ₹{data[0]}")
    profile_text = f"👤 **Name:** {m.from_user.first_name}\n🆔 **User ID:** `{uid}`\n**💸 Balance:** ₹{data[0]:.2f}"
    await m.reply(profile_text)

@bot.on_message(filters.regex("📊 My Stats") & filters.private)
async def user_stats_h(c, m):
    uid = m.from_user.id
    bal, spent, dep = get_user_data(uid)
    conn = get_db(); cur = conn.cursor()
    count = cur.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (uid,)).fetchone()[0]
    conn.close()
    text = (f"**📊 Your Statistics**\n\n**🛒 Accounts Bought:** `{count}`\n**💸 Total Spent:** `₹{spent:.2f}`\n**💳 Total Deposited:** `₹{dep:.2f}`")
    kb = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("📜 View Purchase History", callback_data="user_history")]])
    await m.reply(text, reply_markup=kb)

@bot.on_message(filters.regex("🛒 Buy Account") & filters.private)
async def buy_acc_start(c, m):
    uid = m.from_user.id

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT session_name FROM orders WHERE user_id = ? AND status = 0",
        (uid,)
    )
    existing_order = cur.fetchone()
    conn.close()

    if existing_order:
        return await m.reply("⚠️ **You Have A Pending Order!\nFinish It First!**")

    countries = [
        d for d in os.listdir(BASE_SESSION_DIR)
        if os.path.isdir(os.path.join(BASE_SESSION_DIR, d))
    ]

    if not countries:
        return await m.reply("**❌ No Stock Available Currently.**")

    buttons = []

    for country in countries:
        country_path = os.path.join(BASE_SESSION_DIR, country)

        count = len([
            f for f in os.listdir(country_path)
            if f.endswith(".session")
        ])

        if count > 0:
            price = get_country_price(country)
            buttons.append([
                types.InlineKeyboardButton(
                    f"{country} | ₹{price}",
                    callback_data=f"sel_{country}"
                )
            ])

    if not buttons:
        return await m.reply("**❌ No Stock Available Currently.**")

    await m.reply(
        "**🟢 Select A Country You Need:**",
        reply_markup=types.InlineKeyboardMarkup(buttons)
    )

@bot.on_message(filters.command("admin") & filters.private)
async def admin_panel(c, m):
    uid = m.from_user.id
    if uid not in ADMIN_IDS:
        return await m.reply("❌ **You Are Not My Admin.**")

    price = get_setting("price")
    kb = types.InlineKeyboardMarkup([
    [types.InlineKeyboardButton(f"💰 Default Price | ₹{price}", callback_data="adm_setprice")],
    [types.InlineKeyboardButton("➕ Add Balance", callback_data="adm_addbal_init")],
    [
        types.InlineKeyboardButton("📊 Stats", callback_data="adm_stats"),
        types.InlineKeyboardButton("➕ Add Account", callback_data="adm_addacc")
    ],
    [types.InlineKeyboardButton("🏳 Set Country Price", callback_data="adm_country_price")],
    [types.InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast_init")],
    [types.InlineKeyboardButton("📱 Manage Numbers", callback_data="adm_manage_numbers")]
])
    await m.reply("🛠 **Admin Panel**", reply_markup=kb)

@bot.on_message(filters.command("approve_") & filters.private)
async def approve_spam(bot, m):
    if m.from_user.id not in ADMIN_IDS:
        return
    phone = m.text.split("_", 1)[1]
    SPAM_APPROVAL[phone] = True
    await m.reply(f"✅ `{phone}` **Approved!\nContinuing Process.**")

@bot.on_message(filters.command("skip_") & filters.private)
async def skip_spam(bot, m):
    if m.from_user.id not in ADMIN_IDS:
        return
    phone = m.text.split("_", 1)[1]
    SPAM_APPROVAL[phone] = False
    await m.reply(f"❌ `{phone}` **Skipped!**")

@bot.on_callback_query()
async def handle_all_callbacks(c, q):
    uid = q.from_user.id
    data = q.data

    if data.startswith("sel_"):
        country = data.split("_")[1]
        price = get_country_price(country)
        kb = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("✅ Confirm & Buy", callback_data=f"conf_{country}")],
            [types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_buy")]
        ])
        await q.message.edit_text(
            f"**🛒 Confirm Purchase**\n\n**🏳 Country: {country}\n💵 Price:** `₹{price}`\n\n**• Click Confirm To Get An Account! 👇**",
            reply_markup=kb
        )

    elif data.startswith("conf_"):
        country = data.split("_")[1]
        price = get_country_price(country)
        bal, _, _ = get_user_data(uid)
        if bal < price:
            return await q.answer(f"❌ Insufficient Balance!", show_alert=True)

        c_path = os.path.join(BASE_SESSION_DIR, country)
        sessions = [f for f in os.listdir(c_path) if f.endswith(".session")]
        if not sessions:
            return await q.answer("❌ No Stock Available Currently.", show_alert=True)

        s_name = sessions[0]
        phone_num = s_name.replace(".session", "")
        update_user_stats(uid, balance_delta=-price, spent_delta=price)
        update_biz_stats("total_sold", 1)
        update_biz_stats("total_revenue", price)

        acc_pass = "tgking"
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO orders (user_id, session_name, status, country, price, password) VALUES (?, ?, 0, ?, ?, ?)",
            (uid, s_name, country, price, acc_pass)
        )
        conn.commit()
        conn.close()

        kb = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("📩 Get OTP", callback_data=f"get_{s_name}")]
        ])
        await q.message.edit_text(
            f"✅ **Order Active!**\n\n📱 **Phone:** `{phone_num}`\n🏳 **Country: {country}**\n\n**🔻 INSTRUCTIONS:\n1. Open Telegram > Add Account\n2. Enter The Number Above.\n3. Click Get OTP Below After Sending OTP.**",
            reply_markup=kb
        )

        await bot.send_message(
            LOG_CHANNEL_ID,
            f"🛒 **New Order Placed!**\n\n"
    f"👤 **Name: {q.from_user.first_name}\n"
    f"🆔 User ID:** `{q.from_user.id}`\n"
    f"📛 **Username: @{q.from_user.username if q.from_user.username else 'None'}\n"
    f"🏳 Country: {country}\n"
    f"💸 Charge:** `₹{price}`"
)

    elif data == "back_to_buy":
        await q.message.delete()
        await buy_acc_start(c, q.message)

    elif data.startswith("get_"):
        s_name = data.replace("get_", "")
        phone_display = s_name.replace(".session", "")

        conn = get_db()
        cur = conn.cursor()
        order = cur.execute(
            "SELECT country, password, last_otp FROM orders WHERE user_id = ? AND session_name = ?",
            (uid, s_name)
        ).fetchone()
        conn.close()

        if not order:
            return await q.answer("Order Not Found!", show_alert=True)

        country, password, last_otp = order

        full_path = ""
        for r, _, f in os.walk(BASE_SESSION_DIR):
            if s_name in f:
                full_path = os.path.join(r, s_name).replace(".session", "")
                break

        if not full_path or not os.path.exists(f"{full_path}.session"):
            kb = types.InlineKeyboardMarkup([
                [types.InlineKeyboardButton("🔄 Get OTP Again", callback_data=f"get_{s_name}")],
                [types.InlineKeyboardButton("🔴 Logout This Bot", callback_data=f"ask_log_{s_name}")]
            ])
            final_text = (
                f"🟢 **Bot Logged Out!**\n\n"
                f"📱 **Phone:** `{phone_display}`\n"
                f"🏳️ **Country: {country}**\n"
                f"🔐 **2FA:** `{password}`\n\n"
            )
            await q.message.edit_text(final_text, reply_markup=kb)
            return

        temp_client = Client(name=full_path, api_id=API_ID, api_hash=API_HASH, no_updates=True)
        try:
            await temp_client.start()
            otp_found = None
            async for msg in temp_client.get_chat_history(777000, limit=1):
                if msg.text:
                    found = re.findall(r'\b\d{5}\b', msg.text)
                    if found:
                        otp_found = found[0]
                        break

            if not otp_found:
                return await q.answer("⚠️ OTP Not Found! Please Send OTP First.", show_alert=True)

            if last_otp == otp_found:
                return await q.answer("⚠️ Same OTP Found! Please Send A New OTP.", show_alert=True)

            conn = get_db()
            cur = conn.cursor()

            cur.execute(
                "UPDATE orders SET last_otp=?, status=1 WHERE user_id=? AND session_name=?",
                (otp_found, uid, s_name)
            )

            conn.commit()
            conn.close()

            kb = types.InlineKeyboardMarkup([
                [types.InlineKeyboardButton("🔄 Refresh OTP", callback_data=f"get_{s_name}")],
                [types.InlineKeyboardButton("🔴 Logout This Bot", callback_data=f"ask_log_{s_name}")]
            ])

            final_text = (
                f"✅ **Order Complete!**\n\n"
                f"📱 **Phone:** `{phone_display}`\n"
                f"🏳️ **Country:** {country}\n"
                f"🔢 **OTP:** `{otp_found}`\n"
                f"🔐 **2FA:** `{password}`\n\n"
                f"🔴 **Click Logout Only After Login!**"
            )
            await q.message.edit_text(final_text, reply_markup=kb)

        except Exception as e:
            await q.answer(f"❌ OTP Error: {e}", show_alert=True)
        finally:
            await temp_client.stop()

    elif data.startswith("ask_log_"):
        s_name = data.replace("ask_log_", "")
        kb = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("✅ Confirm Logout", callback_data=f"done_log_{s_name}")],
            [types.InlineKeyboardButton("❌ Back", callback_data=f"back_from_logout_{s_name}")]
        ])
        await q.message.edit_text("🔴 **Logout This Bot From This Account?\n\n• Note: Confirm Logout Only If You Have Logged In From Your Device.**", reply_markup=kb)

    elif data.startswith("back_from_logout_"):
        s_name = data.replace("back_from_logout_", "")
        phone_display = s_name.replace(".session", "")

        conn = get_db()
        cur = conn.cursor()
        order = cur.execute(
            "SELECT country, password, last_otp FROM orders WHERE user_id = ? AND session_name = ?",
            (uid, s_name)
        ).fetchone()
        conn.close()

        if not order:
            return await q.answer("Order Not Found!", show_alert=True)

        country, password, last_otp = order

        kb = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("🔄 Refresh OTP", callback_data=f"get_{s_name}")],
            [types.InlineKeyboardButton("🔴 Logout This Bot", callback_data=f"ask_log_{s_name}")]
        ])

        final_text = (
            f"✅ **Order Complete!**\n\n"
            f"📱 **Phone:** `{phone_display}`\n"
            f"🏳️ **Country:** {country}\n"
            f"🔢 **OTP:** `{last_otp}`\n"
            f"🔐 **2FA:** `{password}`\n\n"
            f"🔴 **Click Logout Only After Login!**"
        )
        await q.message.edit_text(final_text, reply_markup=kb)

    elif data.startswith("done_log_"):
        s_name = data.replace("done_log_", "")
        full_path = ""
        for r, _, f in os.walk(BASE_SESSION_DIR):
            if s_name in f:
                full_path = os.path.join(r, s_name).replace(".session", "")
                break

        if full_path and os.path.exists(f"{full_path}.session"):
            try:
                async with Client(full_path, API_ID, API_HASH) as user_bot:
                    await user_bot.log_out()

                if os.path.exists(f"{full_path}.session"):
                    os.remove(f"{full_path}.session")

                conn = get_db()
                cur = conn.cursor()
                cur.execute("UPDATE orders SET status = 1 WHERE user_id = ? AND session_name = ?", (uid, s_name))
                order = cur.execute(
                    "SELECT country, password FROM orders WHERE user_id = ? AND session_name = ?",
                    (uid, s_name)
                ).fetchone()
                conn.commit()
                conn.close()

                if order:
                    country, password = order
                    phone = s_name.replace(".session", "")
                    await q.message.edit_text(
                        f"🟢 **Bot Logged Out Successfully!\n\n"
                        f"📱 Phone:** `{phone}`\n"
                        f"🏳️ **Country: {country}\n"
                        f"🔐 2FA:** `{password}`"
                    )
                else:
                    await q.message.edit_text("🟢 **Bot Logged Out Successfully!\n\n🔐 2FA:** `tgking`")

            except Exception as e:
                await q.answer(f"❌ Logout Failed: {e}", show_alert=True)

    elif data == "user_history":
        conn = get_db()
        cur = conn.cursor()
        orders = cur.execute("SELECT session_name, country, price FROM orders WHERE user_id=? ORDER BY timestamp DESC LIMIT 10", (uid,)).fetchall()
        conn.close()
        if not orders:
            return await q.answer("No History!", show_alert=True)
        text = "**📜 Purchase History**\n\n" + "\n".join(f"🛒 `{o[0].replace('.session','')}` **| {o[1]}**" for o in orders)
        await q.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_stats")]]))

    elif data == "back_to_stats":
        bal, spent, dep = get_user_data(uid)
        conn = get_db()
        cur = conn.cursor()
        count = cur.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,)).fetchone()[0]
        conn.close()
        await q.message.edit_text(f"**📊 Your Statistics**\n\n**🛒 Accounts Bought:** `{count}`\n**💸 Total Spent:** `₹{spent:.2f}`\n**💳 Total Deposited:** `₹{dep:.2f}`",
            reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton("📜 Purchase History", callback_data="user_history")]]))

    elif data.startswith("adm_"):
        if uid not in ADMIN_IDS:
            return await q.answer("❌ Unauthorized", show_alert=True)

        action = data.replace("adm_", "")
        if action == "stats":
            conn = get_db()
            cur = conn.cursor()
            users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            sold = cur.execute("SELECT value FROM business_stats WHERE key='total_sold'").fetchone()[0] or 0
            rev = cur.execute("SELECT value FROM business_stats WHERE key='total_revenue'").fetchone()[0] or 0
            dep = cur.execute("SELECT value FROM business_stats WHERE key='total_deposited'").fetchone()[0] or 0
            conn.close()
            await q.message.edit_text(f"📊 **Admin Statistics\n\n👥 Users:** `{users}`\n**🛒 Sold:** `{int(sold)}`\n💸 **Revenue:** `₹{float(rev):.2f}`\n💳 **Deposits:** `₹{float(dep):.2f}`",
                reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton("⬅️ Back", callback_data="adm_back")]]))

        elif action == "manage_numbers":
            countries = [d for d in os.listdir(BASE_SESSION_DIR) if os.path.isdir(os.path.join(BASE_SESSION_DIR, d))]
            if not countries:
                return await q.message.edit_text("❌ **No Countries Available!**")
            buttons = [[types.InlineKeyboardButton(c, callback_data=f"man_country_{c}")] for c in countries]
            buttons.append([types.InlineKeyboardButton("⬅️ Back", callback_data="adm_back")])
            await q.message.edit_text("🏳 **Select A Country To Manage:**", reply_markup=types.InlineKeyboardMarkup(buttons))

        elif action == "addbal_init":
            login_data[uid] = {"step": "adm_get_id"}
            await q.message.edit_text("🆔 **Enter User ID To Add Balance:**", reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton("❌ Cancel", callback_data="adm_back")]]))

        elif action == "addacc":
            login_data[uid] = {"step": "country"}
            await q.message.edit_text("**Enter Country Name (Ex.: 🇮🇳 India):**")

        elif action == "setprice":
            login_data[uid] = {"step": "setprice"}
            await q.message.edit_text("**Enter New Default Price for All Accounts:**")

        elif action == "country_price":
            login_data[uid] = {"step": "set_country_name"}
            await q.message.edit_text("**Enter Country Name To Set Specific Price:**")

        elif action == "broadcast_init":
            login_data[uid] = {"step": "broadcast_msg"}
            await q.message.edit_text("📢 **Send Message To Broadcast:**", reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton("❌ Cancel", callback_data="adm_back")]]))

        elif action == "back":
            price = get_setting("price")
            kb = types.InlineKeyboardMarkup([
                [types.InlineKeyboardButton(f"💰 Default Price | ₹{price}", callback_data="adm_setprice")],
                [types.InlineKeyboardButton("➕ Add Balance", callback_data="adm_addbal_init")],
                [types.InlineKeyboardButton("📊 Stats", callback_data="adm_stats"), types.InlineKeyboardButton("➕ Add Account", callback_data="adm_addacc")],
                [types.InlineKeyboardButton("🏳 Set Country Price", callback_data="adm_country_price")],
                [types.InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast_init")],
                [types.InlineKeyboardButton("📱 Manage Numbers", callback_data="adm_manage_numbers")]
            ])
            await q.message.edit_text("🛠 **Admin Panel**", reply_markup=kb)

    elif data.startswith("man_country_"):
        country = data.replace("man_country_", "")
        c_path = os.path.join(BASE_SESSION_DIR, country)
        if not os.path.exists(c_path):
            return await q.message.edit_text("**❌ Folder Not Found!**")
        sessions = [f for f in os.listdir(c_path) if f.endswith(".session")]
        if not sessions:
            return await q.message.edit_text(f"❌ **No Numbers In {country}**")
        buttons = [[types.InlineKeyboardButton(s.replace(".session", ""), callback_data=f"man_number_{country}_{s.replace('.session', '')}")] for s in sessions]
        buttons.append([types.InlineKeyboardButton("⬅️ Back", callback_data="adm_manage_numbers")])
        await q.message.edit_text(f"📱 **Select a Number in {country}:**", reply_markup=types.InlineKeyboardMarkup(buttons))

    elif data.startswith("man_number_"):
        parts = data.split("_")
        if len(parts) == 4:
            _, _, country, number = parts
        else:
            return await q.answer("Invalid Data!", show_alert=True)

        kb = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("✅ Yes", callback_data=f"logout_yes_{country}_{number}")],
                                         [types.InlineKeyboardButton("❌ No", callback_data=f"logout_no_{country}_{number}")]])
        await q.message.edit_text(f"**⚠️ Confirm Logout For** `{number}` **In {country}?**", reply_markup=kb)

    elif data.startswith("logout_no_"):
        parts = data.split("_")
        if len(parts) == 4:
            _, _, country, number = parts
        else:
            return await q.answer("Invalid Data!", show_alert=True)

        # Instead of recursive call, directly handle the back logic
        c_path = os.path.join(BASE_SESSION_DIR, country)
        if not os.path.exists(c_path):
            return await q.message.edit_text("**❌ Folder Not Found!**")
        sessions = [f for f in os.listdir(c_path) if f.endswith(".session")]
        if not sessions:
            return await q.message.edit_text(f"❌ **No Numbers In {country}**")
        buttons = [[types.InlineKeyboardButton(s.replace(".session", ""), callback_data=f"man_number_{country}_{s.replace('.session', '')}")] for s in sessions]
        buttons.append([types.InlineKeyboardButton("⬅️ Back", callback_data="adm_manage_numbers")])
        await q.message.edit_text(f"📱 **Select a Number in {country}:**", reply_markup=types.InlineKeyboardMarkup(buttons))

    elif data.startswith("logout_yes_"):
        parts = data.split("_")
        if len(parts) == 4:
            _, _, country, number = parts
        else:
            return await q.answer("Invalid Data!", show_alert=True)

        full_path = os.path.join(BASE_SESSION_DIR, country, f"{number}.session")
        try:
            if os.path.exists(full_path):
                async with Client(number, API_ID, API_HASH, workdir=os.path.join(BASE_SESSION_DIR, country), no_updates=True) as user_bot:
                    await user_bot.log_out()
        except Exception as e:
            pass

        if os.path.exists(full_path):
            os.remove(full_path)

        await q.message.edit_text(f"**✅ Number Logged Out And Deleted!**")


# --- TEXT INPUT HANDLER ---
@bot.on_message(filters.text & filters.private)
async def handle_inputs(c, m):
    uid = m.from_user.id
    if uid not in login_data:
        return

    state = login_data[uid]

    # 1. ADMIN ADD BALANCE
    if state.get("step") == "adm_get_id":
        target_id = m.text.strip()
        if not target_id.isdigit():
            return await m.reply("**❌ Invalid ID. Please Send Numbers Only.**")
        state.update({"step": "adm_get_amount", "target_id": int(target_id)})
        await m.reply(f"👤 **User ID:** `{target_id}`\n💰 **Enter Amount to Add (In ₹):**")
        return

    elif state.get("step") == "adm_get_amount":
        try:
            amount = float(m.text.strip())
            target_id = state["target_id"]
            update_user_stats(target_id, balance_delta=amount, deposit_delta=amount)
            update_biz_stats("total_deposited", amount)
            login_data.pop(uid)
            await m.reply(f"✅ **Added** `₹{amount}` **To** `{target_id}`")
            try:
                await bot.send_message(target_id, f"🎉 **Successfully Added Deposit Of** `₹{amount}` **To Your Balance!**")
            except:
                pass
        except:
            await m.reply("❌ **Invalid Amount.**")
        return

    # 3. ADMIN SET GLOBAL PRICE (EXISTING)
    if state.get("step") == "setprice":
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE settings SET value = ? WHERE key = 'price'", (m.text,))
        conn.commit()
        conn.close()
        login_data.pop(uid)
        await m.reply(f"**✅ Default Price Updated To** `₹{m.text}`")
        return

    # 🏳 ADMIN SET COUNTRY PRICE (NEW - ADDED ONLY)
    elif state.get("step") == "set_country_name" and uid == ADMIN_ID:
        state["country"] = m.text.strip()
        state["step"] = "set_country_price"
        await m.reply(f"💰 **Enter Price For {state['country']}:**")
        return

    elif state.get("step") == "set_country_price" and uid == ADMIN_ID:
        try:
            price = float(m.text.strip())
            country = state["country"]
            set_country_price(country, price)
            login_data.pop(uid)
            await m.reply(f"✅ **Price Set For {country}:** `₹{price}`")
        except:
            await m.reply("❌ **Invalid Price.**")
        return

    # 4. ADMIN ADD ACCOUNT FLOW (EXISTING - UNTOUCHED)
    elif uid == ADMIN_ID:
        if state.get("step") == "country":
            state.update({"country": m.text, "step": "phone"})
            await m.reply("**✅ Send Phone Number (+91...):**")

        elif state.get("step") == "phone":
            phone = m.text.strip()
            temp = Client(f"{BASE_SESSION_DIR}/{phone}", API_ID, API_HASH)
            await temp.connect()
            try:
                chash = await temp.send_code(phone)
                state.update({
                    "step": "otp",
                    "phone": phone,
                    "hash": chash.phone_code_hash,
                    "client": temp
                })
                await m.reply("**📩 OTP Sent! Enter OTP:**")
            except Exception as e:
                await m.reply(f"**❌ Error:** `{e}`")
                await temp.disconnect()
                login_data.pop(uid)

        elif state.get("step") == "otp":
            try:
                await state["client"].sign_in(
                    state["phone"],
                    state["hash"],
                    m.text.strip()
                )
                await finalize_admin_acc(
                    state["client"],
                    uid,
                    state["phone"],
                    state["country"]
                )
                login_data.pop(uid)
            except SessionPasswordNeeded:
                state["step"] = "2fa"
                await m.reply("**🔐 Enter Current 2FA:**")
            except Exception as e:
                await m.reply(f"**❌ Failed:** `{e}`")
                await state["client"].disconnect()
                login_data.pop(uid)

        elif state.get("step") == "2fa":
            try:
                await state["client"].check_password(m.text.strip())
                await finalize_admin_acc(
                    state["client"],
                    uid,
                    state["phone"],
                    state["country"],
                    m.text.strip()
                )
                login_data.pop(uid)
            except Exception as e:
                await m.reply(f"**❌ Wrong Password:** `{e}`")

    # 5. BROADCAST MESSAGE (EXISTING)
    if state.get("step") == "broadcast_msg" and uid == ADMIN_ID:
        msg_text = m.text
        conn = get_db()
        cur = conn.cursor()
        users = cur.execute("SELECT id FROM users").fetchall()
        conn.close()

        sent_count = 0
        for user in users:
            try:
                await bot.send_message(
                    user[0],
                    f"**{msg_text}**"
                )
                sent_count += 1
            except:
                continue

        login_data.pop(uid)
        await m.reply(f"**✅ Broadcast Sent To** `{sent_count}` **Users.**")

async def spambot_check(client, bot, admin_id, phone):
    # SpamBot start
    await client.send_message("SpamBot", "/start")
    await asyncio.sleep(3)

    reply_text = ""
    async for msg in client.get_chat_history("SpamBot", limit=1):
        reply_text = msg.text or ""

    # ✅ Clean account → auto continue
    if "no limits are currently applied" in reply_text.lower():
        return True

    # ❌ Not clean → admin se pooche
    await bot.send_message(
        admin_id,
        f"⚠️ **SpamBot Warning Detected**\n\n"
        f"📱 **Phone:** `{phone}`\n\n"
        f"{reply_text}\n\n"
        f"??Reply With:**\n"
        f"`/approve_{phone}` **→ Continue**\n"
        f"`/skip_{phone}` **→ Skip**"
    )

    SPAM_APPROVAL[phone] = None
    return None


async def finalize_admin_acc(client, admin_id, phone, country, current_pwd=None):
    try:
        await asyncio.sleep(2)

        # ================= SPAMBOT CHECK =================
        try:
            try:
                await client.unblock_user("spambot")
            except:
                pass

            allowed = await spambot_check(client, bot, admin_id, phone)

            if allowed is None:
                while SPAM_APPROVAL.get(phone) is None:
                    await asyncio.sleep(2)
                allowed = SPAM_APPROVAL.pop(phone)

            if not allowed:
                await bot.send_message(admin_id, f"❌ **Account** `{phone}` **Skipped Due To SpamBot Status.**")
                await client.disconnect()
                return

        except Exception as e:
            await bot.send_message(admin_id, f"⚠️ **SpamBot Check Warning For** `{phone}`:\n`{e}`")

        # ================= PROFILE =================
        try:
            me = await client.get_me()
            await client.update_profile(first_name="sxyaru", last_name="", bio="join @sxyaru")
        except Exception as e:
            await bot.send_message(admin_id, f"⚠️ **Profile Update Warning For** `{phone}`:\n`{e}`")

        # ================= USERNAME =================
        try:
            if getattr(me, "username", None):
                await client.invoke(functions.account.UpdateUsername(username=""))
        except RPCError as e:
            await bot.send_message(admin_id, f"⚠️ **Username Update Warning For** `{phone}`:\n`{e}`")

        # ================= PRIVACY =================
        try:
            await client.invoke(
                functions.account.SetPrivacy(
                    key=raw_types.InputPrivacyKeyPhoneNumber(),
                    rules=[raw_types.InputPrivacyValueDisallowAll()]
                )
            )
            await client.invoke(
                functions.account.SetPrivacy(
                    key=raw_types.InputPrivacyKeyAddedByPhone(),
                    rules=[raw_types.InputPrivacyValueAllowContacts()]
                )
            )
        except Exception as e:
            await bot.send_message(admin_id, f"⚠️ **Privacy Update Warning For** `{phone}`:\n`{e}`")

        # ================= 2FA =================
        try:
            if current_pwd:
                await client.change_cloud_password(current_password=current_pwd, new_password="nikitayt7")
            else:
                await client.enable_cloud_password(password="nikitayt7", hint="")
        except Exception as e:
            await bot.send_message(admin_id, f"⚠️ **2FA Update Warning For** `{phone}`:\n`{e}`")

        # ================= PROFILE PHOTOS =================
        try:
            async for photo in client.get_chat_photos("me"):
                await client.delete_profile_photos(photo.file_id)
        except Exception as e:
            await bot.send_message(admin_id, f"⚠️ **Profile Photo Deletion Warning For** `{phone}`:\n`{e}`")

        # ================= CONTACTS (instant delete) =================
        try:
            contacts = await client.invoke(
        functions.contacts.GetContacts(hash=0)
    )

            if contacts.users:
                await client.invoke(
                functions.contacts.DeleteContacts(
                id=[
                    raw_types.InputUser(
                        user_id=u.id,
                        access_hash=u.access_hash
                    ) for u in contacts.users
                ]
            )
        )

                # Clear saved contacts (Settings wala part)
                await client.invoke(functions.contacts.ResetSaved())

        except FloodWait as fw:
                # FloodWait = Telegram restriction, unavoidable
                await asyncio.sleep(fw.value)

        except Exception as e:
                await bot.send_message(
        admin_id,
        f"⚠️ **Contacts Delete Error**\n📱 `{phone}`\n`{e}`"
    )

        # ================= CHAT CLEANUP =================
        try:
            async for dialog in client.get_dialogs():
                chat = dialog.chat

                if chat.id == 777000:
                    continue
                if getattr(chat, "username", None) and chat.username.lower() == "spambot":
                    continue

                if chat.id == "me":
                    try:
                        peer = await client.resolve_peer("me")
                        await client.invoke(
                            functions.messages.DeleteHistory(
                                peer=peer,
                                max_id=0,
                                revoke=True
                            )
                        )
                    except FloodWait as fw:
                        await asyncio.sleep(fw.value)
                    except:
                        pass
                    continue

                if chat.type == "bot":
                    try:
                        peer = await client.resolve_peer(chat.id)
                        await client.invoke(
                            functions.messages.DeleteHistory(
                                peer=peer,
                                max_id=0,
                                revoke=True
                            )
                        )
                        await client.block_user(chat.id)
                    except FloodWait as fw:
                        await asyncio.sleep(fw.value)
                    except:
                        continue

                elif chat.type == "private":
                    try:
                        peer = await client.resolve_peer(chat.id)
                        await client.invoke(
                            functions.messages.DeleteHistory(
                                peer=peer,
                                max_id=0,
                                revoke=True
                            )
                        )
                    except FloodWait as fw:
                        await asyncio.sleep(fw.value)
                    except:
                        continue

                else:
                    try:
                        await client.leave_chat(chat.id)
                    except FloodWait as fw:
                        await asyncio.sleep(fw.value)
                    except:
                        continue

        except Exception as e:
            await bot.send_message(
                admin_id,
                f"⚠️ **Chat Cleanup Error**\n📱 `{phone}`\n`{e}`"
            )

        # ================= SESSION MOVE =================
        try:
            c_path = os.path.join(BASE_SESSION_DIR, country)
            os.makedirs(c_path, exist_ok=True)

            await client.disconnect()

            phone_str = str(phone).strip()
            shutil.move(f"{BASE_SESSION_DIR}/{phone_str}.session", f"{c_path}/{phone_str}.session")
        except Exception as e:
            await bot.send_message(admin_id, f"⚠️ **Session Move Warning For** `{phone}`:\n`{e}`")

        # ================= SUCCESS =================
        await bot.send_message(
            admin_id,
            f"👑 **Account Added Successfully!**\n\n"
            f"📱 `{phone}`\n"
            f"✅ **SpamBot: Approved**"
        )

    except Exception as e:
        await bot.send_message(admin_id, f"❌ **Fatal Error While Processing** `{phone}`:\n`{e}`")

# --- RUN BOT ---
print("Bot is Starting...")
bot.run()
