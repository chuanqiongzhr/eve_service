import requests
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

def get_system_id():
    url = 'https://esi.evetech.net/latest/universe/systems/?datasource=tranquility'
    response = requests.get(url)
    return response.json()

def get_system_name(system_id):
    url = f'https://esi.evetech.net/latest/universe/systems/{system_id}/?datasource=tranquility&language=zh'
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return system_id, response.json().get('name', '未知系统')
        else:
            print(f"获取系统ID {system_id} 名称失败，状态码: {response.status_code}")
            return system_id, None
    except Exception as e:
        print(f"获取系统ID {system_id} 名称异常: {e}")
        return system_id, None

def save_system_names_to_db(system_name_dict):
    conn = sqlite3.connect('flask-template/scripts/eve_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_ids (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
    ''')
    data = [(sid, name) for sid, name in system_name_dict.items() if name]
    cursor.executemany('INSERT OR REPLACE INTO system_ids (id, name) VALUES (?, ?)', data)
    conn.commit()
    conn.close()
    print(f"已写入{len(data)}个系统ID和名称到数据库")



if __name__ == '__main__':
    system_ids = get_system_id()
    print(f"获取到{len(system_ids)}个系统ID")

    system_name_dict = {}
    with ThreadPoolExecutor(max_workers=40) as executor:
        futures = {executor.submit(get_system_name, sid): sid for sid in system_ids}
        for future in tqdm(as_completed(futures), total=len(system_ids), desc="获取系统名称"):
            sid, name = future.result()
            system_name_dict[sid] = name

    print("系统名称获取完成")
    save_system_names_to_db(system_name_dict)