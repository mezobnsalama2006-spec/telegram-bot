import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from database import Database
from config import BOT_TOKEN, ADMIN_IDS

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database()

# States
WAITING_PAYMENT_AMOUNT = 1
WAITING_PAYMENT_PROOF = 2
WAITING_PRODUCT_NAME = 3
WAITING_PRODUCT_DESC = 4
WAITING_PRODUCT_PRICE = 5
WAITING_ITEM_CONTENT = 6
WAITING_ADD_BALANCE_AMOUNT = 7

def is_admin(user_id):
    return user_id in ADMIN_IDS

def main_menu_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("🛍️ Products", callback_data="products"),
         InlineKeyboardButton("💼 My Wallet", callback_data="wallet")],
        [InlineKeyboardButton("➕ Add Balance", callback_data="add_balance"),
         InlineKeyboardButton("📋 My Orders", callback_data="my_orders")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Manage Products", callback_data="admin_products"),
         InlineKeyboardButton("👥 All Users", callback_data="admin_users")],
        [InlineKeyboardButton("💳 Pending Deposits", callback_data="admin_deposits"),
         InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
    ])

# ========================
# START
# ========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username or user.first_name, user.first_name)
    text = (
        f"👋 Welcome, *{user.first_name}*!\n\n"
        "🏪 *Digital Products Store*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🛍️ Browse our digital products\n"
        "💰 Manage your wallet balance\n"
        "📦 Instant delivery after purchase\n\n"
        "Choose an option below:"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_menu_keyboard(user.id))
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=main_menu_keyboard(user.id))

# ========================
# PRODUCTS
# ========================

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    products = db.get_all_products()
    if not products:
        await query.edit_message_text(
            "📦 *No products available yet.*\n\nCheck back later!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
        return
    keyboard = []
    for p in products:
        emoji = "🟢" if p['stock'] > 0 else "🔴"
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {p['name']} — ${p['price']:.2f} ({p['stock']} left)",
            callback_data=f"product_{p['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    await query.edit_message_text(
        "🛍️ *Available Products*\n━━━━━━━━━━━━━━━━━━\nSelect a product to view details:",
        parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def show_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split("_")[1])
    product = db.get_product(product_id)
    if not product:
        await query.answer("Product not found!", show_alert=True)
        return
    stock_text = f"✅ In Stock ({product['stock']} available)" if product['stock'] > 0 else "❌ Out of Stock"
    text = (
        f"📦 *{product['name']}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📝 {product['description']}\n\n"
        f"💰 Price: *${product['price']:.2f}*\n"
        f"📊 Status: {stock_text}"
    )
    keyboard = []
    if product['stock'] > 0:
        keyboard.append([InlineKeyboardButton(f"🛒 Buy Now — ${product['price']:.2f}", callback_data=f"buy_{product_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Products", callback_data="products")])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    product_id = int(query.data.split("_")[1])
    product = db.get_product(product_id)
    balance = db.get_balance(user_id)
    if not product or product['stock'] <= 0:
        await query.answer("❌ Product is out of stock!", show_alert=True)
        return
    if balance < product['price']:
        shortage = product['price'] - balance
        await query.edit_message_text(
            f"❌ *Insufficient Balance*\n\n"
            f"💰 Your balance: *${balance:.2f}*\n"
            f"💳 Product price: *${product['price']:.2f}*\n"
            f"⚠️ You need: *${shortage:.2f}* more",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Balance", callback_data="add_balance")],
                [InlineKeyboardButton("🔙 Back", callback_data="products")]]))
        return
    await query.edit_message_text(
        f"🛒 *Confirm Purchase*\n\n"
        f"📦 Product: *{product['name']}*\n"
        f"💰 Price: *${product['price']:.2f}*\n"
        f"💼 Your balance: *${balance:.2f}*\n"
        f"💵 After purchase: *${balance - product['price']:.2f}*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_buy_{product_id}"),
             InlineKeyboardButton("❌ Cancel", callback_data="products")]]))

