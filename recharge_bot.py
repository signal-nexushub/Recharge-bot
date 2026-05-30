"""
Free Recharge Telegram Bot — Demo Version
Requirements: pip install python-telegram-bot==20.7
"""

import logging
import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler, filters
)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BOT_TOKEN       = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL_ID      = "@your_channel"   # Apna channel username daalen, e.g. "@mychannel"
ADMIN_ID        = 123456789         # Apna Telegram User ID daalen
CREDIT_VALUE    = 30                # 1 credit = ₹30
DB_FILE         = "users.json"      # Data store (simple file-based)

# ─── CONVERSATION STATES ──────────────────────────────────────────────────────
ASK_NUMBER, ASK_OPERATOR, SHOW_PLANS = range(3)

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── RECHARGE PLANS ───────────────────────────────────────────────────────────
PLANS = {
    "Jio": [
        {"name": "₹29 — 1.5GB/Day | 1 Day",        "price": 29},
        {"name": "₹179 — 2GB/Day | 28 Days",        "price": 179},
        {"name": "₹239 — 1.5GB/Day | 28 Days",      "price": 239},
        {"name": "₹299 — 2GB/Day | 28 Days",        "price": 299},
        {"name": "₹399 — 2.5GB/Day | 28 Days",      "price": 399},
        {"name": "₹555 — 2GB/Day | 84 Days",        "price": 555},
        {"name": "₹999 — 2GB/Day | 365 Days",       "price": 999},
    ],
    "Airtel": [
        {"name": "₹19 — 200MB | 1 Day",             "price": 19},
        {"name": "₹179 — 1.5GB/Day | 28 Days",      "price": 179},
        {"name": "₹249 — 2GB/Day | 28 Days",        "price": 249},
        {"name": "₹299 — 2GB/Day | 28 Days",        "price": 299},
        {"name": "₹359 — 2.5GB/Day | 28 Days",      "price": 359},
        {"name": "₹549 — 2GB/Day | 84 Days",        "price": 549},
        {"name": "₹1099 — 2GB/Day | 365 Days",      "price": 1099},
    ],
    "Vi": [
        {"name": "₹19 — 200MB | 1 Day",             "price": 19},
        {"name": "₹169 — 1GB/Day | 28 Days",        "price": 169},
        {"name": "₹229 — 1.5GB/Day | 28 Days",      "price": 229},
        {"name": "₹299 — 2GB/Day | 28 Days",        "price": 299},
        {"name": "₹449 — 2.5GB/Day | 56 Days",      "price": 449},
        {"name": "₹599 — 2GB/Day | 84 Days",        "price": 599},
        {"name": "₹1099 — 1.5GB/Day | 365 Days",    "price": 1099},
    ],
    "BSNL": [
        {"name": "₹22 — 100MB | 1 Day",             "price": 22},
        {"name": "₹108 — 1GB/Day | 28 Days",        "price": 108},
        {"name": "₹197 — 2GB/Day | 28 Days",        "price": 197},
        {"name": "₹247 — 2GB/Day | 28 Days",        "price": 247},
        {"name": "₹319 — 3GB/Day | 30 Days",        "price": 319},
        {"name": "₹599 — 2GB/Day | 90 Days",        "price": 599},
        {"name": "₹1999 — 2GB/Day | 365 Days",      "price": 1999},
    ],
}

OPERATORS = list(PLANS.keys())

# ═══════════════════════════════════════════════════════════════════════════════
#  DATABASE HELPERS (simple JSON file)
# ═══════════════════════════════════════════════════════════════════════════════

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def get_user(user_id: int):
    db = load_db()
    uid = str(user_id)
    if uid not in db:
        db[uid] = {"credits": 0, "balance": 0, "referrals": [], "referred_by": None}
        save_db(db)
    return db[uid]

def update_user(user_id: int, data: dict):
    db = load_db()
    uid = str(user_id)
    if uid not in db:
        db[uid] = {"credits": 0, "balance": 0, "referrals": [], "referred_by": None}
    db[uid].update(data)
    save_db(db)

def add_balance(user_id: int, amount: float):
    user = get_user(user_id)
    new_balance = round(user["balance"] + amount, 2)
    update_user(user_id, {"balance": new_balance})
    return new_balance

def deduct_balance(user_id: int, amount: float):
    user = get_user(user_id)
    new_balance = round(user["balance"] - amount, 2)
    update_user(user_id, {"balance": new_balance})
    return new_balance

