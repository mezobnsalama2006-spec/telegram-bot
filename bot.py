import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from database import Database
from config import BOT_TOKEN, ADMIN_IDS

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database()

# ── States ─────────────────────────────────────────────────
WAITING_PAYMENT_AMOUNT      = 1
WAITING_PAYMENT_PROOF       = 2
WAITING_PRODUCT_NAME        = 3
WAITING_PRODUCT_DESC        = 4
WAITING_PRODUCT_PRICE       = 5
WAITING_ITEM_CONTENT        = 6
WAITING_ADD_BALANCE_AMOUNT  = 7
WAITING_CATEGORY_NAME       = 8
WAITING_CATEGORY_EMOJI      = 9
WAITING_APP_NAME            = 10
WAITING_APP_EMOJI           = 11

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ── Keyboards ──────────────────────────────────────────────

def persistent_keyboard():
    return ReplyKeyboardMarkup([["/start"]], resize_keyboard=True, is_persistent=True)

def main_menu_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("🛍️ المنتجات",   callback_data="categories"),
         InlineKeyboardButton("💼 محفظتي",      callback_data="wallet")],
        [InlineKeyboardButton("➕ شحن رصيد",    callback_data="add_balance"),
         InlineKeyboardButton("📋 طلباتي",      callback_data="my_orders")],
        [InlineKeyboardButton("ℹ️ مساعدة",      callback_data="help")]
    ]
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 الكاتيجريز",   callback_data="admin_categories"),
         InlineKeyboardButton("📦 المنتجات",      callback_data="admin_products_all")],
        [InlineKeyboardButton("👥 المستخدمين",   callback_data="admin_users"),
         InlineKeyboardButton("💳 الإيداعات",    callback_data="admin_deposits")],
        [InlineKeyboardButton("📊 إحصائيات",     callback_data="admin_stats"),
         InlineKeyboardButton("🔙 رجوع",          callback_data="main_menu")]
    ])

# ══════════════════════════════════════════════════════════
# START
# ══════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username or user.first_name, user.first_name)
    text = (
        f"👋 أهلاً *{user.first_name}*!\n\n"
        "🏪 *متجر المنتجات الرقمية*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🛍️ تصفح منتجاتنا الرقمية\n"
        "💰 أدر رصيدك بسهولة\n"
        "📦 تسليم فوري بعد الشراء\n\n"
        "اختر من القائمة:"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=persistent_keyboard())
        await update.message.reply_text("📋 *القائمة الرئيسية*", parse_mode='Markdown',
                                        reply_markup=main_menu_keyboard(user.id))
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown',
                                                      reply_markup=main_menu_keyboard(user.id))