async def confirm_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    product_id = int(query.data.split("_")[2])
    success, result = db.purchase_product(user_id, product_id)
    if success:
        await query.edit_message_text(
            f"✅ *Purchase Successful!*\n\n"
            f"📦 Product: *{result['product_name']}*\n"
            f"💵 Remaining balance: *${result['new_balance']:.2f}*\n\n"
            f"🎁 *Your Product Details:*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"`{result['content']}`",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]))
    else:
        await query.edit_message_text(
            f"❌ *Purchase Failed*\n\n{result}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="products")]]))

# ========================
# WALLET
# ========================

async def show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    balance = db.get_balance(user_id)
    transactions = db.get_transactions(user_id, limit=5)
    text = (f"💼 *My Wallet*\n━━━━━━━━━━━━━━━━━━\n💰 Balance: *${balance:.2f}*\n\n📋 *Recent Transactions:*\n")
    if transactions:
        for t in transactions:
            emoji = "➕" if t['type'] == 'deposit' else "🛒"
            sign = "+" if t['type'] == 'deposit' else "-"
            text += f"{emoji} {sign}${abs(t['amount']):.2f} — {t['description']}\n"
    else:
        text += "_No transactions yet._"
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Balance", callback_data="add_balance")],
        [InlineKeyboardButton("📋 Full History", callback_data="my_orders")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))

# ========================
# ADD BALANCE
# ========================

async def add_balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "➕ *Add Balance*\n━━━━━━━━━━━━━━━━━━\n\n"
        "💳 *Payment Methods:*\n"
        "• ByBit: `496950466 ,   546961050 `\n"
        "• Binance: `1199904304  , 422086209  `\n"
        "• InstaPay: `01028749936`\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💵 *Step 1:* Enter the *amount* you sent (US . `25`):"
    )
    await query.edit_message_text(text, parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]]))
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
            f"✅ Amount: *${amount:.2f}*\n\n"
            f"📸 *Step 2:* Now send the *screenshot* of your payment receipt:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]]))
        return WAITING_PAYMENT_PROOF
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid amount (US. `25` or `10.5`)", parse_mode='Markdown')
        return WAITING_PAYMENT_AMOUNT

async def receive_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Please send a *photo/screenshot* of your payment receipt.", parse_mode='Markdown')
        return WAITING_PAYMENT_PROOF
    user = update.effective_user
    photo = update.message.photo[-1]
    amount = context.user_data.get('deposit_amount', 0)
    deposit_id = db.create_deposit_request(user.id, photo.file_id, amount)
    await update.message.reply_text(
        f"✅ *Request Sent!*\n\n"
        f"🔢 Request ID: `#{deposit_id}`\n"
        f"💰 Amount: *${amount:.2f}*\n"
        f"⏳ Status: *Pending Review*\n\n"
        f"You'll receive a notification once approved!",
        parse_mode='Markdown', reply_markup=main_menu_keyboard(user.id))
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id, photo=photo.file_id,
                caption=(
                    f"💳 *New Deposit Request*\n━━━━━━━━━━━━━━━━━━\n"
                    f"👤 User: {user.first_name} (@{user.username or 'N/A'})\n"
                    f"🆔 User ID: `{user.id}`\n"
                    f"🔢 Request ID: `#{deposit_id}`\n"
                    f"💰 Amount: *${amount:.2f}*"
                ),
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"✅ Approve ${amount:.2f}", callback_data=f"approve_deposit_{deposit_id}_{amount}"),
                     InlineKeyboardButton("❌ Reject", callback_data=f"reject_deposit_{deposit_id}")]]))
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    context.user_data.pop('state', None)
    context.user_data.pop('deposit_amount', None)
    return ConversationHandler.END

# ========================
# MY ORDERS
# ========================

async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    orders = db.get_user_orders(user_id)
    if not orders:
        text = "📋 *My Orders*\n\n_You haven't made any purchases yet._"
    else:
        text = "📋 *My Orders*\n━━━━━━━━━━━━━━━━━━\n"
        for o in orders:
            text += f"\n🛒 *{o['product_name']}* — ${o['price']:.2f}\n"
            text += f"   📅 {o['date']}\n"
            if o.get('content'):
                text += f"   🎁 `{o['content'][:40]}...`\n"
    await query.edit_message_text(text, parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))

# ========================
# HELP
# ========================

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "ℹ️ *Help & Support*\n━━━━━━━━━━━━━━━━━━\n\n"
        "🛍️ *How to buy:*\n1. Go to Products\n2. Select a product\n3. Confirm purchase\n\n"
        "💰 *How to add balance:*\n1. Go to Add Balance\n2. Send payment\n3. Upload receipt\n4. Wait for approval\n\n"
        "📞 *Contact Support:* `@KDB_store_Admin`",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ])
    )

