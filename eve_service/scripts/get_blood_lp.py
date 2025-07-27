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


def get_mission_status_summary(user_id=None):
    """
    从数据库中获取任务状态统计信息
    
    参数:
    - user_id: 用户ID，如果提供则只统计该用户的数据
    
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
            if user_id is not None:
                # 只统计特定用户的数据
                cursor.execute('''
                    SELECT 
                        COUNT(*) as count, 
                        SUM(bounty) as total_bounty 
                    FROM blood_cooperative_data 
                    WHERE status = ? AND user_id = ?
                ''', (status, user_id))
            else:
                # 统计所有用户的数据（保持向后兼容）
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


def get_eve_character_data(character_id, access_token):
    """
    使用EVE SSO的角色ID和访问令牌获取角色数据
    
    参数:
    - character_id: EVE角色ID
    - access_token: EVE SSO访问令牌
    
    返回:
    - dict: 包含角色忠诚点和钱包日志数据的字典
    """
    try:
        headers = {
            'Authorization': f'{access_token}',
            'User-Agent': 'EVEservice/1.0',
            'Content-Type': 'application/json'
        }
        
        result = {}
        
        # 获取角色忠诚点数
        try:
            loyalty_url = f'https://esi.evetech.net/latest/characters/{character_id}/loyalty/points/'
            loyalty_response = requests.get(loyalty_url, headers=headers, timeout=10)
            if loyalty_response.status_code == 200:
                result['loyalty_points'] = loyalty_response.json()
                print(f"✅ 成功获取忠诚点数据: {len(result['loyalty_points'])} 个公司")
            else:
                print(f"❌ 获取忠诚点信息失败: {loyalty_response.status_code} - {loyalty_response.text}")
        except Exception as e:
            print(f"❌ 获取忠诚点信息异常: {str(e)}")
        
        # 获取角色钱包日志
        try:
            wallet_journal_url = f'https://esi.evetech.net/latest/characters/{character_id}/wallet/journal/'
            wallet_journal_response = requests.get(wallet_journal_url, headers=headers, timeout=10)
            if wallet_journal_response.status_code == 200:
                result['wallet_journal'] = wallet_journal_response.json()
                print(f"✅ 成功获取钱包日志数据: {len(result['wallet_journal'])} 条记录")
            else:
                print(f"❌ 获取钱包日志失败: {wallet_journal_response.status_code} - {wallet_journal_response.text}")
        except Exception as e:
            print(f"❌ 获取钱包日志异常: {str(e)}")
        
        return result
        
    except Exception as e:
        print(f"❌ 获取EVE角色数据异常: {str(e)}")
        return {}

def display_eve_character_summary(character_data):
    """
    显示EVE角色数据摘要（仅显示忠诚点和钱包日志）
    
    参数:
    - character_data: get_eve_character_data函数返回的数据
    """
    print("\n=== EVE角色数据摘要 ===")
    
    # 显示忠诚点数
    if 'loyalty_points' in character_data:
        loyalty_points = character_data['loyalty_points']
        if loyalty_points:
            print("\n📊 忠诚点数据:")
            for lp in loyalty_points:
                corp_id = lp.get('corporation_id', 'N/A')
                points = lp.get('loyalty_points', 0)
                print(f"  公司ID {corp_id}: {points:,} LP")
        else:
            print("📊 忠诚点数据: 无")
    
    # 显示钱包日志摘要
    if 'wallet_journal' in character_data:
        wallet_journal = character_data['wallet_journal']
        if wallet_journal:
            print(f"\n💰 钱包日志: 共 {len(wallet_journal)} 条记录")
            print("最近5条记录:")
            for i, entry in enumerate(wallet_journal[:5]):
                amount = entry.get('amount', 0)
                ref_type = entry.get('ref_type', 'unknown')
                date = entry.get('date', 'N/A')
                print(f"  {i+1}. {date} | {ref_type} | {amount:,} ISK")
        else:
            print("💰 钱包日志: 无记录")
    
    print("=" * 40)

# 在现有函数后添加以下数据库存储函数

def save_eve_character_data_to_db(user_id, character_id, character_name, eve_data):
    """
    将EVE角色数据保存到数据库
    
    参数:
    - user_id: 用户ID
    - character_id: EVE角色ID
    - character_name: EVE角色名称
    - eve_data: EVE角色数据（包含忠诚点和钱包日志）
    
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
        
        # 创建EVE忠诚点数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS eve_loyalty_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                character_id TEXT NOT NULL,
                character_name TEXT NOT NULL,
                corporation_id INTEGER NOT NULL,
                loyalty_points INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # 创建EVE钱包日志数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS eve_wallet_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                character_id TEXT NOT NULL,
                character_name TEXT NOT NULL,
                journal_id INTEGER NOT NULL,
                date TEXT,
                ref_type TEXT,
                first_party_id INTEGER,
                second_party_id INTEGER,
                amount REAL,
                balance REAL,
                reason TEXT,
                description TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # 创建唯一索引，防止重复插入
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_character_corp_loyalty 
            ON eve_loyalty_points (user_id, character_id, corporation_id)
        ''')
        
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_character_journal 
            ON eve_wallet_journal (user_id, character_id, journal_id)
        ''')
        
        # 获取当前时间
        current_time = datetime.now().isoformat()
        
        # 保存忠诚点数据
        loyalty_count = 0
        if 'loyalty_points' in eve_data and eve_data['loyalty_points']:
            loyalty_data = []
            for lp in eve_data['loyalty_points']:
                corporation_id = lp.get('corporation_id')
                loyalty_points = lp.get('loyalty_points', 0)
                
                loyalty_data.append((
                    user_id,
                    character_id,
                    character_name,
                    corporation_id,
                    loyalty_points,
                    current_time
                ))
            
            # 批量插入忠诚点数据
            cursor.executemany('''
                INSERT OR REPLACE INTO eve_loyalty_points 
                (user_id, character_id, character_name, corporation_id, loyalty_points, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', loyalty_data)
            
            loyalty_count = len(loyalty_data)
        
        # 保存钱包日志数据
        journal_count = 0
        if 'wallet_journal' in eve_data and eve_data['wallet_journal']:
            journal_data = []
            for entry in eve_data['wallet_journal']:
                journal_id = entry.get('id')
                date = entry.get('date')
                ref_type = entry.get('ref_type')
                first_party_id = entry.get('first_party_id')
                second_party_id = entry.get('second_party_id')
                amount = entry.get('amount', 0)
                balance = entry.get('balance', 0)
                reason = entry.get('reason', '')
                description = entry.get('description', '')
                
                journal_data.append((
                    user_id,
                    character_id,
                    character_name,
                    journal_id,
                    date,
                    ref_type,
                    first_party_id,
                    second_party_id,
                    amount,
                    balance,
                    reason,
                    description,
                    current_time
                ))
            
            # 批量插入钱包日志数据
            cursor.executemany('''
                INSERT OR REPLACE INTO eve_wallet_journal 
                (user_id, character_id, character_name, journal_id, date, ref_type, 
                 first_party_id, second_party_id, amount, balance, reason, description, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', journal_data)
            
            journal_count = len(journal_data)
        
        # 提交事务
        conn.commit()
        
        return True, f"成功保存EVE数据: {loyalty_count}条忠诚点记录, {journal_count}条钱包日志记录"
        
    except Exception as e:
        # 发生异常时回滚事务
        if conn:
            conn.rollback()
        return False, f"保存EVE数据失败: {str(e)}"
        
    finally:
        # 确保关闭数据库连接
        if conn:
            conn.close()

def get_eve_character_summary_from_db(user_id, character_id=None):
    """
    从数据库中获取EVE角色数据摘要
    
    参数:
    - user_id: 用户ID
    - character_id: 角色ID，如果提供则只查询该角色的数据
    
    返回:
    - dict: 包含忠诚点和钱包统计信息的字典
    """
    try:
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 构建数据库文件的绝对路径
        db_path = os.path.join(current_dir, 'eve_data.db')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        result = {
            'loyalty_summary': {},
            'wallet_summary': {}
        }
        
        # 查询忠诚点摘要
        if character_id:
            cursor.execute('''
                SELECT corporation_id, loyalty_points, character_name
                FROM eve_loyalty_points 
                WHERE user_id = ? AND character_id = ?
                ORDER BY loyalty_points DESC
            ''', (user_id, character_id))
        else:
            cursor.execute('''
                SELECT corporation_id, SUM(loyalty_points) as total_lp, character_name
                FROM eve_loyalty_points 
                WHERE user_id = ?
                GROUP BY corporation_id
                ORDER BY total_lp DESC
            ''', (user_id,))
        
        loyalty_rows = cursor.fetchall()
        result['loyalty_summary'] = [
            {
                'corporation_id': row[0],
                'loyalty_points': row[1],
                'character_name': row[2] if len(row) > 2 else None
            }
            for row in loyalty_rows
        ]
        
        # 查询钱包日志摘要
        if character_id:
            cursor.execute('''
                SELECT COUNT(*) as count, SUM(amount) as total_amount, character_name
                FROM eve_wallet_journal 
                WHERE user_id = ? AND character_id = ?
            ''', (user_id, character_id))
        else:
            cursor.execute('''
                SELECT COUNT(*) as count, SUM(amount) as total_amount
                FROM eve_wallet_journal 
                WHERE user_id = ?
            ''', (user_id,))
        
        wallet_row = cursor.fetchone()
        if wallet_row:
            result['wallet_summary'] = {
                'total_entries': wallet_row[0] or 0,
                'total_amount': wallet_row[1] or 0,
                'character_name': wallet_row[2] if len(wallet_row) > 2 else None
            }
        
        return result
        
    except Exception as e:
        print(f"获取EVE角色数据摘要失败: {str(e)}")
        return {}
        
    finally:
        # 确保关闭数据库连接
        if conn:
            conn.close()

# 修改主函数以包含数据库存储
if __name__ == '__main__':
    # 现有的血袭合作社数据获取
    data = get_blood_cooperatives_task_data('chuanqiong','zhr1530043602')
    summarize_bounty_by_status(data)
    
    # EVE SSO数据获取和存储
    character_id = '2119670383'  # 替换为实际的角色ID
    access_token = 'eyJhbGciOiJSUzI1NiIsImtpZCI6IkpXVC1TaWduYXR1cmUtS2V5IiwidHlwIjoiSldUIn0.eyJzY3AiOlsicHVibGljRGF0YSIsImVzaS1jYWxlbmRhci5yZXNwb25kX2NhbGVuZGFyX2V2ZW50cy52MSIsImVzaS1jYWxlbmRhci5yZWFkX2NhbGVuZGFyX2V2ZW50cy52MSIsImVzaS1sb2NhdGlvbi5yZWFkX2xvY2F0aW9uLnYxIiwiZXNpLWxvY2F0aW9uLnJlYWRfc2hpcF90eXBlLnYxIiwiZXNpLW1haWwub3JnYW5pemVfbWFpbC52MSIsImVzaS1tYWlsLnJlYWRfbWFpbC52MSIsImVzaS1tYWlsLnNlbmRfbWFpbC52MSIsImVzaS1za2lsbHMucmVhZF9za2lsbHMudjEiLCJlc2ktc2tpbGxzLnJlYWRfc2tpbGxxdWV1ZS52MSIsImVzaS13YWxsZXQucmVhZF9jaGFyYWN0ZXJfd2FsbGV0LnYxIiwiZXNpLXdhbGxldC5yZWFkX2NvcnBvcmF0aW9uX3dhbGxldC52MSIsImVzaS1zZWFyY2guc2VhcmNoX3N0cnVjdHVyZXMudjEiLCJlc2ktY2xvbmVzLnJlYWRfY2xvbmVzLnYxIiwiZXNpLWNoYXJhY3RlcnMucmVhZF9jb250YWN0cy52MSIsImVzaS11bml2ZXJzZS5yZWFkX3N0cnVjdHVyZXMudjEiLCJlc2kta2lsbG1haWxzLnJlYWRfa2lsbG1haWxzLnYxIiwiZXNpLWNvcnBvcmF0aW9ucy5yZWFkX2NvcnBvcmF0aW9uX21lbWJlcnNoaXAudjEiLCJlc2ktYXNzZXRzLnJlYWRfYXNzZXRzLnYxIiwiZXNpLXBsYW5ldHMubWFuYWdlX3BsYW5ldHMudjEiLCJlc2ktZmxlZXRzLnJlYWRfZmxlZXQudjEiLCJlc2ktZmxlZXRzLndyaXRlX2ZsZWV0LnYxIiwiZXNpLXVpLm9wZW5fd2luZG93LnYxIiwiZXNpLXVpLndyaXRlX3dheXBvaW50LnYxIiwiZXNpLWNoYXJhY3RlcnMud3JpdGVfY29udGFjdHMudjEiLCJlc2ktZml0dGluZ3MucmVhZF9maXR0aW5ncy52MSIsImVzaS1maXR0aW5ncy53cml0ZV9maXR0aW5ncy52MSIsImVzaS1tYXJrZXRzLnN0cnVjdHVyZV9tYXJrZXRzLnYxIiwiZXNpLWNvcnBvcmF0aW9ucy5yZWFkX3N0cnVjdHVyZXMudjEiLCJlc2ktY2hhcmFjdGVycy5yZWFkX3N0cnVjdHVyZXMudjEiLCJlc2ktY2hhcmFjdGVycy5yZWFkX21lZGFscy52MSIsImVzaS1jaGFyYWN0ZXJzLnJlYWRfc3RhbmRpbmdzLnYxIiwiZXNpLWNoYXJhY3RlcnMucmVhZF9hZ2VudHNfcmVzZWFyY2gudjEiLCJlc2ktaW5kdXN0cnkucmVhZF9jaGFyYWN0ZXJfam9icy52MSIsImVzaS1tYXJrZXRzLnJlYWRfY2hhcmFjdGVyX29yZGVycy52MSIsImVzaS1jaGFyYWN0ZXJzLnJlYWRfYmx1ZXByaW50cy52MSIsImVzaS1jaGFyYWN0ZXJzLnJlYWRfY29ycG9yYXRpb25fcm9sZXMudjEiLCJlc2ktbG9jYXRpb24ucmVhZF9vbmxpbmUudjEiLCJlc2ktY29udHJhY3RzLnJlYWRfY2hhcmFjdGVyX2NvbnRyYWN0cy52MSIsImVzaS1jbG9uZXMucmVhZF9pbXBsYW50cy52MSIsImVzaS1jaGFyYWN0ZXJzLnJlYWRfZmF0aWd1ZS52MSIsImVzaS1raWxsbWFpbHMucmVhZF9jb3Jwb3JhdGlvbl9raWxsbWFpbHMudjEiLCJlc2ktY29ycG9yYXRpb25zLnRyYWNrX21lbWJlcnMudjEiLCJlc2ktd2FsbGV0LnJlYWRfY29ycG9yYXRpb25fd2FsbGV0cy52MSIsImVzaS1jaGFyYWN0ZXJzLnJlYWRfbm90aWZpY2F0aW9ucy52MSIsImVzaS1jb3Jwb3JhdGlvbnMucmVhZF9kaXZpc2lvbnMudjEiLCJlc2ktY29ycG9yYXRpb25zLnJlYWRfY29udGFjdHMudjEiLCJlc2ktYXNzZXRzLnJlYWRfY29ycG9yYXRpb25fYXNzZXRzLnYxIiwiZXNpLWNvcnBvcmF0aW9ucy5yZWFkX3RpdGxlcy52MSIsImVzaS1jb3Jwb3JhdGlvbnMucmVhZF9ibHVlcHJpbnRzLnYxIiwiZXNpLWNvbnRyYWN0cy5yZWFkX2NvcnBvcmF0aW9uX2NvbnRyYWN0cy52MSIsImVzaS1jb3Jwb3JhdGlvbnMucmVhZF9zdGFuZGluZ3MudjEiLCJlc2ktY29ycG9yYXRpb25zLnJlYWRfc3RhcmJhc2VzLnYxIiwiZXNpLWluZHVzdHJ5LnJlYWRfY29ycG9yYXRpb25fam9icy52MSIsImVzaS1tYXJrZXRzLnJlYWRfY29ycG9yYXRpb25fb3JkZXJzLnYxIiwiZXNpLWNvcnBvcmF0aW9ucy5yZWFkX2NvbnRhaW5lcl9sb2dzLnYxIiwiZXNpLWluZHVzdHJ5LnJlYWRfY2hhcmFjdGVyX21pbmluZy52MSIsImVzaS1pbmR1c3RyeS5yZWFkX2NvcnBvcmF0aW9uX21pbmluZy52MSIsImVzaS1wbGFuZXRzLnJlYWRfY3VzdG9tc19vZmZpY2VzLnYxIiwiZXNpLWNvcnBvcmF0aW9ucy5yZWFkX2ZhY2lsaXRpZXMudjEiLCJlc2ktY29ycG9yYXRpb25zLnJlYWRfbWVkYWxzLnYxIiwiZXNpLWNoYXJhY3RlcnMucmVhZF90aXRsZXMudjEiLCJlc2ktYWxsaWFuY2VzLnJlYWRfY29udGFjdHMudjEiLCJlc2ktY2hhcmFjdGVycy5yZWFkX2Z3X3N0YXRzLnYxIiwiZXNpLWNvcnBvcmF0aW9ucy5yZWFkX2Z3X3N0YXRzLnYxIl0sImp0aSI6IjkwNWU1NmUzLWVmMmYtNDFiOS1iNTJmLWJiYzQ0Mzk4MmIzOSIsImtpZCI6IkpXVC1TaWduYXR1cmUtS2V5Iiwic3ViIjoiQ0hBUkFDVEVSOkVWRToyMTE5NjcwMzgzIiwiYXpwIjoiZDJiZTEyNmU2YjMxNDg2ZGFhODIyOTE1NmNlY2JhMTUiLCJ0ZW5hbnQiOiJ0cmFucXVpbGl0eSIsInRpZXIiOiJsaXZlIiwicmVnaW9uIjoid29ybGQiLCJhdWQiOlsiZDJiZTEyNmU2YjMxNDg2ZGFhODIyOTE1NmNlY2JhMTUiLCJFVkUgT25saW5lIl0sIm5hbWUiOiJDaHVhblFpb25nIiwib3duZXIiOiJ0K0paVUZBYzQxNHdoTlhtYk4vVThKVjEybjg9IiwiZXhwIjoxNzUzNjM3MTAzLCJpYXQiOjE3NTM2MzU5MDMsImlzcyI6Imh0dHBzOi8vbG9naW4uZXZlb25saW5lLmNvbSJ9.KlIPHhDaFmbZQyCS9vu8qjbZgd6xrONbFV4ee4_hPeJ93xnGDu-aEBL_de2_ZusCN--gROpGN2_bXftFDmWCJIOPG2Df_Wb-IB3FSGb4F4mKwdR5UihXQc-v4hdsPOWp3Gy1qN6zS66Zty_MkwiFAm6Vh6LENA0OnSqCjmQ12DzjOODLPKuebvT_aXMhHktQyFw6Ivy7TTsovOIWC2MRzi2kVtKhA9bdqDXGiJWvk0PWuqWTef1PNbZyx2cR-_Dgpk0Yva6n5VdIQ0PWc0ErUiHv2fHgU4wtod7hqTSPIahF0kfM3RG71MxqdpE5S-1g5RV7cwtl2s8ouO_BV4XeWw'  # 替换为实际的访问令牌
    user_id = 1  # 替换为实际的用户ID
    character_name = 'ChuanQiong'  # 替换为实际的角色名称
    
    # 获取EVE数据
    eve_data = get_eve_character_data(character_id, access_token)
    
    # 显示数据
    display_eve_character_summary(eve_data)
    
    # 保存到数据库
    success, message = save_eve_character_data_to_db(user_id, character_id, character_name, eve_data)
    print(f"\n数据库存储结果: {message}")
    
    # 从数据库获取摘要
    db_summary = get_eve_character_summary_from_db(user_id, character_id)
    print(f"\n数据库中的数据摘要: {db_summary}")

def get_blood_raider_lp_from_db():
    """
    从数据库中获取血袭者LP点数（公司ID 1000134）
    
    返回:
    - int: 血袭者LP点数总和，如果没有数据则返回0
    """
    try:
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 构建数据库文件的绝对路径
        db_path = os.path.join(current_dir, 'eve_data.db')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询血袭者公司（ID 1000134）的LP点数总和
        cursor.execute('''
            SELECT SUM(loyalty_points) as total_lp
            FROM eve_loyalty_points 
            WHERE corporation_id = 1000134
        ''')
        
        row = cursor.fetchone()
        total_lp = row[0] if row and row[0] else 0
        
        return int(total_lp)
        
    except Exception as e:
        print(f"获取血袭者LP点数失败: {str(e)}")
        return 0
        
    finally:
        # 确保关闭数据库连接
        if conn:
            conn.close()

 