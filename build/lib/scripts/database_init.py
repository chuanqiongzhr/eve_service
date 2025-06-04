import sqlite3
import requests
import concurrent.futures
from tqdm import tqdm  # 顶部导入

def get_type_ids():
    result = []
    page = 1
    while True:
        url = f'https://esi.evetech.net/latest/universe/types/?datasource=tranquility&page={page}'
        if requests.get(url).status_code != 200:
            print(f'id页面有{page - 1}页')
            break
        response = requests.get(url).json()
        result.extend(response)
        print(f'获取第{page}页的id')
        page += 1
    
    result = sorted(result)

    return result

def create_database():
    '''创建数据库并插入type_ids'''
    conn = sqlite3.connect('eve_data.db')
    cursor = conn.cursor()
    
    # Create a table for type IDs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS type_ids (
            id INTEGER PRIMARY KEY
        )
    ''')
    
    # Insert type IDs into the database
    type_ids = get_type_ids()
    for type_id in type_ids:
        cursor.execute('INSERT OR IGNORE INTO type_ids (id) VALUES (?)', (type_id,))
    
    conn.commit()
    conn.close()

def get_type_ids_from_db():
    '''从数据库中获取type_ids'''
    conn = sqlite3.connect('scripts/eve_data.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM type_ids')
    type_ids = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return type_ids

def from_ids_get_info(type_ids):
    for ids in type_ids:
        url = f'https://esi.evetech.net/latest/universe/types/{ids}/?datasource=tranquility&language=zh'
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def chunks(lst, n):
    """将列表 lst 拆分为每个长度为 n 的小列表"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def fetch_type_info(type_id):
    url = f'https://esi.evetech.net/latest/universe/types/{type_id}/?datasource=tranquility&language=zh'
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        info = response.json()
        return (
            type_id,
            info.get('capacity'),
            info.get('description'),
            info.get('group_id'),
            info.get('icon_id'),
            info.get('market_group_id'),
            info.get('mass'),
            info.get('name'),
            info.get('packaged_volume'),
            info.get('portion_size'),
            info.get('published'),
            info.get('radius'),
            info.get('type_name'),
            info.get('volume')
        )
    except Exception as e:
        print(f"获取 type_id {type_id} 失败: {e}")
        return None
    
def fetch_en_type_info(type_id):
    url = f'https://esi.evetech.net/latest/universe/types/{type_id}/?datasource=tranquility&language=en'
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        info = response.json()
        return (
            info.get('description'),
            info.get('name'),
            type_id
        )
    except Exception as e:
        print(f"获取 type_id {type_id} 失败: {e}")
        return None

def add_info_to_db(type_ids, batch_size=200, max_workers=100):
    '''并发抓取并批量写入数据库，带进度条'''
    conn = sqlite3.connect('scripts/eve_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS type_info (
            type_id INTEGER PRIMARY KEY,
            capacity REAL,
            description TEXT,
            group_id INTEGER,
            icon_id INTEGER,
            market_group_id INTEGER,
            mass REAL,
            name TEXT,
            packaged_volume REAL,
            portion_size INTEGER,
            published BOOLEAN,
            radius REAL,
            type_name TEXT,
            volume REAL
        )
    ''')

    total = len(type_ids)
    processed = 0
    for batch in tqdm(chunks(type_ids, batch_size), total=(total // batch_size + 1), desc="写入进度"):
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(fetch_type_info, batch))
        results = [r for r in results if r is not None]
        cursor.executemany('''
            INSERT OR REPLACE INTO type_info (
                type_id, capacity, description, group_id, icon_id, market_group_id,
                mass, name, packaged_volume, portion_size, published, radius, type_name, volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', results)
        conn.commit()
        processed += len(results)

    conn.close()
    print("全部type_id信息已写入数据库")

def add_en_info_to_db(type_ids, batch_size=200, max_workers=400):
    '''并发抓取并批量写入数据库，带进度条'''
    conn = sqlite3.connect('scripts/eve_data.db')
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE type_info ADD COLUMN en_description TEXT")
    except sqlite3.OperationalError:
        pass  # 列已存在则忽略
    try:
        cursor.execute("ALTER TABLE type_info ADD COLUMN en_name TEXT")
    except sqlite3.OperationalError:
        pass  # 列已存在则忽略
    total = len(type_ids)
    processed = 0
    for batch in tqdm(chunks(type_ids, batch_size), total=(total // batch_size + 1), desc="写入进度"):
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(fetch_en_type_info, batch))
        results = [r for r in results if r is not None]
        cursor.executemany('''
            UPDATE type_info
            SET en_description = ?, en_name = ?
            WHERE type_id = ?
        ''', results)
        conn.commit()
        processed += len(results)

    conn.close()
    print("全部en_type_id信息已写入数据库")

def get_single_type_info(type_id):
    '''获取单个type_id的信息'''
    url = f'https://esi.evetech.net/latest/universe/types/{type_id}/?datasource=tranquility&language=zh'
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    type_ids = get_type_ids_from_db()
    add_en_info_to_db(type_ids)
    print("数据库初始化完成，type_ids信息已添加。")