# ══════════════════════════════════════════════════════════
# CATEGORIES (Level 1)
# ══════════════════════════════════════════════════════════

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categories = db.get_all_categories()
    if not categories:
        await query.edit_message_text(
            "📂 *لا توجد كاتيجريز بعد.*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]))
        return
    keyboard = []
    for cat in categories:
        keyboard.append([InlineKeyboardButton(
            f"{cat['emoji']} {cat['name']}",
            callback_data=f"cat_{cat['id']}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    await query.edit_message_text(
        "🛍️ *اختر الكاتيجري:*\n━━━━━━━━━━━━━━━━━━",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ══════════════════════════════════════════════════════════
# APPS (Level 2)
# ══════════════════════════════════════════════════════════

async def show_apps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split("_")[1])
    cat = db.get_category(cat_id)
    apps = db.get_apps_by_category(cat_id)
    if not apps:
        await query.edit_message_text(
            f"{cat['emoji']} *{cat['name']}*\n\nلا توجد تطبيقات بعد.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="categories")]]))
        return
    keyboard = []
    for app in apps:
        keyboard.append([InlineKeyboardButton(
            f"{app['emoji']} {app['name']}",
            callback_data=f"app_{app['id']}_{cat_id}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="categories")])
    await query.edit_message_text(
        f"{cat['emoji']} *{cat['name']}*\n━━━━━━━━━━━━━━━━━━\nاختر التطبيق:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ══════════════════════════════════════════════════════════
# PRODUCTS (Level 3)
# ══════════════════════════════════════════════════════════

async def show_products_by_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts  = query.data.split("_")
    app_id = int(parts[1])
    cat_id = int(parts[2])
    app      = db.get_app(app_id)
    products = db.get_products_by_app(app_id)
    if not products:
        await query.edit_message_text(
            f"{app['emoji']} *{app['name']}*\n\nلا توجد خدمات بعد.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=f"cat_{cat_id}")]]))
        return
    keyboard = []
    for p in products:
        emoji = "🟢" if p['stock'] > 0 else "🔴"
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {p['name']} — ${p['price']:.2f} ({p['stock']} متوفر)",
            callback_data=f"product_{p['id']}_{app_id}_{cat_id}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"cat_{cat_id}")])
    await query.edit_message_text(
        f"{app['emoji']} *{app['name']}*\n━━━━━━━━━━━━━━━━━━\nاختر الخدمة:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ══════════════════════════════════════════════════════════
# PRODUCT DETAIL
# ══════════════════════════════════════════════════════════

async def show_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts      = query.data.split("_")   # product_{id}_{app_id}_{cat_id}
    product_id = int(parts[1])
    app_id     = int(parts[2])
    cat_id     = int(parts[3])
    product = db.get_product(product_id)
    if not product:
        await query.answer("المنتج غير موجود!", show_alert=True)
        return
    stock_text = f"✅ متوفر ({product['stock']} قطعة)" if product['stock'] > 0 else "❌ نفد المخزون"
    text = (
        f"📦 *{product['name']}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📝 {product['description']}\n\n"
        f"💰 السعر: *${product['price']:.2f}*\n"
        f"📊 الحالة: {stock_text}"
    )
    keyboard = []
    if product['stock'] > 0:
        keyboard.append([InlineKeyboardButton(
            f"🛒 اشتري الآن — ${product['price']:.2f}",
            callback_data=f"buy_{product_id}_{app_id}_{cat_id}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"app_{app_id}_{cat_id}")])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# ══════════════════════════════════════════════════════════
# BUY
# ══════════════════════════════════════════════════════════

async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts      = query.data.split("_")
    product_id = int(parts[1])
    app_id     = int(parts[2])
    cat_id     = int(parts[3])
    user_id    = query.from_user.id
    product = db.get_product(product_id)
    balance = db.get_balance(user_id)
    if not product or product['stock'] <= 0:
        await query.answer("❌ نفد المخزون!", show_alert=True)
        return
    if balance < product['price']:
        shortage = product['price'] - balance
        await query.edit_message_text(
            f"❌ *رصيد غير كافٍ*\n\n"
            f"💰 رصيدك: *${balance:.2f}*\n"
            f"💳 سعر المنتج: *${product['price']:.2f}*\n"
            f"⚠️ تحتاج: *${shortage:.2f}* إضافية",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ شحن رصيد", callback_data="add_balance")],
                [InlineKeyboardButton("🔙 رجوع",       callback_data=f"app_{app_id}_{cat_id}")]
            ]))
        return
    await query.edit_message_text(
        f"🛒 *تأكيد الشراء*\n\n"
        f"📦 المنتج: *{product['name']}*\n"
        f"💰 السعر: *${product['price']:.2f}*\n"
        f"💼 رصيدك: *${balance:.2f}*\n"
        f"💵 بعد الشراء: *${balance - product['price']:.2f}*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تأكيد", callback_data=f"confirmbuy_{product_id}_{app_id}_{cat_id}"),
             InlineKeyboardButton("❌ إلغاء", callback_data=f"app_{app_id}_{cat_id}")]
        ]))

async def confirm_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts      = query.data.split("_")
    product_id = int(parts[1])
    app_id     = int(parts[2])
    cat_id     = int(parts[3])
    user_id    = query.from_user.id
    success, result = db.purchase_product(user_id, product_id)
    if success:
        await query.edit_message_text(
            f"✅ *تمت عملية الشراء بنجاح!*\n\n"
            f"📦 المنتج: *{result['product_name']}*\n"
            f"💵 الرصيد المتبقي: *${result['new_balance']:.2f}*\n\n"
            f"🎁 *تفاصيل المنتج:*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"`{result['content']}`",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]]))
    else:
        await query.edit_message_text(
            f"❌ *فشل الشراء*\n\n{result}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=f"app_{app_id}_{cat_id}")]]))

# ══════════════════════════════════════════════════════════
# WALLET
# ══════════════════════════════════════════════════════════

async def show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    balance      = db.get_balance(user_id)
    transactions = db.get_transactions(user_id, limit=5)
    text = f"💼 *محفظتي*\n━━━━━━━━━━━━━━━━━━\n💰 الرصيد: *${balance:.2f}*\n\n📋 *آخر المعاملات:*\n"
    if transactions:
        for t in transactions:
            emoji = "➕" if t['type'] == 'deposit' else "🛒"
            sign  = "+" if t['type'] == 'deposit' else "-"
            text += f"{emoji} {sign}${abs(t['amount']):.2f} — {t['description']}\n"
    else:
        text += "_لا توجد معاملات بعد._"
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ شحن رصيد",   callback_data="add_balance")],
        [InlineKeyboardButton("📋 كل الطلبات", callback_data="my_orders")],
        [InlineKeyboardButton("🔙 رجوع",        callback_data="main_menu")]
    ]))

# ══════════════════════════════════════════════════════════
# ADD BALANCE
# ══════════════════════════════════════════════════════════

async def add_balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "➕ *شحن الرصيد*\n━━━━━━━━━━━━━━━━━━\n\n"
        "💳 *طرق الدفع:*\n"
        "• Binance: `1199904304`\n"
        "• Vodafone Cash: `01028749936`\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💵 *الخطوة 1:* أدخل *المبلغ* الذي أرسلته (مثال: `25`):"
    )
    await query.edit_message_text(text, parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="main_menu")]]))
    context.user_data['state'] = WAITING_PAYMENT_AMOUNT
    return WAITING_PAYMENT_AMOUNT

async def receive_payment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
        context.user_data['deposit_amount'] = amount
        context.user_data['state'] = WAITING_PAYMENT_PROOF
        await update.message.reply_text(
            f"✅ المبلغ: *${amount:.2f}*\n\n"
            f"📸 *الخطوة 2:* أرسل *صورة* إيصال الدفع:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="main_menu")]]))
        return WAITING_PAYMENT_PROOF
    except ValueError:
        await update.message.reply_text("❌ أدخل مبلغاً صحيحاً (مثال: `25` أو `10.5`)", parse_mode='Markdown')
        return WAITING_PAYMENT_AMOUNT

async def receive_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ أرسل *صورة* إيصال الدفع.", parse_mode='Markdown')
        return WAITING_PAYMENT_PROOF
    user   = update.effective_user
    photo  = update.message.photo[-1]
    amount = context.user_data.get('deposit_amount', 0)
    deposit_id = db.create_deposit_request(user.id, photo.file_id, amount)
    await update.message.reply_text(
        f"✅ *تم إرسال الطلب!*\n\n"
        f"🔢 رقم الطلب: `#{deposit_id}`\n"
        f"💰 المبلغ: *${amount:.2f}*\n"
        f"⏳ الحالة: *قيد المراجعة*\n\n"
        f"ستصلك رسالة فور الموافقة!",
        parse_mode='Markdown', reply_markup=main_menu_keyboard(user.id))
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id, photo=photo.file_id,
                caption=(
                    f"💳 *طلب إيداع جديد*\n━━━━━━━━━━━━━━━━━━\n"
                    f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
                    f"🆔 `{user.id}`\n"
                    f"🔢 #{deposit_id}\n"
                    f"💰 *${amount:.2f}*"
                ),
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"✅ قبول ${amount:.2f}", callback_data=f"approve_deposit_{deposit_id}_{amount}"),
                     InlineKeyboardButton("❌ رفض",                callback_data=f"reject_deposit_{deposit_id}")]
                ]))
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    context.user_data.pop('state', None)
    context.user_data.pop('deposit_amount', None)
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════
# MY ORDERS
# ══════════════════════════════════════════════════════════

