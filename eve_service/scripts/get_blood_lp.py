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

def get_blood_cooperatives_task_data(user_name, password):
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

    return data

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
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'eve_data.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

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
                publisher TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # 检查是否存在publisher列，如果不存在则添加
        cursor.execute("PRAGMA table_info(blood_cooperative_data)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'publisher' not in columns:
            cursor.execute('ALTER TABLE blood_cooperative_data ADD COLUMN publisher TEXT')
            conn.commit()

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_mission 
            ON blood_cooperative_data (user_id, mission_id)
        ''')

        current_time = datetime.now().isoformat()
        insert_data = []
        for mission in data:
            mission_id = mission.get('id')
            mission_name = mission.get('title')
            status = mission.get('status')
            bounty = mission.get('bounty', 0)
            created_at = mission.get('created')
            arrived_at = mission.get('published')
            publisher = mission.get('publisher', {})
            publisher_name = publisher.get('owner', {}).get('default_account', {}).get('name')

            insert_data.append((
                user_id,
                username,
                mission_id,
                mission_name,
                status,
                bounty,
                created_at,
                arrived_at,
                publisher_name,
                current_time
            ))

        cursor.executemany('''
            INSERT OR REPLACE INTO blood_cooperative_data 
            (user_id, username, mission_id, mission_name, status, bounty, created_at, arrived_at, publisher, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', insert_data)

        conn.commit()
        inserted_count = len(insert_data)
        return True, f"成功保存{inserted_count}条到达任务数据"

    except Exception as e:
        if conn:
            conn.rollback()
        return False, f"保存数据失败: {str(e)}"

    finally:
        if conn:
            conn.close()


def get_paid_missions_summary():
    """
    获取已支付任务的付款人和付款金额汇总
    
    返回:
    - list: 包含付款人和总金额的列表
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'eve_data.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 查询已支付任务，按支付者分组汇总
        # 使用正确的publisher字段
        cursor.execute('''
            SELECT 
                COALESCE(publisher, '未知支付者') as payer,
                SUM(bounty) as total_amount,
                COUNT(*) as mission_count
            FROM blood_cooperative_data
            WHERE status = 'paid'
            GROUP BY COALESCE(publisher, '未知支付者')
            ORDER BY total_amount DESC
        ''')

        result = []
        for row in cursor.fetchall():
            result.append({
                'payer': row[0],
                'total_amount': row[1],
                'mission_count': row[2]
            })

        return result

    except Exception as e:
        print(f"获取已支付任务汇总失败: {str(e)}")
        return []
    finally:
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
        
        # 获取角色钱包日志 - 支持分页
        try:
            wallet_journal = []
            page = 1
            
            while True:
                wallet_journal_url = f'https://esi.evetech.net/latest/characters/{character_id}/wallet/journal/?datasource=tranquility&page={page}'
                wallet_journal_response = requests.get(wallet_journal_url, headers=headers, timeout=10)
                
                if wallet_journal_response.status_code == 200:
                    page_data = wallet_journal_response.json()
                    if not page_data:  # 空页面，结束
                        break
                    wallet_journal.extend(page_data)
                    
                    # 检查是否还有更多页面
                    x_pages = wallet_journal_response.headers.get('X-Pages')
                    if x_pages and page >= int(x_pages):
                        break
                    page += 1
                else:
                    print(f"❌ 钱包数据获取失败 (页面 {page}): {wallet_journal_response.status_code}")
                    break
            
            result['wallet_journal'] = wallet_journal
            print(f"✅ 成功获取钱包日志数据: {len(wallet_journal)} 条记录")
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

def get_paid_missions_summary():
    """
    获取已支付任务的付款人和付款金额汇总
    
    返回:
    - list: 包含付款人和总金额的列表
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'eve_data.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT 
                COALESCE(publisher, '未知支付者') as payer,
                SUM(bounty) as total_amount,
                COUNT(*) as mission_count
            FROM blood_cooperative_data
            WHERE status = 'paid'
            GROUP BY COALESCE(publisher, '未知支付者')
            ORDER BY total_amount DESC
        ''')

        result = []
        for row in cursor.fetchall():
            result.append({
                'payer': row[0],
                'total_amount': row[1],
                'mission_count': row[2]
            })

        return result

    except Exception as e:
        print(f"获取已支付任务汇总失败: {str(e)}")
        return []
    finally:
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
        
        # 获取角色钱包日志 - 支持分页
        try:
            wallet_journal = []
            page = 1
            
            while True:
                wallet_journal_url = f'https://esi.evetech.net/latest/characters/{character_id}/wallet/journal/?datasource=tranquility&page={page}'
                wallet_journal_response = requests.get(wallet_journal_url, headers=headers, timeout=10)
                
                if wallet_journal_response.status_code == 200:
                    page_data = wallet_journal_response.json()
                    if not page_data:  # 空页面，结束
                        break
                    wallet_journal.extend(page_data)
                    
                    # 检查是否还有更多页面
                    x_pages = wallet_journal_response.headers.get('X-Pages')
                    if x_pages and page >= int(x_pages):
                        break
                    page += 1
                else:
                    print(f"❌ 钱包数据获取失败 (页面 {page}): {wallet_journal_response.status_code}")
                    break
            
            result['wallet_journal'] = wallet_journal
            print(f"✅ 成功获取钱包日志数据: {len(wallet_journal)} 条记录")
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

def get_paid_missions_summary():
    """
    获取已支付任务的付款人和付款金额汇总
    
    返回:
    - list: 包含付款人和总金额的列表
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'eve_data.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 查询已支付任务，按支付者分组汇总
        # 使用正确的publisher字段
        cursor.execute('''
            SELECT 
                COALESCE(publisher, '未知支付者') as payer,
                SUM(bounty) as total_amount,
                COUNT(*) as mission_count
            FROM blood_cooperative_data
            WHERE status = 'paid'
            GROUP BY COALESCE(publisher, '未知支付者')
            ORDER BY total_amount DESC
        ''')

        result = []
        for row in cursor.fetchall():
            result.append({
                'payer': row[0],
                'total_amount': row[1],
                'mission_count': row[2]
            })

        return result

    except Exception as e:
        print(f"获取已支付任务汇总失败: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

def get_recent_wallet_donations(limit=10):
    """
    获取最近的钱包捐赠记录（个人捐赠和军团账户支取）
    
    参数:
    - limit: 返回记录数量限制
    
    返回:
    - list: 包含最近捐赠记录的列表
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'eve_data.db')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询个人捐赠和军团账户支取记录，移除时间过滤
        cursor.execute('''
            SELECT character_name, amount, ref_type, date, description, first_party_id, second_party_id, timestamp
            FROM eve_wallet_journal 
            WHERE ref_type IN ('player_donation', 'corporation_account_withdrawal')
            ORDER BY COALESCE(date, timestamp) DESC
            LIMIT ?
        ''', (limit,))
        
        result = []
        for row in cursor.fetchall():
            character_name = row[0]
            amount = row[1]
            ref_type = row[2]
            date = row[3]
            description = row[4] or ''
            first_party_id = row[5]
            second_party_id = row[6]
            timestamp = row[7] if len(row) > 7 else None
            
            # 从description中解析捐赠者用户名
            def extract_donor_from_description(desc, ref_type):
                if not desc:
                    return character_name
                
                if ref_type == 'player_donation':
                    # 匹配模式: "2b robot deposited cash into ChuanQiong's account"
                    # 更新正则表达式以支持连字符、空格和其他特殊字符
                    import re
                    
                    # 尝试匹配 "用户名 deposited cash into" 模式
                    # 修改正则表达式以包含连字符、数字、空格等字符
                    match = re.search(r'^([\w\-\s]+?)\s+deposited\s+cash\s+into', desc)
                    if match:
                        return match.group(1).strip()
                    
                    # 尝试匹配 "用户名 transferred" 模式
                    match = re.search(r'^([\w\-\s]+?)\s+transferred', desc)
                    if match:
                        return match.group(1).strip()
                    
                    # 如果无法解析，根据金额正负判断
                    if amount < 0:
                        return character_name  # 当前角色是捐赠者
                    else:
                        return "外部捐赠者"  # 无法确定具体捐赠者
                
                elif ref_type == 'corporation_account_withdrawal':
                    # 对于军团账户支取，支取者通常是当前角色
                    return character_name
                
                return character_name
            
            # 解析捐赠者
            donor = extract_donor_from_description(description, ref_type)
            display_amount = abs(amount)
            
            # 设置交易类型
            if ref_type == 'player_donation':
                transaction_type = '个人捐赠'
            elif ref_type == 'corporation_account_withdrawal':
                transaction_type = '军团账户支取'
            else:
                transaction_type = '未知类型'
            
            # 使用更准确的时间信息
            display_date = date if date else timestamp
            
            result.append({
                'donor': donor,
                'amount': display_amount,
                'type': transaction_type,
                'date': display_date,
                'description': description,
                'data_freshness': '历史数据'  # 移除时间限制后，统一标记为历史数据
            })
        
        return result
        
    except Exception as e:
        print(f"获取钱包捐赠记录失败: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

# 在文件中添加以下函数

def get_publisher_info(publisher_id, user_name, password):
    """
    获取发布者信息
    
    参数:
    - publisher_id: 发布者ID
    - user_name: 血袭合作社用户名
    - password: 血袭合作社密码
    
    返回:
    - dict: 发布者信息
    """
    try:
        # 先登录获取token
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
        
        # 使用获取的token请求publisher信息
        headers_with_token = {
            'authority': 'bloodapi.cs-eve.com',
            'method': 'GET',
            'scheme': 'https',
            'accept': 'application/json, text/plain, */*',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'zh-CN,zh;q=0.9',
            'authorization': f'Bearer {access_token}',
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
        
        url = f"https://bloodapi.cs-eve.com/api/users/{publisher_id}"
        response = requests.get(url, headers=headers_with_token, timeout=30)
        
        # 检查响应状态
        if response.status_code == 404:
            return None  # 表示没有找到该publisher_id
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"获取发布者信息失败: {e}")
        return None

def collect_publisher_data(user_name, password, start_id=1, end_id=1000):
    """
    收集发布者数据并保存到数据库
    
    参数:
    - user_name: 血袭合作社用户名
    - password: 血袭合作社密码
    - start_id: 起始publisher_id
    - end_id: 结束publisher_id
    
    返回:
    - (bool, str): 成功状态和消息
    """
    try:
        # 创建数据库连接
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'eve_data.db')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建publisher表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS publisher_info (
                id INTEGER PRIMARY KEY,
                publisher_id INTEGER UNIQUE NOT NULL,
                name TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 获取当前时间
        current_time = datetime.now().isoformat()
        
        # 遍历publisher_id从start_id到end_id
        success_count = 0
        
        for publisher_id in range(start_id, end_id + 1):
            try:
                publisher_info = get_publisher_info(publisher_id, user_name, password)
                
                if publisher_info and 'default_account' in publisher_info:
                    name = publisher_info['default_account'].get('name', '未知')
                    
                    # 插入或更新数据
                    cursor.execute('''
                        INSERT OR REPLACE INTO publisher_info 
                        (publisher_id, name, timestamp)
                        VALUES (?, ?, ?)
                    ''', (publisher_id, name, current_time))
                    
                    conn.commit()
                    success_count += 1
                    print(f"成功保存publisher_id={publisher_id}, name={name}")
                else:
                    print(f"publisher_id={publisher_id}没有有效数据")
            except Exception as e:
                print(f"处理publisher_id={publisher_id}时出错: {e}")
                continue
        
        return True, f"成功保存{success_count}条发布者数据，处理范围: {start_id}-{end_id}"
    
    except Exception as e:
        if conn:
            conn.rollback()
        return False, f"保存发布者数据失败: {str(e)}"
    
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    user_name = 'chuanqiong'
    password = 'zhr1530043602'
    success, message = collect_publisher_data(user_name, password)
    print(message)