# ═══════════════════════════════════════════════════════════════════════════════
#  CHANNEL CHECK
# ═══════════════════════════════════════════════════════════════════════════════

async def is_member(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

def channel_join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Channel Join Karein", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
        [InlineKeyboardButton("✅ Join Ho Gaya — Aage Badhein", callback_data="check_join")]
    ])

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN MENU
# ═══════════════════════════════════════════════════════════════════════════════

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Recharge Karein", callback_data="recharge")],
        [InlineKeyboardButton("👥 Referral Link", callback_data="referral"),
         InlineKeyboardButton("💰 Mera Balance", callback_data="balance")],
        [InlineKeyboardButton("ℹ️ Help & Guide", callback_data="help")]
    ])

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    user = update.effective_user
    data = get_user(user.id)
    balance = data["balance"]
    credits = data["credits"]

    text = (
        f"👋 *Assalam-o-Alaikum, {user.first_name}!*\n\n"
        f"🎉 *Free Recharge Bot mein aapka swagat hai!*\n"
        f"Apne doston ko refer karein aur muft mein recharge paayein.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *Aapka Balance:*  ₹{balance:.2f}\n"
        f"⭐ *Aapke Credits:*  {credits}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 *1 Referral = 1 Credit = ₹{CREDIT_VALUE} Balance*\n\n"
        f"Neeche diye gaye options mein se chunein 👇"
    )

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )
    else:
        msg = update.message or update.callback_query.message
        await msg.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())

