import aiosqlite

async def init_db():
    
    # sessions(id,server,started_at,last_at,call_count), calls(id,session_id,ts,direction,tool_name,input,output,latency_ms,status,flags)
    
    db = await aiosqlite.connect('sessions.db')
    
    await db.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        server TEXT,
        started_at TIMESTAMP,
        last_at TIMESTAMP,
        call_count INTEGER
    )
    ''')
    
    await db.execute('''
    CREATE TABLE IF NOT EXISTS calls (
        id TEXT PRIMARY KEY,
        session_id TEXT,
        ts TIMESTAMP,
        direction TEXT,
        tool_name TEXT,
        input TEXT,
        output TEXT,
        latency_ms INTEGER,
        status TEXT,
        flags TEXT
    )
    ''')
    
    await db.commit()
    return db
    
async def insert_call(path, record):
    db = await aiosqlite.connect(path)
    await db.execute('''
    INSERT INTO calls (id, session_id, ts, direction, tool_name, input, output, latency_ms, status, flags)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        record['id'],
        record['session_id'],
        record['ts'],
        record['direction'],
        record['tool_name'],
        record['input'],
        record['output'],
        record['latency_ms'],
        record['status'],
        record['flags']
    ))
    await db.commit()
    await db.close()
    
async def list_calls(path, **filters):
    db = await aiosqlite.connect(path)
    query = 'SELECT * FROM calls'
    conditions = []
    values = []
    
    for key, value in filters.items():
        conditions.append(f"{key} = ?")
        values.append(value)
    
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    
    async with db.execute(query, values) as cursor:
        rows = await cursor.fetchall()
    
    await db.close()
    return rows

async def get_session(path, sid):
    db = await aiosqlite.connect(path)
    async with db.execute('SELECT * FROM sessions WHERE id = ?', (sid,)) as cursor:
        session = await cursor.fetchone()
    await db.close()
    return session

async def get_flags(path, sid):
    db = await aiosqlite.connect(path)
    async with db.execute('SELECT flags FROM calls WHERE session_id = ?', (sid,)) as cursor:
        rows = await cursor.fetchall()
    await db.close()
    return [row[0] for row in rows]