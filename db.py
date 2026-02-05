import aiosqlite

DB_NAME = 'aho_requests.db'

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # 1. Таблица заявок (добавили поле user_fio)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                user_fio TEXT, 
                category TEXT,
                urgency TEXT,
                location TEXT,
                description TEXT,
                photo_id TEXT,
                status TEXT DEFAULT '🆕 Новая'
            )
        ''')
        
        # 2. НОВАЯ Таблица пользователей (чтобы помнить ФИО)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                fio TEXT
            )
        ''')
        await db.commit()

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С ЮЗЕРАМИ ---

async def get_user_fio(user_id):
    """Проверяем, есть ли такой юзер в базе. Возвращает ФИО или None"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT fio FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def register_user(user_id, fio):
    """Запоминаем нового сотрудника"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT OR REPLACE INTO users (user_id, fio) VALUES (?, ?)', (user_id, fio))
        await db.commit()

# --- ФУНКЦИИ ЗАЯВОК ---

async def add_request(data):
    async with aiosqlite.connect(DB_NAME) as db:
        # Теперь сохраняем и user_fio
        cursor = await db.execute('''
            INSERT INTO requests (user_id, username, user_fio, category, urgency, location, description, photo_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id
        ''', (data['user_id'], data['username'], data['user_fio'], data['category'], data['urgency'], 
              data['location'], data['description'], data.get('photo_id')))
        row = await cursor.fetchone()
        await db.commit()
        return row[0]

async def update_status(req_id, new_status):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE requests SET status = ? WHERE id = ?', (new_status, req_id))
        await db.commit()

async def get_request(req_id):
    async with aiosqlite.connect(DB_NAME) as db:
        # Достаем еще и описание (для уведомлений)
        async with db.execute('SELECT user_id, description FROM requests WHERE id = ?', (req_id,)) as cursor:
            return await cursor.fetchone()
            
async def get_user_requests(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT id, category, status, description FROM requests WHERE user_id = ? ORDER BY id DESC LIMIT 10', (user_id,)) as cursor:
            return await cursor.fetchall()

async def get_active_requests_for_admin():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        # Добавили user_fio в выборку
        query = "SELECT * FROM requests WHERE status NOT IN ('Выполнено ✅', 'Отклонено ❌') ORDER BY id ASC"
        async with db.execute(query) as cursor:
            return await cursor.fetchall()