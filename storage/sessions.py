import aiosqlite

async def ensure_session(path, sid, server):
    db = await aiosqlite.connect(path)
    cursor = await db.execute('SELECT * FROM sessions WHERE id = ?', (sid,))
    session = await cursor.fetchone()
    
    if session is None:
        await db.execute('''
        INSERT INTO sessions (id, server, started_at, last_at, call_count)
        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)
        ''', (sid, server))
        await db.commit()
    
    await db.close()

async def touch(path, sid):
    db = await aiosqlite.connect(path)
    await db.execute('''
    UPDATE sessions
    SET last_at = CURRENT_TIMESTAMP
    WHERE id = ?
    ''', (sid,))
    await db.commit()
    await db.close()
    
async def list_sessions(path):
    db = await aiosqlite.connect(path)
    cursor = await db.execute('SELECT * FROM sessions')
    sessions = await cursor.fetchall()
    await db.close()
    return sessions

async def session_summary(path, sid):
    db = await aiosqlite.connect(path)
    async with db.execute('SELECT * FROM sessions WHERE id = ?', (sid,)) as cursor:
        session = await cursor.fetchone()
    
    async with db.execute('SELECT COUNT(*) FROM calls WHERE session_id = ?', (sid,)) as cursor:
        call_count = await cursor.fetchone()
    
    await db.close()
    
    if session is None:
        return None
    
    return {
        'id': session[0],
        'server': session[1],
        'started_at': session[2],
        'last_at': session[3],
        'call_count': call_count[0]
    }
    