async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    orders  = db.get_user_orders(user_id)
    if not orders:
        text = "📋 *طلباتي*\n\n_لم تقم بأي عمليات شراء بعد._"
    else:
        text = "📋 *طلباتي*\n━━━━━━━━━━━━━━━━━━\n"
        for o in orders:
            text += f"\n🛒 *{o['product_name']}* — ${o['price']:.2f}\n"
            text += f"   📅 {o['date']}\n"
            if o.get('content'):
                text += f"   🎁 `{o['content'][:40]}...`\n"
    await query.edit_message_text(text, parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]))

# ══════════════════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════════════════

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "ℹ️ *المساعدة والدعم*\n━━━━━━━━━━━━━━━━━━\n\n"
        "🛍️ *كيف تشتري:*\n1. اذهب للمنتجات\n2. اختر الكاتيجري ثم التطبيق\n3. اختر الخدمة وأكد الشراء\n\n"
        "💰 *كيف تشحن الرصيد:*\n1. اذهب لـ شحن رصيد\n2. أرسل الدفع\n3. ارفع الإيصال\n4. انتظر الموافقة\n\n"
        "📞 *تواصل مع الدعم:* `@MezoStoreeAdmin`",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]))

# ══════════════════════════════════════════════════════════
# ADMIN PANEL
# ══════════════════════════════════════════════════════════

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("❌ غير مسموح!", show_alert=True)
        return
    stats = db.get_stats()
    text = (
        f"⚙️ *لوحة الإدارة*\n━━━━━━━━━━━━━━━━━━\n"
        f"👥 المستخدمين: *{stats['users']}*\n"
        f"📂 الكاتيجريز: *{stats['categories']}*\n"
        f"📱 التطبيقات: *{stats['apps']}*\n"
        f"📦 المنتجات: *{stats['products']}*\n"
        f"🗃️ المخزون: *{stats['total_items']}*\n"
        f"🛒 الطلبات: *{stats['orders']}*\n"
        f"💰 الإيرادات: *${stats['revenue']:.2f}*\n"
        f"⏳ إيداعات معلقة: *{stats['pending_deposits']}*"
    )
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=admin_panel_keyboard())

