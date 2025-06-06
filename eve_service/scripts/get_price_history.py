import requests
import sqlite3
import os

def get_price_history(type_id,region_id):
    """获取指定类型和区域的价格"""
    url = f'https://esi.evetech.net/latest/markets/{region_id}/history/?datasource=tranquility&type_id={type_id}'
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"获取价格失败，状态码: {response.status_code}")
        return None

def name_to_id(name):
    """将名称转换为ID，支持中英文名称搜索（大小写不敏感）"""
    db_path = os.path.join(os.path.dirname(__file__), 'eve_data.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # 先尝试中文名称搜索（大小写不敏感）
    cursor.execute('SELECT type_id, name FROM type_info WHERE LOWER(name) = LOWER(?)', (name,))
    result = cursor.fetchone()
    if not result:
        # 如果中文名称没找到，尝试英文名称搜索（大小写不敏感）
        cursor.execute('SELECT type_id, name FROM type_info WHERE LOWER(en_name) = LOWER(?)', (name,))
        result = cursor.fetchone()
    conn.close()
    if result:
        return result[0], result[1]  # 返回 (type_id, name)
    else:
        print(f"未找到名称为 {name} 的ID")
        return None, None


if __name__ == '__main__':
    name = input("请输入物品名称: ")
    # name = 'plex'
    type_id, chinese_name = name_to_id(name)
    if type_id:
        print(f"物品 {chinese_name} 的ID为: {type_id}")
    region_id = 10000002  # 伏尔戈
    price_data = get_price_history(type_id, region_id)