# ========================
# ADMIN PANEL
# ========================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("❌ Access denied!", show_alert=True)
        return
    stats = db.get_stats()
    text = (
        f"⚙️ *Admin Panel*\n━━━━━━━━━━━━━━━━━━\n"
        f"👥 Users: *{stats['users']}*\n"
        f"📦 Products: *{stats['products']}*\n"
        f"🗃️ Items in Stock: *{stats['total_items']}*\n"
        f"🛒 Orders: *{stats['orders']}*\n"
        f"💰 Revenue: *${stats['revenue']:.2f}*\n"
        f"⏳ Pending Deposits: *{stats['pending_deposits']}*"
    )
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=admin_panel_keyboard())

# ========================
# ADMIN - DEPOSITS
# ========================

async def admin_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    deposits = db.get_pending_deposits()
    if not deposits:
        await query.edit_message_text(
            "💳 *Pending Deposits*\n\n✅ No pending requests!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]))
        return
    keyboard = []
    text = f"💳 *Pending Deposits ({len(deposits)})*\n━━━━━━━━━━━━━━━━━━\n\n"
    for dep in deposits:
        text += f"🔢 #{dep['id']} — 👤 {dep['username']}\n"
        keyboard.append([InlineKeyboardButton(f"👁️ Review #{dep['id']}", callback_data=f"review_deposit_{dep['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def review_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    deposit_id = int(query.data.split("_")[2])
    deposit = db.get_deposit(deposit_id)
    if not deposit:
        await query.answer("Not found!", show_alert=True)
        return
    await context.bot.send_photo(
        chat_id=query.from_user.id, photo=deposit['photo_file_id'],
        caption=(f"💳 *Deposit #{deposit_id}*\n👤 {deposit['username']}\n🆔 `{deposit['user_id']}`\n\nChoose amount to approve:"),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("$5", callback_data=f"approve_deposit_{deposit_id}_5"),
             InlineKeyboardButton("$10", callback_data=f"approve_deposit_{deposit_id}_10"),
             InlineKeyboardButton("$20", callback_data=f"approve_deposit_{deposit_id}_20")],
            [InlineKeyboardButton("$50", callback_data=f"approve_deposit_{deposit_id}_50"),
             InlineKeyboardButton("$100", callback_data=f"approve_deposit_{deposit_id}_100")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"reject_deposit_{deposit_id}")]]))

async def approve_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    parts = query.data.split("_")
    deposit_id = int(parts[2])
    if len(parts) < 4:
        context.user_data['pending_deposit_id'] = deposit_id
        context.user_data['state'] = WAITING_ADD_BALANCE_AMOUNT
        await query.message.reply_text("Enter custom amount:")
        return
    amount = float(parts[3])
    deposit = db.get_deposit(deposit_id)
    if not deposit:
        return
    db.approve_deposit(deposit_id, amount, query.from_user.id)
    new_balance = db.get_balance(deposit['user_id'])
    try:
        await context.bot.send_message(
            chat_id=deposit['user_id'],
            text=f"✅ *Balance Added: ${amount:.2f}*\n💼 New balance: *${new_balance:.2f}*\n\nYou can now shop! 🛍️",
            parse_mode='Markdown', reply_markup=main_menu_keyboard(deposit['user_id']))
    except: pass
    try:
        await query.edit_message_caption(
            caption=f"✅ Deposit #{deposit_id} Approved — ${amount:.2f} added to {deposit['username']}",
            parse_mode='Markdown')
    except: pass