# ══════════════════════════════════════════════════════════
# ADMIN — CATEGORIES MANAGEMENT
# ══════════════════════════════════════════════════════════

async def admin_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    cats = db.get_all_categories()
    keyboard = []
    text = f"📂 *إدارة الكاتيجريز* ({len(cats)})\n━━━━━━━━━━━━━━━━━━\n\n"
    for cat in cats:
        apps_count = len(db.get_apps_by_category(cat['id']))
        keyboard.append([InlineKeyboardButton(
            f"{cat['emoji']} {cat['name']} ({apps_count} تطبيق)",
            callback_data=f"admin_cat_{cat['id']}"
        )])
    keyboard.append([InlineKeyboardButton("➕ إضافة كاتيجري", callback_data="admin_add_category")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع",           callback_data="admin_panel")])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_category_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    cat_id = int(query.data.split("_")[2])
    cat    = db.get_category(cat_id)
    apps   = db.get_apps_by_category(cat_id)
    keyboard = []
    text = (
        f"{cat['emoji']} *{cat['name']}*\n━━━━━━━━━━━━━━━━━━\n"
        f"التطبيقات: *{len(apps)}*\n\n"
    )
    for app in apps:
        products = db.get_products_by_app(app['id'])
        keyboard.append([InlineKeyboardButton(
            f"{app['emoji']} {app['name']} ({len(products)} خدمة)",
            callback_data=f"admin_app_{app['id']}_{cat_id}"
        )])
    keyboard.append([InlineKeyboardButton("➕ إضافة تطبيق",     callback_data=f"admin_add_app_{cat_id}")])
    keyboard.append([InlineKeyboardButton("🗑️ حذف الكاتيجري",  callback_data=f"admin_del_cat_{cat_id}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع",             callback_data="admin_categories")])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def start_add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data['state'] = WAITING_CATEGORY_NAME
    await query.edit_message_text(
        "➕ *إضافة كاتيجري جديدة*\n\nأدخل *اسم الكاتيجري* (مثال: متابعين):",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_categories")]]))

async def get_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_category_name'] = update.message.text.strip()
    context.user_data['state'] = WAITING_CATEGORY_EMOJI
    await update.message.reply_text(
        "أدخل *إيموجي* الكاتيجري (مثال: 👥 أو 👍 أو 👁️):\nأو اكتب `skip` لاستخدام 📁",
        parse_mode='Markdown')

async def get_category_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text  = update.message.text.strip()
    emoji = "📁" if text.lower() == "skip" else text
    name  = context.user_data.get('new_category_name', 'بدون اسم')
    cat_id = db.add_category(name, emoji)
    context.user_data.pop('state', None)
    await update.message.reply_text(
        f"✅ *تم إنشاء الكاتيجري!*\n\n{emoji} *{name}*\n\nالآن أضف تطبيقات لها.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"➕ إضافة تطبيق لـ {name}", callback_data=f"admin_add_app_{cat_id}")],
            [InlineKeyboardButton("🔙 إدارة الكاتيجريز",       callback_data="admin_categories")]
        ]))

async def admin_delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    cat_id = int(query.data.split("_")[3])
    db.delete_category(cat_id)
    await query.answer("✅ تم الحذف!", show_alert=True)
    query.data = "admin_categories"
    await admin_categories(update, context)

# ══════════════════════════════════════════════════════════
# ADMIN — APPS MANAGEMENT
# ══════════════════════════════════════════════════════════

async def admin_app_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    parts  = query.data.split("_")
    app_id = int(parts[2])
    cat_id = int(parts[3])
    app      = db.get_app(app_id)
    products = db.get_products_by_app(app_id)
    keyboard = []
    text = (
        f"{app['emoji']} *{app['name']}*\n━━━━━━━━━━━━━━━━━━\n"
        f"الخدمات: *{len(products)}*\n\n"
    )
    for p in products:
        emoji = "🟢" if p['stock'] > 0 else "🔴"
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {p['name']} (${p['price']:.2f}) — {p['stock']} قطعة",
            callback_data=f"admin_prod_{p['id']}_{app_id}_{cat_id}"
        )])
    keyboard.append([InlineKeyboardButton("➕ إضافة خدمة",      callback_data=f"admin_add_prod_{app_id}_{cat_id}")])
    keyboard.append([InlineKeyboardButton("🗑️ حذف التطبيق",    callback_data=f"admin_del_app_{app_id}_{cat_id}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع",             callback_data=f"admin_cat_{cat_id}")])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def start_add_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split("_")[3])
    context.user_data.clear()
    context.user_data['adding_app_to_cat'] = cat_id
    context.user_data['state'] = WAITING_APP_NAME
    cat = db.get_category(cat_id)
    await query.edit_message_text(
        f"➕ *إضافة تطبيق إلى: {cat['name']}*\n\nأدخل *اسم التطبيق* (مثال: Instagram):",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data=f"admin_cat_{cat_id}")]]))