# ═══════════════════════════════════════════════════════════════════════════════
#  /start COMMAND
# ═══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args  # referral check

    # --- Referral process ---
    referrer_id = None
    if args and args[0].startswith("ref_"):
        try:
            referrer_id = int(args[0].replace("ref_", ""))
        except ValueError:
            pass

    # Register user if new
    db = load_db()
    uid = str(user.id)
    is_new = uid not in db

    user_data = get_user(user.id)  # creates if not exists

    # Credit referrer only if:
    # 1. User is new
    # 2. Referrer exists
    # 3. User is not referring himself
    # 4. Not already referred
    if is_new and referrer_id and referrer_id != user.id and not user_data.get("referred_by"):
        referrer_data = get_user(referrer_id)

        # Mark this user as referred
        update_user(user.id, {"referred_by": referrer_id})

        # Add credit + balance to referrer
        new_credits = referrer_data["credits"] + 1
        new_balance = round(referrer_data["balance"] + CREDIT_VALUE, 2)
        referrals = referrer_data.get("referrals", [])
        referrals.append(user.id)
        update_user(referrer_id, {
            "credits": new_credits,
            "balance": new_balance,
            "referrals": referrals
        })

        # Notify referrer
        try:
            await context.bot.send_message(
                referrer_id,
                f"🎉 *Congratulations!*\n\n"
                f"👤 *{user.first_name}* ne aapke referral link se bot join kiya!\n\n"
                f"✅ *+1 Credit aur +₹{CREDIT_VALUE}* aapke account mein add kar diye gaye hain.\n\n"
                f"💰 *Aapka Naaya Balance:* ₹{new_balance:.2f}\n\n"
                f"Aur referrals ke liye apna link share karte rahein! 🚀",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    # Check channel membership
    joined = await is_member(context.bot, user.id)
    if not joined:
        await update.message.reply_text(
            f"👋 *Assalam-o-Alaikum, {user.first_name}!*\n\n"
            f"🔒 *Bot Access ke liye Channel Join Zaruri Hai*\n\n"
            f"Hamara channel join karein aur tazaa updates, offers aur "
            f"recharge alerts sabse pehle paayein!\n\n"
            f"▶️ Neeche *'Channel Join Karein'* button dabayein,\n"
            f"phir *'Join Ho Gaya'* button dabayein aur bot shuru ho jaayega. ✅",
            parse_mode="Markdown",
            reply_markup=channel_join_keyboard()
        )
        # Save referrer temporarily
        if referrer_id:
            context.user_data["pending_referrer"] = referrer_id
        return

    await show_main_menu(update, context)

# ═══════════════════════════════════════════════════════════════════════════════
#  CALLBACK HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user

    # ── Check Join ──────────────────────────────────────────────────────────
    if data == "check_join":
        joined = await is_member(context.bot, user.id)
        if not joined:
            await query.answer("❌ Aapne abhi channel join nahi kiya!", show_alert=True)
            return
        await show_main_menu(update, context, edit=True)

    # ── Main Menu ────────────────────────────────────────────────────────────
    elif data == "main_menu":
        await show_main_menu(update, context, edit=True)

    # ── Balance ──────────────────────────────────────────────────────────────
    elif data == "balance":
        user_data = get_user(user.id)
        text = (
            f"💰 *Aapka Balance — Poori Jaankari*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 *Maujuda Balance:*   ₹{user_data['balance']:.2f}\n"
            f"⭐ *Aapke Credits:*      {user_data['credits']}\n"
            f"👥 *Kul Referrals:*      {len(user_data.get('referrals', []))}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💡 *1 Credit = ₹{CREDIT_VALUE} Balance*\n\n"
            f"Apna referral link zyada se zyada logo mein share karein\n"
            f"aur apna balance badhate rahein! 🚀"
        )
        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="main_menu")
            ]])
        )

    # ── Referral ─────────────────────────────────────────────────────────────
    elif data == "referral":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user.id}"
        user_data = get_user(user.id)
        text = (
            f"👥 *Referral Program — Muft Kamaayein!*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *1 Referral = 1 Credit = ₹{CREDIT_VALUE} Balance*\n"
            f"👤 *Aapke Kul Referrals:*  {len(user_data.get('referrals', []))}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔗 *Aapka Referral Link:*\n"
            f"`{ref_link}`\n\n"
            f"📋 *Yeh link copy karein aur apne doston, family aur\n"
            f"groups mein share karein!*\n\n"
            f"⚠️ *Zaruri Baat:*\n"
            f"Credit sirf tab milega jab doosra insaan is link se\n"
            f"bot open kare aur /start kare. Sirf link bhejne se\n"
            f"credit nahi milega."
        )
        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="main_menu")
            ]])
        )

    # ── Help ─────────────────────────────────────────────────────────────────
    elif data == "help":
        text = (
            f"ℹ️ *Help & Guide — Poori Jaankari*\n\n"
            f"*📌 Bot Kaise Use Karein?*\n\n"
            f"1️⃣ Apna referral link copy karein\n"
            f"2️⃣ Doston aur family mein share karein\n"
            f"3️⃣ Jab woh /start karein → aapko ₹{CREDIT_VALUE} milega\n"
            f"4️⃣ Balance aane par *'Recharge Karein'* button dabayein\n"
            f"5️⃣ Apna 10 digit mobile number enter karein\n"
            f"6️⃣ Apna operator chunein (Jio / Airtel / Vi / BSNL)\n"
            f"7️⃣ Plan chunein aur recharge turant ho jaayega!\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ *Zaruri Baatein:*\n\n"
            f"• Sirf link bhejne se credit *nahi* milega\n"
            f"• Credit tab milega jab doosra insaan bot start kare\n"
            f"• Recharge ke liye plan ki poori raqam balance mein honi chahiye\n"
            f"• Ek hi referral link se aap khud credit nahi le sakte\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="main_menu")
            ]])
        )

    # ── Recharge Start ────────────────────────────────────────────────────────
    elif data == "recharge":
        # Check channel membership again
        joined = await is_member(context.bot, user.id)
        if not joined:
            await query.answer("❌ Recharge ke liye pehle channel join karein!", show_alert=True)
            return

        await query.edit_message_text(
            "📱 *Mobile Recharge — Step 1 of 3*\n\n"
            "Apna *10 digit mobile number* darj karein:\n\n"
            "📝 _(Misal ke taur par: 9876543210)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="main_menu")
            ]])
        )
        return ASK_NUMBER

    # ── Operator Selected ─────────────────────────────────────────────────────
    elif data.startswith("op_"):
        operator = data.replace("op_", "")
        context.user_data["operator"] = operator
        plans = PLANS.get(operator, [])
        user_data = get_user(user.id)
        balance = user_data["balance"]

        buttons = []
        for i, plan in enumerate(plans):
            affordable = "✅" if balance >= plan["price"] else "❌"
            buttons.append([InlineKeyboardButton(
                f"{affordable} {plan['name']}",
                callback_data=f"plan_{i}"
            )])
        buttons.append([InlineKeyboardButton("🔙 Wapas Jaayein", callback_data="recharge")])

        await query.edit_message_text(
            f"📋 *{operator} — Recharge Plans*\n\n"
            f"💰 *Aapka Maujuda Balance:* ₹{balance:.2f}\n\n"
            f"✅ = Aap yeh plan le sakte hain\n"
            f"❌ = Is plan ke liye balance kam hai\n\n"
            f"Apna plan chunein 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # ── Plan Selected ─────────────────────────────────────────────────────────
    elif data.startswith("plan_"):
        plan_idx = int(data.replace("plan_", ""))
        operator = context.user_data.get("operator")
        mobile = context.user_data.get("mobile")
        plan = PLANS[operator][plan_idx]
        user_data = get_user(user.id)
        balance = user_data["balance"]

        if balance < plan["price"]:
            await query.answer(
                f"❌ Balance Kam Hai!\n\nIs plan ke liye ₹{plan['price']} chahiye.\nAapka maujuda balance ₹{balance:.2f} hai.\n\nZyada referrals karen aur balance badhayein!",
                show_alert=True
            )
            return

        # Confirm recharge
        context.user_data["selected_plan"] = plan
        await query.edit_message_text(
            f"🔍 *Recharge Confirm Karein — Step 3 of 3*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 *Mobile Number:*    `{mobile}`\n"
            f"📡 *Operator:*          {operator}\n"
            f"📦 *Plan:*              {plan['name']}\n"
            f"💵 *Recharge Amount:*  ₹{plan['price']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Maujuda Balance:*  ₹{balance:.2f}\n"
            f"💳 *Recharge ke Baad:* ₹{balance - plan['price']:.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Kya aap is recharge ko confirm karte hain?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Haan, Recharge Karein", callback_data="confirm_recharge")],
                [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]
            ])
        )

    # ── Confirm Recharge ──────────────────────────────────────────────────────
    elif data == "confirm_recharge":
        plan = context.user_data.get("selected_plan")
        operator = context.user_data.get("operator")
        mobile = context.user_data.get("mobile")
        user_data = get_user(user.id)
        balance = user_data["balance"]

        if balance < plan["price"]:
            await query.answer("❌ Balance Kam Ho Gaya! Pehle referrals karein.", show_alert=True)
            return

        # Deduct balance
        new_balance = deduct_balance(user.id, plan["price"])

        # Show success
        await query.edit_message_text(
            f"✅ *Recharge Successful!*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 *Mobile Number:*     `{mobile}`\n"
            f"📡 *Operator:*           {operator}\n"
            f"📦 *Plan:*               {plan['name']}\n"
            f"💵 *Katauti Hui Raqam:* ₹{plan['price']}\n"
            f"💰 *Bacha Hua Balance:* ₹{new_balance:.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎉 *Recharge Complete!*\n"
            f"Aapka plan kuch hi der mein aapke number par active ho jaayega.\n\n"
            f"_(Yeh ek demo recharge hai — asli recharge nahi hua)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Recharge Again", callback_data="recharge")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
        )
        # Clear temp data
        context.user_data.pop("selected_plan", None)
        context.user_data.pop("operator", None)
        context.user_data.pop("mobile", None)

    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════════
#  CONVERSATION — Number & Operator
# ═══════════════════════════════════════════════════════════════════════════════

async def ask_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text.strip()
    if not (number.isdigit() and len(number) == 10):
        await update.message.reply_text(
            "❌ *Galat Number Darj Kiya!*\n\n"
            "Kripya apna *10 digit ka sahih mobile number* darj karein.\n\n"
            "📝 _(Misal ke taur par: 9876543210)_",
            parse_mode="Markdown"
        )
        return ASK_NUMBER

    context.user_data["mobile"] = number

    # Show operator selection
    buttons = [[InlineKeyboardButton(op, callback_data=f"op_{op}")] for op in OPERATORS]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="main_menu")])

    await update.message.reply_text(
        f"✅ *Number Darj Ho Gaya!*\n\n"
        f"📱 *Aapka Number:* `{number}`\n\n"
        f"📡 *Step 2 of 3 — Apna Operator Chunein:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ *Recharge Raddh Kar Di Gayi.*\n\nMain Menu se dobara shuru kar sakte hain.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ BOT_TOKEN set nahi kiya!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Conversation handler for number input
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^recharge$")],
        states={
            ASK_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_number)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Recharge Bot chalu ho gaya!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