async def reject_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    deposit_id = int(query.data.split("_")[2])
    deposit = db.get_deposit(deposit_id)
    if not deposit:
        return
    db.reject_deposit(deposit_id, query.from_user.id)
    try:
        await context.bot.send_message(
            chat_id=deposit['user_id'],
            text=f"❌ *Deposit Request #{deposit_id} Rejected*\n\nPlease contact support if you think this is an error.",
            parse_mode='Markdown', reply_markup=main_menu_keyboard(deposit['user_id']))
    except: pass
    try:
        await query.edit_message_caption(caption=f"❌ Deposit #{deposit_id} Rejected", parse_mode='Markdown')
    except:
        await query.edit_message_text(f"❌ Deposit #{deposit_id} Rejected",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_deposits")]]))

# ========================
# ADMIN - PRODUCTS MANAGEMENT
# ========================

async def admin_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    products = db.get_all_products()
    keyboard = []
    text = f"📦 *Products Management*\n━━━━━━━━━━━━━━━━━━\nTotal: {len(products)} products\n\n"
    for p in products:
        emoji = "🟢" if p['stock'] > 0 else "🔴"
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {p['name']} (${p['price']:.2f}) — {p['stock']} items",
            callback_data=f"admin_product_{p['id']}")])
    keyboard.append([InlineKeyboardButton("➕ Add New Product", callback_data="admin_add_product")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    product_id = int(query.data.split("_")[2])
    product = db.get_product(product_id)
    if not product:
        await query.answer("Not found!", show_alert=True)
        return
    items = db.get_product_items(product_id)
    text = (
        f"📦 *{product['name']}*\n━━━━━━━━━━━━━━━━━━\n"
        f"📝 {product['description']}\n"
        f"💰 Price: ${product['price']:.2f}\n"
        f"🗃️ Items in stock: *{product['stock']}*\n\n"
    )
    if items:
        text += "📋 *Available Items:*\n"
        for i, item in enumerate(items[:5], 1):
            preview = item['content'][:30] + "..." if len(item['content']) > 30 else item['content']
            text += f"{i}. `{preview}` (ID: {item['id']})\n"
        if len(items) > 5:
            text += f"_... and {len(items) - 5} more_\n"
    keyboard = [
        [InlineKeyboardButton("➕ Add Item", callback_data=f"add_item_{product_id}"),
         InlineKeyboardButton("🗑️ Delete Items", callback_data=f"manage_items_{product_id}")],
        [InlineKeyboardButton("🗑️ Delete Product", callback_data=f"delete_product_{product_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_products")]
    ]
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def start_add_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    product_id = int(query.data.split("_")[2])
    product = db.get_product(product_id)
    # امسح اي state قديم وابدأ نضيف
    context.user_data.clear()
    context.user_data['adding_item_to'] = product_id
    context.user_data['state'] = WAITING_ITEM_CONTENT
    await query.edit_message_text(
        f"➕ *Add Item to: {product['name']}*\n\n"
        f"Send the item content (account details, license key, etc.)\n\n"
        f"You can send *multiple items* — send each one as a separate message.\n"
        f"When done, press the button below.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Done Adding", callback_data=f"admin_product_{product_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"admin_product_{product_id}")]]))

async def receive_item_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != WAITING_ITEM_CONTENT:
        return
    product_id = context.user_data.get('adding_item_to')
    if not product_id:
        return
    content = update.message.text.strip()
    if not content:
        return
    item_id = db.add_item_to_product(product_id, content)
    product = db.get_product(product_id)
    # State لازم يفضل زي ما هو عشان يستقبل items تانية - متمسحوش
    await update.message.reply_text(
        f"✅ *Item Added!*\n\n"
        f"📦 Product: *{product['name']}*\n"
        f"🗃️ Total in stock: *{product['stock']}*\n\n"
        f"Send another item or press *Done Adding* button.",
        parse_mode='Markdown')

async def manage_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    product_id = int(query.data.split("_")[2])
    product = db.get_product(product_id)
    items = db.get_product_items(product_id)
    if not items:
        await query.edit_message_text(
            f"📦 *{product['name']}*\n\nNo items in stock.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Item", callback_data=f"add_item_{product_id}")],
                [InlineKeyboardButton("🔙 Back", callback_data=f"admin_product_{product_id}")]]))
        return
    keyboard = []
    text = f"🗑️ *Delete Items from: {product['name']}*\n━━━━━━━━━━━━━━━━━━\n\n"
    for item in items[:10]:
        preview = item['content'][:25] + "..." if len(item['content']) > 25 else item['content']
        text += f"ID {item['id']}: `{preview}`\n"
        keyboard.append([InlineKeyboardButton(f"🗑️ Delete ID {item['id']}", callback_data=f"delete_item_{item['id']}_{product_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"admin_product_{product_id}")])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    parts = query.data.split("_")
    item_id = int(parts[2])
    product_id = int(parts[3])
    db.delete_item(item_id)
    await query.answer("✅ Item deleted!", show_alert=True)
    query.data = f"manage_items_{product_id}"
    await manage_items(update, context)

async def delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    product_id = int(query.data.split("_")[2])
    db.delete_product(product_id)
    await query.answer("✅ Product deleted!", show_alert=True)
    query.data = "admin_products"
    await admin_products(update, context)

# ========================
# ADD PRODUCT CONVERSATION
# ========================

async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data['new_product'] = {}
    context.user_data['state'] = WAITING_PRODUCT_NAME
    await query.edit_message_text(
        "➕ *Add New Product*\n\nStep 1/3: Enter the *product name*:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_products")]]))

async def get_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_product']['name'] = update.message.text
    context.user_data['state'] = WAITING_PRODUCT_DESC
    await update.message.reply_text("Step 2/3: Enter the *description*:", parse_mode='Markdown')