async def get_app_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_app_name'] = update.message.text.strip()
    context.user_data['state'] = WAITING_APP_EMOJI
    await update.message.reply_text(
        "أدخل *إيموجي* التطبيق (مثال: 📸 أو 👍 أو 🎵):\nأو اكتب `skip` لاستخدام 📱",
        parse_mode='Markdown')

async def get_app_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text   = update.message.text.strip()
    emoji  = "📱" if text.lower() == "skip" else text
    name   = context.user_data.get('new_app_name', 'بدون اسم')
    cat_id = context.user_data.get('adding_app_to_cat')
    app_id = db.add_app(cat_id, name, emoji)
    context.user_data.pop('state', None)
    await update.message.reply_text(
        f"✅ *تم إنشاء التطبيق!*\n\n{emoji} *{name}*\n\nالآن أضف خدمات له.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"➕ إضافة خدمة لـ {name}", callback_data=f"admin_add_prod_{app_id}_{cat_id}")],
            [InlineKeyboardButton("🔙 رجوع للتطبيق",           callback_data=f"admin_cat_{cat_id}")]
        ]))

async def admin_delete_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    parts  = query.data.split("_")
    app_id = int(parts[3])
    cat_id = int(parts[4])
    db.delete_app(app_id)
    await query.answer("✅ تم الحذف!", show_alert=True)
    query.data = f"admin_cat_{cat_id}"
    await admin_category_detail(update, context)

# ══════════════════════════════════════════════════════════
# ADMIN — PRODUCTS MANAGEMENT (inside app)
# ══════════════════════════════════════════════════════════

async def admin_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    parts      = query.data.split("_")
    product_id = int(parts[2])
    app_id     = int(parts[3])
    cat_id     = int(parts[4])
    product = db.get_product(product_id)
    if not product:
        await query.answer("غير موجود!", show_alert=True)
        return
    items = db.get_product_items(product_id)
    text  = (
        f"📦 *{product['name']}*\n━━━━━━━━━━━━━━━━━━\n"
        f"📝 {product['description']}\n"
        f"💰 السعر: ${product['price']:.2f}\n"
        f"🗃️ المخزون: *{product['stock']}*\n\n"
    )
    if items:
        text += "📋 *العناصر المتاحة:*\n"
        for i, item in enumerate(items[:5], 1):
            preview = item['content'][:30] + "..." if len(item['content']) > 30 else item['content']
            text += f"{i}. `{preview}`\n"
        if len(items) > 5:
            text += f"_... و {len(items)-5} أكثر_\n"
    keyboard = [
        [InlineKeyboardButton("➕ إضافة عنصر",    callback_data=f"admin_additem_{product_id}_{app_id}_{cat_id}"),
         InlineKeyboardButton("🗑️ حذف عناصر",    callback_data=f"admin_mgitems_{product_id}_{app_id}_{cat_id}")],
        [InlineKeyboardButton("🗑️ حذف الخدمة",   callback_data=f"admin_delprod_{product_id}_{app_id}_{cat_id}")],
        [InlineKeyboardButton("🔙 رجوع",           callback_data=f"admin_app_{app_id}_{cat_id}")]
    ]
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts  = query.data.split("_")
    app_id = int(parts[3])
    cat_id = int(parts[4])
    context.user_data.clear()
    context.user_data['new_product']         = {}
    context.user_data['new_product_app_id']  = app_id
    context.user_data['new_product_cat_id']  = cat_id
    context.user_data['state']               = WAITING_PRODUCT_NAME
    app = db.get_app(app_id)
    await query.edit_message_text(
        f"➕ *إضافة خدمة إلى: {app['name']}*\n\nالخطوة 1/3: أدخل *اسم الخدمة*:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data=f"admin_app_{app_id}_{cat_id}")]]))

async def get_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_product']['name'] = update.message.text
    context.user_data['state'] = WAITING_PRODUCT_DESC
    await update.message.reply_text("الخطوة 2/3: أدخل *الوصف*:", parse_mode='Markdown')

async def get_product_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_product']['description'] = update.message.text
    context.user_data['state'] = WAITING_PRODUCT_PRICE
    await update.message.reply_text("الخطوة 3/3: أدخل *السعر* (مثال: 9.99):", parse_mode='Markdown')

async def get_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price  = float(update.message.text)
        app_id = context.user_data.get('new_product_app_id')
        cat_id = context.user_data.get('new_product_cat_id')
        product = context.user_data['new_product']
        product['price'] = price
        product_id = db.add_product(product['name'], product['description'], price, app_id)
        context.user_data['adding_item_to']     = product_id
        context.user_data['adding_item_app_id'] = app_id
        context.user_data['adding_item_cat_id'] = cat_id
        context.user_data['state']              = WAITING_ITEM_CONTENT
        await update.message.reply_text(
            f"✅ *تم إنشاء الخدمة: {product['name']}*\n\n"
            f"الآن أضف العناصر (حسابات/مفاتيح) واحداً تلو الآخر.\n\n"
            f"مثال:\n`email@gmail.com:password123`\nأو\n`XXXX-XXXX-XXXX-XXXX`",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ انتهيت", callback_data=f"admin_prod_{product_id}_{app_id}_{cat_id}")]
            ]))
    except ValueError:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً (مثال: 9.99)")

