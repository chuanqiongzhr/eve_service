import requests
import sqlite3
from tqdm import tqdm

def get_region_ids():
    """获取所有region的ID"""
    while True:
        url = f'https://esi.evetech.net/latest/universe/regions/?datasource=tranquility'
        response = requests.get(url).json()
        if response:
            return response
        else:
            print("获取region ID失败，正在重试...")
            continue    

def get_region_name(region_ids):
    """获取region的详细信息"""
    region_info = []
    region_name = {}
    for region_id in tqdm(region_ids, desc="获取region信息"):
        url = f'https://esi.evetech.net/latest/universe/regions/{region_id}/?datasource=tranquility&language=zh'
        response = requests.get(url)
        if response.status_code == 200:
            region_info.append(response.json())
        else:
            print(f"获取region ID {region_id} 信息失败，状态码: {response.status_code}")
    for region_id ,region_info in zip(region_ids, region_info):
        region_name[region_id] = region_info.get('name', '未知区域')
    return region_name

def save_region_ids_to_db(region_name_dict):
    conn = sqlite3.connect('flask-template\scripts\eve_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS region_ids (
            id INTEGER PRIMARY KEY
        )
    ''')
    cursor.execute('ALTER TABLE region_ids ADD COLUMN name TEXT')
    data = [(rid, name) for rid, name in region_name_dict.items()]
    cursor.executemany('INSERT OR REPLACE INTO region_ids (id, name) VALUES (?, ?)', data)
    conn.commit()
    conn.close()
    print(f"已写入{len(region_name_dict)}个region ID和名称到数据库")

if __name__ == '__main__':
    print("开始获取region ID...")
    region_ids = get_region_ids()
    print(f"获取到{len(region_ids)}个region ID")
    print("开始获取region名称...")
    region_name = get_region_name(region_ids)
    print(region_name)
    print("获取region名称完成")
    save_region_ids_to_db(region_name)