async def get_product_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_product']['description'] = update.message.text
    context.user_data['state'] = WAITING_PRODUCT_PRICE
    await update.message.reply_text("Step 3/3: Enter the *price* (e.g. 9.99):", parse_mode='Markdown')

async def get_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data['new_product']['price'] = price
        product = context.user_data['new_product']
        product_id = db.add_product(product['name'], product['description'], price)
        context.user_data['adding_item_to'] = product_id
        context.user_data['state'] = WAITING_ITEM_CONTENT
        await update.message.reply_text(
            f"✅ *Product Created: {product['name']}*\n\n"
            f"Now add items (accounts/keys) one by one.\n"
            f"Send each item as a separate message.\n\n"
            f"Example:\n`email@gmail.com:password123`\nor\n`XXXX-XXXX-XXXX-XXXX`",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Done", callback_data=f"admin_product_{product_id}")]]))
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number (e.g. 9.99)")

# ========================
# ADMIN USERS
# ========================

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    users = db.get_all_users()
    text = f"👥 *All Users ({len(users)})*\n━━━━━━━━━━━━━━━━━━\n\n"
    for user in users[:20]:
        text += f"👤 {user['name']} — 💰 ${user['balance']:.2f}\n"
    if len(users) > 20:
        text += f"\n_... and {len(users) - 20} more_"
    await query.edit_message_text(text, parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]))

# ========================
# HANDLE TEXT - المشكله كانت هنا
# ========================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')

    if state == WAITING_PRODUCT_NAME:
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
        await update.message.reply_text("📸 Please send a *photo* of your receipt.", parse_mode='Markdown')

    elif state == WAITING_ADD_BALANCE_AMOUNT:
        try:
            amount = float(update.message.text)
            deposit_id = context.user_data.get('pending_deposit_id')
            if deposit_id:
                deposit = db.get_deposit(deposit_id)
                db.approve_deposit(deposit_id, amount, update.effective_user.id)
                new_balance = db.get_balance(deposit['user_id'])
                try:
                    await context.bot.send_message(
                        chat_id=deposit['user_id'],
                        text=f"✅ *Balance Added: ${amount:.2f}*\n💼 New balance: *${new_balance:.2f}*",
                        parse_mode='Markdown',
                        reply_markup=main_menu_keyboard(deposit['user_id']))
                except:
                    pass
                await update.message.reply_text(
                    f"✅ Deposit #{deposit_id} approved! Added ${amount:.2f}",
                    reply_markup=admin_panel_keyboard())
                context.user_data.pop('state', None)
                context.user_data.pop('pending_deposit_id', None)
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid amount")

# ========================
# CALLBACK ROUTER
# ========================

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # لما الادمن يضغط اي زرار غير add item، امسح state الـ item content
    if context.user_data.get('state') == WAITING_ITEM_CONTENT:
        if not data.startswith("admin_product_"):
            context.user_data.pop('state', None)
            context.user_data.pop('adding_item_to', None)

    routes = {
        "main_menu": start,
        "products": show_products,
        "wallet": show_wallet,
        "add_balance": add_balance_start,
        "my_orders": show_orders,
        "help": show_help,
        "admin_panel": admin_panel,
        "admin_deposits": admin_deposits,
        "admin_products": admin_products,
        "admin_users": admin_users,
        "admin_stats": admin_panel,
    }
    if data in routes:
        await routes[data](update, context)
    elif data.startswith("product_"):
        await show_product_detail(update, context)
    elif data.startswith("buy_"):
        await buy_product(update, context)
    elif data.startswith("confirm_buy_"):
        await confirm_buy(update, context)
    elif data.startswith("approve_deposit_"):
        await approve_deposit(update, context)
    elif data.startswith("reject_deposit_"):
        await reject_deposit(update, context)
    elif data.startswith("review_deposit_"):
        await review_deposit(update, context)
    elif data.startswith("admin_product_"):
        # لما يضغط Done Adding يمسح الـ state
        context.user_data.pop('state', None)
        context.user_data.pop('adding_item_to', None)
        await admin_product_detail(update, context)
    elif data.startswith("admin_add_product"):
        await start_add_product(update, context)
    elif data.startswith("delete_product_"):
        await delete_product(update, context)
    elif data.startswith("add_item_"):
        await start_add_item(update, context)
    elif data.startswith("manage_items_"):
        await manage_items(update, context)
    elif data.startswith("delete_item_"):
        await delete_item(update, context)

# ========================
# MAIN
# ========================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, receive_payment_proof))

    print("🤖 Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