async def start_add_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    parts      = query.data.split("_")
    product_id = int(parts[2])
    app_id     = int(parts[3])
    cat_id     = int(parts[4])
    product = db.get_product(product_id)
    context.user_data.clear()
    context.user_data['adding_item_to']     = product_id
    context.user_data['adding_item_app_id'] = app_id
    context.user_data['adding_item_cat_id'] = cat_id
    context.user_data['state']              = WAITING_ITEM_CONTENT
    await query.edit_message_text(
        f"➕ *إضافة عنصر إلى: {product['name']}*\n\n"
        f"أرسل المحتوى (تفاصيل الحساب، مفتاح الترخيص، إلخ)\n\n"
        f"يمكنك إرسال *عدة عناصر* — أرسل كل واحد كرسالة منفصلة.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ انتهيت", callback_data=f"admin_prod_{product_id}_{app_id}_{cat_id}")],
            [InlineKeyboardButton("❌ إلغاء",  callback_data=f"admin_prod_{product_id}_{app_id}_{cat_id}")]
        ]))

async def receive_item_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != WAITING_ITEM_CONTENT:
        return
    product_id = context.user_data.get('adding_item_to')
    if not product_id:
        return
    content = update.message.text.strip()
    if not content:
        return
    db.add_item_to_product(product_id, content)
    product = db.get_product(product_id)
    await update.message.reply_text(
        f"✅ *تم إضافة العنصر!*\n\n"
        f"📦 الخدمة: *{product['name']}*\n"
        f"🗃️ المخزون الحالي: *{product['stock']}*\n\n"
        f"أرسل عنصراً آخر أو اضغط *انتهيت*.",
        parse_mode='Markdown')

async def manage_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    parts      = query.data.split("_")
    product_id = int(parts[2])
    app_id     = int(parts[3])
    cat_id     = int(parts[4])
    product = db.get_product(product_id)
    items   = db.get_product_items(product_id)
    if not items:
        await query.edit_message_text(
            f"📦 *{product['name']}*\n\nلا يوجد مخزون.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إضافة عنصر", callback_data=f"admin_additem_{product_id}_{app_id}_{cat_id}")],
                [InlineKeyboardButton("🔙 رجوع",        callback_data=f"admin_prod_{product_id}_{app_id}_{cat_id}")]
            ]))
        return
    keyboard = []
    text = f"🗑️ *حذف عناصر من: {product['name']}*\n━━━━━━━━━━━━━━━━━━\n\n"
    for item in items[:10]:
        preview = item['content'][:25] + "..." if len(item['content']) > 25 else item['content']
        text += f"ID {item['id']}: `{preview}`\n"
        keyboard.append([InlineKeyboardButton(
            f"🗑️ حذف ID {item['id']}",
            callback_data=f"admin_delitem_{item['id']}_{product_id}_{app_id}_{cat_id}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_prod_{product_id}_{app_id}_{cat_id}")])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    parts      = query.data.split("_")
    item_id    = int(parts[2])
    product_id = int(parts[3])
    app_id     = int(parts[4])
    cat_id     = int(parts[5])
    db.delete_item(item_id)
    await query.answer("✅ تم الحذف!", show_alert=True)
    query.data = f"admin_mgitems_{product_id}_{app_id}_{cat_id}"
    await manage_items(update, context)

async def delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    parts      = query.data.split("_")
    product_id = int(parts[2])
    app_id     = int(parts[3])
    cat_id     = int(parts[4])
    db.delete_product(product_id)
    await query.answer("✅ تم الحذف!", show_alert=True)
    query.data = f"admin_app_{app_id}_{cat_id}"
    await admin_app_detail(update, context)

# ══════════════════════════════════════════════════════════
# ADMIN — ALL PRODUCTS VIEW (flat list)
# ══════════════════════════════════════════════════════════

