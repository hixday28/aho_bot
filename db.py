import aiosqlite

DB_NAME = 'aho_requests.db'

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                category TEXT,
                urgency TEXT,
                location TEXT,
                description TEXT,
                photo_id TEXT,
                status TEXT DEFAULT '🆕 Новая'
            )
        ''')
        await db.commit()

async def add_request(data):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('''
            INSERT INTO requests (user_id, username, category, urgency, location, description, photo_id)
            VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id
        ''', (data['user_id'], data['username'], data['category'], data['urgency'], 
              data['location'], data['description'], data.get('photo_id')))
        row = await cursor.fetchone()
        await db.commit()
        return row[0] # Возвращаем номер заявки

async def update_status(req_id, new_status):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE requests SET status = ? WHERE id = ?', (new_status, req_id))
        await db.commit()

async def get_request(req_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT user_id, description FROM requests WHERE id = ?', (req_id,)) as cursor:
            return await cursor.fetchone()
            
async def get_user_requests(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT id, category, status FROM requests WHERE user_id = ? ORDER BY id DESC LIMIT 10', (user_id,)) as cursor:
            return await cursor.fetchall()


async def get_active_requests_for_admin():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        # Берем всё, что НЕ выполнено и НЕ отклонено
        query = "SELECT * FROM requests WHERE status NOT IN ('Выполнено ✅', 'Отклонено ❌')"
        async with db.execute(query) as cursor:
            return await cursor.fetchall()