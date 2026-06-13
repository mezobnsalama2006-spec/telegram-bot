import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_path="store.db"):
        self.db_path = db_path
        self.init_db()

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_conn()
        c = conn.cursor()

        # Users
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            name TEXT,
            balance REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        # Categories (e.g. متابعين, لايكات, مشاهدات)
        c.execute('''CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '📁',
            position INTEGER DEFAULT 0
        )''')

        # Apps inside categories (e.g. Instagram, Facebook, TikTok)
        c.execute('''CREATE TABLE IF NOT EXISTS apps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '📱',
            position INTEGER DEFAULT 0,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )''')

        # Products — now linked to app (and indirectly to category)
        c.execute('''CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (app_id) REFERENCES apps(id)
        )''')

        # Items (the actual deliverable content)
        c.execute('''CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            is_sold INTEGER DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )''')

        # Orders
        c.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            price REAL NOT NULL,
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )''')

        # Deposits
        c.execute('''CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            photo_file_id TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            approved_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        # Transactions
        c.execute('''CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            date TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        conn.commit()
        conn.close()

    # ── USERS ──────────────────────────────────────────────

    def add_user(self, user_id, username, name):
        conn = self.get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, name) VALUES (?,?,?)",
            (user_id, username, name)
        )
        conn.commit()
        conn.close()

    def get_balance(self, user_id):
        conn = self.get_conn()
        row = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()
        conn.close()
        return row['balance'] if row else 0

    def get_all_users(self):
        conn = self.get_conn()
        rows = conn.execute("SELECT * FROM users ORDER BY balance DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_transactions(self, user_id, limit=10):
        conn = self.get_conn()
        rows = conn.execute(
            "SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── CATEGORIES ─────────────────────────────────────────

    def add_category(self, name, emoji="📁"):
        conn = self.get_conn()
        c = conn.cursor()
        pos = (c.execute("SELECT COUNT(*) FROM categories").fetchone()[0])
        c.execute("INSERT INTO categories (name, emoji, position) VALUES (?,?,?)", (name, emoji, pos))
        cat_id = c.lastrowid
        conn.commit()
        conn.close()
        return cat_id

    def get_all_categories(self):
        conn = self.get_conn()
        rows = conn.execute("SELECT * FROM categories ORDER BY position").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_category(self, cat_id):
        conn = self.get_conn()
        row = conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def delete_category(self, cat_id):
        conn = self.get_conn()
        # cascade: delete apps → products → items
        app_ids = [r[0] for r in conn.execute("SELECT id FROM apps WHERE category_id=?", (cat_id,)).fetchall()]
        for app_id in app_ids:
            prod_ids = [r[0] for r in conn.execute("SELECT id FROM products WHERE app_id=?", (app_id,)).fetchall()]
            for pid in prod_ids:
                conn.execute("DELETE FROM items WHERE product_id=?", (pid,))
            conn.execute("DELETE FROM products WHERE app_id=?", (app_id,))
        conn.execute("DELETE FROM apps WHERE category_id=?", (cat_id,))
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        conn.commit()
        conn.close()

    # ── APPS ───────────────────────────────────────────────

    def add_app(self, category_id, name, emoji="📱"):
        conn = self.get_conn()
        c = conn.cursor()
        pos = (c.execute("SELECT COUNT(*) FROM apps WHERE category_id=?", (category_id,)).fetchone()[0])
        c.execute("INSERT INTO apps (category_id, name, emoji, position) VALUES (?,?,?,?)", (category_id, name, emoji, pos))
        app_id = c.lastrowid
        conn.commit()
        conn.close()
        return app_id

    def get_apps_by_category(self, category_id):
        conn = self.get_conn()
        rows = conn.execute(
            "SELECT * FROM apps WHERE category_id=? ORDER BY position", (category_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_app(self, app_id):
        conn = self.get_conn()
        row = conn.execute("SELECT * FROM apps WHERE id=?", (app_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def delete_app(self, app_id):
        conn = self.get_conn()
        prod_ids = [r[0] for r in conn.execute("SELECT id FROM products WHERE app_id=?", (app_id,)).fetchall()]
        for pid in prod_ids:
            conn.execute("DELETE FROM items WHERE product_id=?", (pid,))
        conn.execute("DELETE FROM products WHERE app_id=?", (app_id,))
        conn.execute("DELETE FROM apps WHERE id=?", (app_id,))
        conn.commit()
        conn.close()

    # ── PRODUCTS ───────────────────────────────────────────

    def add_product(self, name, description, price, app_id=None):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO products (name, description, price, app_id) VALUES (?,?,?,?)",
            (name, description, price, app_id)
        )
        pid = c.lastrowid
        conn.commit()
        conn.close()
        return pid

    def get_all_products(self):
        conn = self.get_conn()
        rows = conn.execute("""
            SELECT p.*, COALESCE(COUNT(i.id),0) as stock
            FROM products p
            LEFT JOIN items i ON i.product_id = p.id AND i.is_sold=0
            GROUP BY p.id
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_products_by_app(self, app_id):
        conn = self.get_conn()
        rows = conn.execute("""
            SELECT p.*, COALESCE(COUNT(i.id),0) as stock
            FROM products p
            LEFT JOIN items i ON i.product_id = p.id AND i.is_sold=0
            WHERE p.app_id=?
            GROUP BY p.id
        """, (app_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_product(self, product_id):
        conn = self.get_conn()
        row = conn.execute("""
            SELECT p.*, COALESCE(COUNT(i.id),0) as stock
            FROM products p
            LEFT JOIN items i ON i.product_id = p.id AND i.is_sold=0
            WHERE p.id=?
            GROUP BY p.id
        """, (product_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def delete_product(self, product_id):
        conn = self.get_conn()
        conn.execute("DELETE FROM items WHERE product_id=?", (product_id,))
        conn.execute("DELETE FROM products WHERE id=?", (product_id,))
        conn.commit()
        conn.close()

    # ── ITEMS ──────────────────────────────────────────────

    def add_item_to_product(self, product_id, content):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("INSERT INTO items (product_id, content) VALUES (?,?)", (product_id, content))
        item_id = c.lastrowid
        conn.commit()
        conn.close()
        return item_id

    def get_product_items(self, product_id):
        conn = self.get_conn()
        rows = conn.execute(
            "SELECT * FROM items WHERE product_id=? AND is_sold=0", (product_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def delete_item(self, item_id):
        conn = self.get_conn()
        conn.execute("DELETE FROM items WHERE id=?", (item_id,))
        conn.commit()
        conn.close()

    # ── PURCHASE ───────────────────────────────────────────

    def purchase_product(self, user_id, product_id):
        conn = self.get_conn()
        try:
            product = conn.execute("""
                SELECT p.*, COALESCE(COUNT(i.id),0) as stock
                FROM products p
                LEFT JOIN items i ON i.product_id=p.id AND i.is_sold=0
                WHERE p.id=?
                GROUP BY p.id
            """, (product_id,)).fetchone()

            if not product or product['stock'] == 0:
                return False, "Product out of stock"

            balance_row = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()
            balance = balance_row['balance'] if balance_row else 0

            if balance < product['price']:
                return False, "Insufficient balance"

            item = conn.execute(
                "SELECT * FROM items WHERE product_id=? AND is_sold=0 LIMIT 1", (product_id,)
            ).fetchone()

            conn.execute("UPDATE items SET is_sold=1 WHERE id=?", (item['id'],))
            conn.execute("UPDATE users SET balance=balance-? WHERE id=?", (product['price'], user_id))
            conn.execute(
                "INSERT INTO orders (user_id, product_id, item_id, price) VALUES (?,?,?,?)",
                (user_id, product_id, item['id'], product['price'])
            )
            conn.execute(
                "INSERT INTO transactions (user_id, amount, type, description) VALUES (?,?,?,?)",
                (user_id, -product['price'], 'purchase', f"Bought: {product['name']}")
            )
            conn.commit()
            new_balance = balance - product['price']
            return True, {
                'product_name': product['name'],
                'content': item['content'],
                'new_balance': new_balance
            }
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    # ── ORDERS ─────────────────────────────────────────────

    def get_user_orders(self, user_id):
        conn = self.get_conn()
        rows = conn.execute("""
            SELECT o.*, p.name as product_name, i.content
            FROM orders o
            JOIN products p ON o.product_id = p.id
            JOIN items i ON o.item_id = i.id
            WHERE o.user_id=?
            ORDER BY o.date DESC
        """, (user_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── DEPOSITS ───────────────────────────────────────────

    def create_deposit_request(self, user_id, photo_file_id, amount):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO deposits (user_id, photo_file_id, amount) VALUES (?,?,?)",
            (user_id, photo_file_id, amount)
        )
        dep_id = c.lastrowid
        conn.commit()
        conn.close()
        return dep_id

    def get_pending_deposits(self):
        conn = self.get_conn()
        rows = conn.execute("""
            SELECT d.*, u.username, u.name
            FROM deposits d JOIN users u ON d.user_id=u.id
            WHERE d.status='pending'
            ORDER BY d.created_at
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_deposit(self, deposit_id):
        conn = self.get_conn()
        row = conn.execute("""
            SELECT d.*, u.username, u.name
            FROM deposits d JOIN users u ON d.user_id=u.id
            WHERE d.id=?
        """, (deposit_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def approve_deposit(self, deposit_id, amount, admin_id):
        conn = self.get_conn()
        dep = conn.execute("SELECT * FROM deposits WHERE id=?", (deposit_id,)).fetchone()
        if not dep:
            conn.close()
            return
        conn.execute(
            "UPDATE deposits SET status='approved', approved_by=? WHERE id=?",
            (admin_id, deposit_id)
        )
        conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, dep['user_id']))
        conn.execute(
            "INSERT INTO transactions (user_id, amount, type, description) VALUES (?,?,?,?)",
            (dep['user_id'], amount, 'deposit', f"Deposit approved #{deposit_id}")
        )
        conn.commit()
        conn.close()

    def reject_deposit(self, deposit_id, admin_id):
        conn = self.get_conn()
        conn.execute(
            "UPDATE deposits SET status='rejected', approved_by=? WHERE id=?",
            (admin_id, deposit_id)
        )
        conn.commit()
        conn.close()

    # ── STATS ──────────────────────────────────────────────

    def get_stats(self):
        conn = self.get_conn()
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        categories = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        apps = conn.execute("SELECT COUNT(*) FROM apps").fetchone()[0]
        total_items = conn.execute("SELECT COUNT(*) FROM items WHERE is_sold=0").fetchone()[0]
        orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        revenue = conn.execute("SELECT COALESCE(SUM(price),0) FROM orders").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM deposits WHERE status='pending'").fetchone()[0]
        conn.close()
        return {
            'users': users,
            'products': products,
            'categories': categories,
            'apps': apps,
            'total_items': total_items,
            'orders': orders,
            'revenue': revenue,
            'pending_deposits': pending
        }
