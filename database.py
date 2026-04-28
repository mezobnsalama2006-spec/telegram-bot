import sqlite3
import datetime
from contextlib import contextmanager

DB_PATH = "bot_database.db"

class Database:
    def __init__(self):
        self._create_tables()
    
    @contextmanager
    def get_conn(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _create_tables(self):
        with self.get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    name TEXT,
                    balance REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS product_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    is_sold INTEGER DEFAULT 0,
                    sold_to INTEGER DEFAULT NULL,
                    sold_at TIMESTAMP DEFAULT NULL,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );
                
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    product_id INTEGER,
                    product_name TEXT,
                    item_id INTEGER,
                    price REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                
                CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    photo_file_id TEXT,
                    amount REAL DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    approved_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    type TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
            """)
    
    def add_user(self, user_id, username, name):
        with self.get_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO users (id, username, name) VALUES (?, ?, ?)",
                        (user_id, username, name))
    
    def get_balance(self, user_id):
        with self.get_conn() as conn:
            row = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
            return row['balance'] if row else 0.0
    
    def get_all_users(self):
        with self.get_conn() as conn:
            return [dict(row) for row in conn.execute(
                "SELECT id, username, name, balance FROM users ORDER BY created_at DESC").fetchall()]
    
    def get_all_products(self):
        with self.get_conn() as conn:
            rows = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
            products = []
            for row in rows:
                p = dict(row)
                p['stock'] = conn.execute(
                    "SELECT COUNT(*) as c FROM product_items WHERE product_id = ? AND is_sold = 0",
                    (p['id'],)).fetchone()['c']
                products.append(p)
            return products
    
    def get_product(self, product_id):
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            if not row:
                return None
            p = dict(row)
            p['stock'] = conn.execute(
                "SELECT COUNT(*) as c FROM product_items WHERE product_id = ? AND is_sold = 0",
                (product_id,)).fetchone()['c']
            return p
    
    def add_product(self, name, description, price):
        with self.get_conn() as conn:
            cursor = conn.execute("INSERT INTO products (name, description, price) VALUES (?, ?, ?)",
                                 (name, description, price))
            return cursor.lastrowid
    
    def delete_product(self, product_id):
        with self.get_conn() as conn:
            conn.execute("DELETE FROM product_items WHERE product_id = ?", (product_id,))
            conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    
    def add_item_to_product(self, product_id, content):
        with self.get_conn() as conn:
            cursor = conn.execute("INSERT INTO product_items (product_id, content) VALUES (?, ?)",
                                 (product_id, content))
            return cursor.lastrowid
    
    def get_product_items(self, product_id, show_sold=False):
        with self.get_conn() as conn:
            if show_sold:
                rows = conn.execute("SELECT * FROM product_items WHERE product_id = ? ORDER BY id DESC",
                                   (product_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM product_items WHERE product_id = ? AND is_sold = 0 ORDER BY id ASC",
                                   (product_id,)).fetchall()
            return [dict(row) for row in rows]
    
    def delete_item(self, item_id):
        with self.get_conn() as conn:
            conn.execute("DELETE FROM product_items WHERE id = ? AND is_sold = 0", (item_id,))
    
    def get_item(self, item_id):
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM product_items WHERE id = ?", (item_id,)).fetchone()
            return dict(row) if row else None

    def purchase_product(self, user_id, product_id):
        with self.get_conn() as conn:
            product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if not product or not user:
                return False, "Product or user not found"
            item = conn.execute(
                "SELECT * FROM product_items WHERE product_id = ? AND is_sold = 0 ORDER BY id ASC LIMIT 1",
                (product_id,)).fetchone()
            if not item:
                return False, "Product is out of stock"
            if user['balance'] < product['price']:
                return False, "Insufficient balance"
            new_balance = user['balance'] - product['price']
            conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
            conn.execute("UPDATE product_items SET is_sold = 1, sold_to = ?, sold_at = ? WHERE id = ?",
                        (user_id, datetime.datetime.now(), item['id']))
            conn.execute("INSERT INTO orders (user_id, product_id, product_name, item_id, price) VALUES (?, ?, ?, ?, ?)",
                        (user_id, product_id, product['name'], item['id'], product['price']))
            conn.execute("INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
                        (user_id, -product['price'], 'purchase', f"Bought: {product['name']}"))
            return True, {'content': item['content'], 'new_balance': new_balance, 'product_name': product['name']}
    
    def get_user_orders(self, user_id):
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT o.*, strftime('%Y-%m-%d', o.created_at) as date, pi.content FROM orders o LEFT JOIN product_items pi ON o.item_id = pi.id WHERE o.user_id = ? ORDER BY o.created_at DESC",
                (user_id,)).fetchall()
            return [dict(row) for row in rows]
    
    def get_transactions(self, user_id, limit=10):
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)).fetchall()
            return [dict(row) for row in rows]
    
    def create_deposit_request(self, user_id, photo_file_id, amount=0):
        with self.get_conn() as conn:
            user = conn.execute("SELECT username, name FROM users WHERE id = ?", (user_id,)).fetchone()
            username = user['username'] if user else str(user_id)
            cursor = conn.execute("INSERT INTO deposits (user_id, username, photo_file_id, amount) VALUES (?, ?, ?, ?)",
                                 (user_id, username, photo_file_id, amount))
            return cursor.lastrowid
    
    def get_pending_deposits(self):
        with self.get_conn() as conn:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM deposits WHERE status = 'pending' ORDER BY created_at DESC").fetchall()]
    
    def get_deposit(self, deposit_id):
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM deposits WHERE id = ?", (deposit_id,)).fetchone()
            return dict(row) if row else None
    
    def approve_deposit(self, deposit_id, amount, admin_id):
        with self.get_conn() as conn:
            deposit = conn.execute("SELECT * FROM deposits WHERE id = ?", (deposit_id,)).fetchone()
            if not deposit:
                return False
            conn.execute("UPDATE deposits SET status = 'approved', amount = ?, approved_by = ?, updated_at = ? WHERE id = ?",
                        (amount, admin_id, datetime.datetime.now(), deposit_id))
            conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, deposit['user_id']))
            conn.execute("INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
                        (deposit['user_id'], amount, 'deposit', f"Deposit approved #{deposit_id}"))
            return True
    
    def reject_deposit(self, deposit_id, admin_id):
        with self.get_conn() as conn:
            conn.execute("UPDATE deposits SET status = 'rejected', approved_by = ?, updated_at = ? WHERE id = ?",
                        (admin_id, datetime.datetime.now(), deposit_id))
    
    def get_stats(self):
        with self.get_conn() as conn:
            users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
            products = conn.execute("SELECT COUNT(*) as c FROM products").fetchone()['c']
            orders = conn.execute("SELECT COUNT(*) as c FROM orders").fetchone()['c']
            revenue = conn.execute("SELECT SUM(price) as s FROM orders").fetchone()['s'] or 0.0
            pending = conn.execute("SELECT COUNT(*) as c FROM deposits WHERE status = 'pending'").fetchone()['c']
            total_items = conn.execute("SELECT COUNT(*) as c FROM product_items WHERE is_sold = 0").fetchone()['c']
            return {'users': users, 'products': products, 'orders': orders,
                    'revenue': revenue, 'pending_deposits': pending, 'total_items': total_items}