async def admin_products_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    products = db.get_all_products()
    text = f"📦 *كل الخدمات ({len(products)})*\n━━━━━━━━━━━━━━━━━━\n\n"
    for p in products:
        emoji = "🟢" if p['stock'] > 0 else "🔴"
        text += f"{emoji} *{p['name']}* — ${p['price']:.2f} ({p['stock']} قطعة)\n"
    await query.edit_message_text(text, parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]))

# ══════════════════════════════════════════════════════════
# ADMIN — DEPOSITS
# ══════════════════════════════════════════════════════════

async def admin_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    deposits = db.get_pending_deposits()
    if not deposits:
        await query.edit_message_text(
            "💳 *الإيداعات المعلقة*\n\n✅ لا توجد طلبات معلقة!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]))
        return
    keyboard = []
    text = f"💳 *الإيداعات المعلقة ({len(deposits)})*\n━━━━━━━━━━━━━━━━━━\n\n"
    for dep in deposits:
        text += f"🔢 #{dep['id']} — 👤 {dep['username']} — ${dep['amount']:.2f}\n"
        keyboard.append([InlineKeyboardButton(f"👁️ مراجعة #{dep['id']}", callback_data=f"review_deposit_{dep['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def review_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    deposit_id = int(query.data.split("_")[2])
    deposit    = db.get_deposit(deposit_id)
    if not deposit:
        await query.answer("غير موجود!", show_alert=True)
        return
    amount = deposit['amount']
    await context.bot.send_photo(
        chat_id=query.from_user.id,
        photo=deposit['photo_file_id'],
        caption=(
            f"💳 *إيداع #{deposit_id}*\n"
            f"👤 {deposit['username']}\n"
            f"🆔 `{deposit['user_id']}`\n"
            f"💵 المبلغ: *${amount}*\n\nهل تقبل هذا الإيداع؟"
        ),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ قبول",  callback_data=f"approve_deposit_{deposit_id}_{amount}")],
            [InlineKeyboardButton("❌ رفض",   callback_data=f"reject_deposit_{deposit_id}")]
        ]))

async def approve_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    parts      = query.data.split("_")
    deposit_id = int(parts[2])
    if len(parts) < 4:
        context.user_data['pending_deposit_id'] = deposit_id
        context.user_data['state'] = WAITING_ADD_BALANCE_AMOUNT
        await query.message.reply_text("أدخل المبلغ المراد إضافته:")
        return
    amount  = float(parts[3])
    deposit = db.get_deposit(deposit_id)
    if not deposit:
        return
    db.approve_deposit(deposit_id, amount, query.from_user.id)
    new_balance = db.get_balance(deposit['user_id'])
    try:
        await context.bot.send_message(
            chat_id=deposit['user_id'],
            text=f"✅ *تم إضافة ${amount:.2f} لرصيدك!*\n💼 الرصيد الجديد: *${new_balance:.2f}*\n\nيمكنك التسوق الآن! 🛍️",
            parse_mode='Markdown', reply_markup=main_menu_keyboard(deposit['user_id']))
    except:
        pass
    try:
        await query.edit_message_caption(
            caption=f"✅ تم قبول إيداع #{deposit_id} — ${amount:.2f} أضيفت لـ {deposit['username']}",
            parse_mode='Markdown')
    except:
        pass

async def reject_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    deposit_id = int(query.data.split("_")[2])
    deposit    = db.get_deposit(deposit_id)
    if not deposit:
        return
    db.reject_deposit(deposit_id, query.from_user.id)
    try:
        await context.bot.send_message(
            chat_id=deposit['user_id'],
            text=f"❌ *تم رفض طلب الإيداع #{deposit_id}*\n\nتواصل مع الدعم إذا كان هناك خطأ.",
            parse_mode='Markdown', reply_markup=main_menu_keyboard(deposit['user_id']))
    except:
        pass
    try:
        await query.edit_message_caption(caption=f"❌ تم رفض إيداع #{deposit_id}", parse_mode='Markdown')
    except:
        await query.edit_message_text(f"❌ تم رفض إيداع #{deposit_id}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_deposits")]]))

# ══════════════════════════════════════════════════════════
# ADMIN — USERS
# ══════════════════════════════════════════════════════════

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    users = db.get_all_users()
    text  = f"👥 *كل المستخدمين ({len(users)})*\n━━━━━━━━━━━━━━━━━━\n\n"
    for user in users[:20]:
        text += f"👤 {user['name']} — 💰 ${user['balance']:.2f}\n"
    if len(users) > 20:
        text += f"\n_... و {len(users)-20} أكثر_"
    await query.edit_message_text(text, parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]))

