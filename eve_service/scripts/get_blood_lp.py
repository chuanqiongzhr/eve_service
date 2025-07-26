import requests
from bs4 import BeautifulSoup
import json
from collections import defaultdict
import sqlite3
import os
from datetime import datetime

def get_blood_lp_rate():
    url = "https://www.fuzzwork.co.uk/lpstore/buy/10000002/1000134"
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # 找到主表格
    table = soup.find("table")
    max_isk_lp = None

    for row in table.find_all("tr")[1:]:  # 跳过表头
        cols = row.find_all("td")
        if not cols or len(cols) < 10:
            continue
        isk_lp_str = cols[-1].get_text(strip=True).replace(',', '')
        try:
            isk_lp = float(isk_lp_str)
            if (max_isk_lp is None) or (isk_lp > max_isk_lp):
                max_isk_lp = isk_lp
        except ValueError:
            continue

    # 按百取整
    if max_isk_lp is not None:
        max_isk_lp = int(max_isk_lp // 100 * 100)
    return max_isk_lp

def get_blood_cooperatives_task_data(user_name,password):
    login_url = "https://bloodapi.cs-eve.com/api/tokens"
    headers = {
        'authority': 'bloodapi.cs-eve.com',
        'method': 'POST',
        'path': '/api/tokens',
        'scheme': 'https',
        'accept': 'application/json, text/plain, */*',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'zh-CN,zh;q=0.9',
        'authorization': 'Basic Y2h1YW5xaW9uZzp6aHIxNTMwMDQzNjAy',
        'content-type': 'application/json',
        'origin': 'https://blood.cs-eve.com',
        'referer': 'https://blood.cs-eve.com/',
        'sec-ch-ua': '"Not)A;Brand";v="24", "Chromium";v="116"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.97 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest'
    }
    data = {
        "username": f"{user_name}",
        "password": f"{password}",
    }


    response = requests.post(login_url, headers=headers, json=data)
    response_data = response.json()
    access_token = response_data["access_token"]
    refresh_token = response_data["refresh_token"]

    authorization = f'Bearer {access_token}'


    headers_with_token = {
        'authority': 'bloodapi.cs-eve.com',
        'method': 'GET',
        'path': '/api/missions/state/completed',
        'scheme': 'https',
        'accept': 'application/json, text/plain, */*',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'zh-CN,zh;q=0.9',
        'authorization': f'{authorization}',
        'content-type': 'application/json',
        'origin': 'https://blood.cs-eve.com',
        'referer': 'https://blood.cs-eve.com/',
        'sec-ch-ua': '"Not)A;Brand";v="24", "Chromium";v="116"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.97 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest'
    }
    # 获取用户信息
    profile_url = "https://bloodapi.cs-eve.com/api/missions/runned"
    profile_response = requests.get(profile_url, headers=headers_with_token)

    data = json.loads(profile_response.text)

    return data['data']

def summarize_bounty_by_status(data):
    bounty_sum = defaultdict(int)
    count = defaultdict(int)
    for mission in data:
        status = mission.get('status', 'unknown')
        bounty = mission.get('bounty', 0)
        bounty_sum[status] += bounty
        count[status] += 1
    for status in bounty_sum:
        print(f"状态：{status}，任务数：{count[status]}，总赏金：{bounty_sum[status]:,} ISK")
    


def save_blood_data_to_db(user_id, username, data):
    """
    将血袭合作社到达数据保存到数据库
    
    参数:
    - user_id: 用户ID
    - username: 用户名
    - data: 血袭合作社任务数据
    
    返回:
    - (bool, str): 成功状态和消息
    """
    try:
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 构建数据库文件的绝对路径
        db_path = os.path.join(current_dir, 'eve_data.db')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建血袭合作社数据表（如果不存在）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blood_cooperative_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                mission_id TEXT NOT NULL,
                mission_name TEXT,
                status TEXT,
                bounty INTEGER,
                created_at TEXT,
                arrived_at TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # 创建一个唯一索引，防止重复插入相同的任务
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_mission 
            ON blood_cooperative_data (user_id, mission_id)
        ''')
        
        # 获取当前时间
        current_time = datetime.now().isoformat()
        
        # 准备批量插入的数据
        insert_data = []
        for mission in data:
            mission_id = mission.get('id')
            mission_name = mission.get('name')
            status = mission.get('status')
            bounty = mission.get('bounty', 0)
            created_at = mission.get('created_at')
            arrived_at = mission.get('arrived_at')
            
            # 保存所有状态的任务数据，仅仅是arrived状态
            insert_data.append((
                user_id,
                username,
                mission_id,
                mission_name,
                status,
                bounty,
                created_at,
                arrived_at,
                current_time
            ))
        
        # 批量插入数据，使用REPLACE策略处理重复数据
        cursor.executemany('''
            INSERT OR REPLACE INTO blood_cooperative_data 
            (user_id, username, mission_id, mission_name, status, bounty, created_at, arrived_at, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', insert_data)
        
        # 提交事务
        conn.commit()
        
        # 获取插入的记录数
        inserted_count = len(insert_data)
        
        return True, f"成功保存{inserted_count}条到达任务数据"
        
    except Exception as e:
        # 发生异常时回滚事务
        if conn:
            conn.rollback()
        return False, f"保存数据失败: {str(e)}"
        
    finally:
        # 确保关闭数据库连接
        if conn:
            conn.close()


def get_mission_status_summary():
    """
    从数据库中获取任务状态统计信息
    
    返回:
    - dict: 包含各状态任务数量和总赏金的字典
    """
    try:
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 构建数据库文件的绝对路径
        db_path = os.path.join(current_dir, 'eve_data.db')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询特定状态的任务统计信息
        status_list = ['completed', 'paid', 'done']
        result = {}
        
        for status in status_list:
            cursor.execute('''
                SELECT 
                    COUNT(*) as count, 
                    SUM(bounty) as total_bounty 
                FROM blood_cooperative_data 
                WHERE status = ?
            ''', (status,))
            
            row = cursor.fetchone()
            if row:
                count, total_bounty = row
                result[status] = {
                    'count': count or 0,
                    'total_bounty': total_bounty or 0
                }
            else:
                result[status] = {
                    'count': 0,
                    'total_bounty': 0
                }
        
        return result
        
    except Exception as e:
        print(f"获取任务状态统计信息失败: {str(e)}")
        return {}
        
    finally:
        # 确保关闭数据库连接
        if conn:
            conn.close()


if __name__ == '__main__':
    data = get_blood_cooperatives_task_data('chuanqiong','zhr1530043602')
    # 检查'data'字段是否存在且为列表
    summarize_bounty_by_status(data)
 