# ══════════════════════════════════════════════════════════
# HANDLE TEXT (state machine)
# ══════════════════════════════════════════════════════════

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')

    if state == WAITING_CATEGORY_NAME:
        await get_category_name(update, context)
    elif state == WAITING_CATEGORY_EMOJI:
        await get_category_emoji(update, context)
    elif state == WAITING_APP_NAME:
        await get_app_name(update, context)
    elif state == WAITING_APP_EMOJI:
        await get_app_emoji(update, context)
    elif state == WAITING_PRODUCT_NAME:
        await get_product_name(update, context)
    elif state == WAITING_PRODUCT_DESC:
        await get_product_desc(update, context)
    elif state == WAITING_PRODUCT_PRICE:
        await get_product_price(update, context)
    elif state == WAITING_ITEM_CONTENT:
        await receive_item_content(update, context)
    elif state == WAITING_PAYMENT_AMOUNT:
        await receive_payment_amount(update, context)
    elif state == WAITING_PAYMENT_PROOF:
        await update.message.reply_text("📸 أرسل *صورة* الإيصال.", parse_mode='Markdown')
    elif state == WAITING_ADD_BALANCE_AMOUNT:
        try:
            amount     = float(update.message.text)
            deposit_id = context.user_data.get('pending_deposit_id')
            if deposit_id:
                deposit = db.get_deposit(deposit_id)
                db.approve_deposit(deposit_id, amount, update.effective_user.id)
                new_balance = db.get_balance(deposit['user_id'])
                try:
                    await context.bot.send_message(
                        chat_id=deposit['user_id'],
                        text=f"✅ *تم إضافة ${amount:.2f}!*\n💼 الرصيد: *${new_balance:.2f}*",
                        parse_mode='Markdown',
                        reply_markup=main_menu_keyboard(deposit['user_id']))
                except:
                    pass
                await update.message.reply_text(
                    f"✅ تم قبول إيداع #{deposit_id}! أضيف ${amount:.2f}",
                    reply_markup=admin_panel_keyboard())
                context.user_data.pop('state', None)
                context.user_data.pop('pending_deposit_id', None)
        except ValueError:
            await update.message.reply_text("❌ أدخل رقماً صحيحاً")

# ══════════════════════════════════════════════════════════
# CALLBACK ROUTER
# ══════════════════════════════════════════════════════════

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data

    # clear item-adding state when navigating away
    if context.user_data.get('state') == WAITING_ITEM_CONTENT:
        if not (data.startswith("admin_prod_") or data.startswith("admin_additem_")):
            context.user_data.pop('state', None)
            context.user_data.pop('adding_item_to', None)

    # deposit actions first
    if data.startswith("approve_deposit_"):
        await approve_deposit(update, context); return
    if data.startswith("reject_deposit_"):
        await reject_deposit(update, context);  return
    if data.startswith("review_deposit_"):
        await review_deposit(update, context);  return

    # simple routes
    routes = {
        "main_menu":          start,
        "categories":         show_categories,
        "wallet":             show_wallet,
        "add_balance":        add_balance_start,
        "my_orders":          show_orders,
        "help":               show_help,
        "admin_panel":        admin_panel,
        "admin_categories":   admin_categories,
        "admin_products_all": admin_products_all,
        "admin_deposits":     admin_deposits,
        "admin_users":        admin_users,
        "admin_stats":        admin_panel,
        "admin_add_category": start_add_category,
    }
    if data in routes:
        await routes[data](update, context); return

    # parameterised routes
    if data.startswith("cat_"):              await show_apps(update, context)
    elif data.startswith("app_"):           await show_products_by_app(update, context)
    elif data.startswith("product_"):       await show_product_detail(update, context)
    elif data.startswith("buy_"):           await buy_product(update, context)
    elif data.startswith("confirmbuy_"):    await confirm_buy(update, context)

    elif data.startswith("admin_cat_"):     await admin_category_detail(update, context)
    elif data.startswith("admin_del_cat_"): await admin_delete_category(update, context)
    elif data.startswith("admin_add_app_"): await start_add_app(update, context)
    elif data.startswith("admin_app_"):     await admin_app_detail(update, context)
    elif data.startswith("admin_del_app_"): await admin_delete_app(update, context)
    elif data.startswith("admin_add_prod_"):await start_add_product(update, context)
    elif data.startswith("admin_prod_"):
        context.user_data.pop('state', None)
        context.user_data.pop('adding_item_to', None)
        await admin_product_detail(update, context)
    elif data.startswith("admin_delprod_"): await delete_product(update, context)
    elif data.startswith("admin_additem_"): await start_add_item(update, context)
    elif data.startswith("admin_mgitems_"): await manage_items(update, context)
    elif data.startswith("admin_delitem_"): await delete_item(update, context)

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, receive_payment_proof))
    print("🤖 البوت شغال...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
