import requests
from bs4 import BeautifulSoup
import json
from collections import defaultdict
import sqlite3
import os
from datetime import datetime
import time
import random
from functools import wraps

def retry_with_backoff(max_retries=3, base_delay=1, max_delay=60):
    """
    改进的重试装饰器 - 不对认证错误重试
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    if attempt == max_retries:
                        raise e
                    
                    # 🔧 修复：对于认证错误不重试
                    if hasattr(e, 'response') and e.response:
                        status_code = e.response.status_code
                        # 对于认证和权限错误，立即失败
                        if status_code in [400, 401, 403, 404]:
                            print(f"❌ 认证/权限错误 {status_code}，不重试")
                            raise e
                        # 对于429（限流）使用更长的延迟
                        if status_code == 429:
                            retry_after = e.response.headers.get('Retry-After')
                            if retry_after:
                                delay = int(retry_after)
                            else:
                                delay = min(base_delay * (2 ** attempt), max_delay)
                        else:
                            delay = min(base_delay * (2 ** attempt), max_delay)
                    else:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                    
                    # 添加随机抖动
                    jitter = random.uniform(0.1, 0.3) * delay
                    total_delay = delay + jitter
                    
                    print(f"⚠️ 请求失败，{total_delay:.1f}秒后重试 (尝试 {attempt + 1}/{max_retries + 1})")
                    time.sleep(total_delay)
            
            return None
        return wrapper
    return decorator

@retry_with_backoff(max_retries=3)
def make_esi_request(url, headers, timeout=10):
    """
    带重试机制的ESI请求
    """
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response

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
    - list: 包含付款人、总金额和任务ID列表的列表
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
                COUNT(*) as mission_count,
                GROUP_CONCAT(mission_id) as mission_ids
            FROM blood_cooperative_data
            WHERE status = 'paid'
            GROUP BY COALESCE(publisher, '未知支付者')
            ORDER BY total_amount DESC
        ''')

        result = []
        for row in cursor.fetchall():
            # 将mission_ids字符串转换为列表
            mission_ids = row[3].split(',') if row[3] else []
            
            result.append({
                'payer': row[0],
                'total_amount': row[1],
                'mission_count': row[2],
                'mission_ids': mission_ids  # 新增的任务ID列表
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
            'Authorization': f'Bearer {access_token}',
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
            elif loyalty_response.status_code == 401:
                print(f"❌ Token已过期，需要刷新: {loyalty_response.status_code}")
                return {'error': 'token_expired', 'message': 'EVE SSO token已过期'}
            else:
                print(f"❌ 获取忠诚点信息失败: {loyalty_response.status_code} - {loyalty_response.text}")
        except Exception as e:
            print(f"❌ 获取忠诚点信息异常: {str(e)}")
        
        # 获取角色钱包日志
        try:
            wallet_journal = []
            page = 1
            
            while True:
                wallet_journal_url = f'https://esi.evetech.net/latest/characters/{character_id}/wallet/journal/?datasource=tranquility&page={page}'
                wallet_journal_response = requests.get(wallet_journal_url, headers=headers, timeout=10)
                
                if wallet_journal_response.status_code == 200:
                    page_data = wallet_journal_response.json()
                    if not page_data:
                        break
                    wallet_journal.extend(page_data)
                    
                    x_pages = wallet_journal_response.headers.get('X-Pages')
                    if x_pages and page >= int(x_pages):
                        break
                    page += 1
                elif wallet_journal_response.status_code == 401:
                    print(f"❌ Token已过期，需要刷新: {wallet_journal_response.status_code}")
                    return {'error': 'token_expired', 'message': 'EVE SSO token已过期'}
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
        return {'error': 'exception', 'message': str(e)}

def is_cache_expired(character_id, data_type):
    """
    检查缓存是否已过期
    """
    cache_info = get_cache_info(character_id, data_type)  # 🔧 修复：传递data_type参数
    if not cache_info or not cache_info.get('expires'):
        return True
    
    try:
        # 解析ESI返回的Expires头（RFC 2822格式）
        from email.utils import parsedate_to_datetime
        expires_time = parsedate_to_datetime(cache_info['expires'])
        return datetime.now(expires_time.tzinfo) >= expires_time
    except:
        return True  # 解析失败时认为已过期

def get_cache_info(character_id, data_type='loyalty_points'):
    """
    获取缓存信息
    
    参数:
    - character_id: EVE角色ID
    - data_type: 数据类型，默认为'loyalty_points'
    
    返回:
    - dict: 缓存信息
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'eve_data.db')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建缓存信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS eve_cache_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id TEXT NOT NULL,
                data_type TEXT NOT NULL,
                etag TEXT,
                last_modified TEXT,
                expires TEXT,
                cache_control TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(character_id, data_type)
            )
        ''')
        
        cursor.execute('''
            SELECT etag, last_modified, expires, cache_control
            FROM eve_cache_info
            WHERE character_id = ? AND data_type = ?
        ''', (character_id, data_type))
        
        row = cursor.fetchone()
        if row:
            return {
                'etag': row[0],
                'last_modified': row[1],
                'expires': row[2],
                'cache_control': row[3]
            }
        return None
        
    except Exception as e:
        print(f"获取缓存信息失败: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()

def save_cache_info(character_id, data_type, cache_info):
    """
    保存缓存信息
    
    参数:
    - character_id: EVE角色ID
    - data_type: 数据类型
    - cache_info: 缓存信息
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'eve_data.db')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO eve_cache_info
            (character_id, data_type, etag, last_modified, expires, cache_control)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            character_id,
            data_type,
            cache_info.get('etag'),
            cache_info.get('last_modified'),
            cache_info.get('expires'),
            cache_info.get('cache_control')
        ))
        
        conn.commit()
        
    except Exception as e:
        print(f"保存缓存信息失败: {str(e)}")
    finally:
        if conn:
            conn.close()

def get_cached_data(character_id, data_type):
    """
    获取缓存的数据
    
    参数:
    - character_id: EVE角色ID
    - data_type: 数据类型
    
    返回:
    - list: 缓存的数据
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'eve_data.db')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if data_type == 'loyalty_points':
            cursor.execute('''
                SELECT corporation_id, loyalty_points
                FROM eve_loyalty_points
                WHERE character_id = ?
                ORDER BY timestamp DESC
                LIMIT 1000
            ''', (character_id,))
            
            rows = cursor.fetchall()
            return [{'corporation_id': row[0], 'loyalty_points': row[1]} for row in rows]
        
        return []
        
    except Exception as e:
        print(f"获取缓存数据失败: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

def get_cached_wallet_data(character_id):
    """
    获取缓存的钱包数据
    
    参数:
    - character_id: EVE角色ID
    
    返回:
    - list: 缓存的钱包数据
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'eve_data.db')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT journal_id, date, ref_type, first_party_id, second_party_id, 
                   amount, balance, reason, description
            FROM eve_wallet_journal
            WHERE character_id = ?
            ORDER BY journal_id DESC
            LIMIT 1000
        ''', (character_id,))
        
        rows = cursor.fetchall()
        return [{
            'id': row[0],
            'date': row[1],
            'ref_type': row[2],
            'first_party_id': row[3],
            'second_party_id': row[4],
            'amount': row[5],
            'balance': row[6],
            'reason': row[7],
            'description': row[8]
        } for row in rows]
        
    except Exception as e:
        print(f"获取缓存钱包数据失败: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

def save_cached_data(character_id, data_type, data):
    """
    保存缓存数据
    
    参数:
    - character_id: EVE角色ID
    - data_type: 数据类型
    - data: 要缓存的数据
    """
    # 这个函数可以根据需要实现，目前数据已经通过其他函数保存到数据库
    pass

def get_last_journal_id(character_id):
    """
    获取最后一次更新的journal_id
    
    参数:
    - character_id: EVE角色ID
    
    返回:
    - int: 最后的journal_id
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'eve_data.db')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT MAX(journal_id)
            FROM eve_wallet_journal
            WHERE character_id = ? AND journal_id IS NOT NULL
        ''', (character_id,))
        
        row = cursor.fetchone()
        return row[0] if row and row[0] else 0
        
    except Exception as e:
        print(f"获取最后journal_id失败: {str(e)}")
        return 0
    finally:
        if conn:
            conn.close()

def get_eve_character_data_with_cache(character_id, access_token, force_refresh=False):
    """
    带缓存机制的EVE角色数据获取
    
    参数:
    - character_id: EVE角色ID
    - access_token: EVE SSO访问令牌
    - force_refresh: 是否强制刷新缓存
    
    返回:
    - dict: 包含角色忠诚点和钱包日志数据的字典
    """
    try:
        headers = {
            'Authorization': f'Bearer {access_token}',
            'User-Agent': 'EVEservice/1.0',
            'Content-Type': 'application/json'
        }
        
        # 添加缓存头处理
        if not force_refresh:
            # 检查本地缓存的ETag和Last-Modified
            cache_info = get_cache_info(character_id)
            if cache_info:
                if cache_info.get('etag'):
                    headers['If-None-Match'] = cache_info['etag']
                if cache_info.get('last_modified'):
                    headers['If-Modified-Since'] = cache_info['last_modified']
        
        result = {}
        
        # 获取角色忠诚点数
        loyalty_url = f'https://esi.evetech.net/latest/characters/{character_id}/loyalty/points/'
        loyalty_response = make_esi_request(loyalty_url, headers, timeout=10)
        
        # 处理304 Not Modified响应
        if loyalty_response.status_code == 304:
            print(f"✅ 忠诚点数据未变更，使用缓存")
            result['loyalty_points'] = get_cached_data(character_id, 'loyalty_points')
        elif loyalty_response.status_code == 200:
            result['loyalty_points'] = loyalty_response.json()
            # 保存缓存信息
            save_cache_info(character_id, 'loyalty_points', {
                'etag': loyalty_response.headers.get('ETag'),
                'last_modified': loyalty_response.headers.get('Last-Modified'),
                'expires': loyalty_response.headers.get('Expires'),
                'cache_control': loyalty_response.headers.get('Cache-Control')
            })
            save_cached_data(character_id, 'loyalty_points', result['loyalty_points'])
            print(f"✅ 成功获取忠诚点数据: {len(result['loyalty_points'])} 个公司")
        
        # 获取钱包日志 - 增量更新策略
        wallet_journal = get_wallet_journal_incremental(character_id, headers, force_refresh)
        result['wallet_journal'] = wallet_journal
        
        return result
        
    except Exception as e:
        print(f"❌ 获取EVE角色数据异常: {str(e)}")
        return {}

def get_wallet_journal_incremental(character_id, headers, force_refresh=False):
    """
    增量获取钱包日志数据
    """
    try:
        wallet_journal = []
        
        # 🔧 修复：强制刷新时跳过缓存检查
        if force_refresh:
            print("🔄 强制刷新模式，跳过缓存检查")
        elif not is_cache_expired(character_id, 'wallet_journal'):
            print("✅ 缓存未过期，跳过更新")
            return get_cached_wallet_data(character_id)
        
        # 获取最后一次更新的journal_id（仅在非强制刷新时使用）
        last_journal_id = None
        if not force_refresh:
            last_journal_id = get_last_journal_id(character_id)
            if last_journal_id:
                print(f"🔄 增量更新：从journal_id {last_journal_id} 开始")
        
        page = 1
        new_entries_count = 0
        
        while True:
            wallet_journal_url = f'https://esi.evetech.net/latest/characters/{character_id}/wallet/journal/?datasource=tranquility&page={page}'
            
            try:
                wallet_journal_response = make_esi_request(wallet_journal_url, headers, timeout=10)
                
                if wallet_journal_response.status_code == 304:
                    print(f"✅ 钱包日志页面{page}未变更，使用缓存")
                    break
                elif wallet_journal_response.status_code == 200:
                    page_data = wallet_journal_response.json()
                    if not page_data:
                        break
                    
                    # 增量更新逻辑（仅在非强制刷新且有last_journal_id时使用）
                    if not force_refresh and last_journal_id:
                        # 过滤出新的记录
                        new_entries = [entry for entry in page_data 
                                     if entry.get('id', 0) > last_journal_id]
                        if not new_entries:
                            print(f"✅ 已获取所有新记录，停止分页")
                            break
                        wallet_journal.extend(new_entries)
                        new_entries_count += len(new_entries)
                    else:
                        wallet_journal.extend(page_data)
                        new_entries_count += len(page_data)
                    
                    # 保存缓存信息
                    save_cache_info(character_id, f'wallet_journal_page_{page}', {
                        'etag': wallet_journal_response.headers.get('ETag'),
                        'last_modified': wallet_journal_response.headers.get('Last-Modified'),
                        'expires': wallet_journal_response.headers.get('Expires'),
                        'cache_control': wallet_journal_response.headers.get('Cache-Control')
                    })
                    
                    # 检查是否还有更多页面
                    x_pages = wallet_journal_response.headers.get('X-Pages')
                    if x_pages and page >= int(x_pages):
                        break
                    page += 1
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 304:
                    print("✅ 数据未变更，使用缓存")
                    return get_cached_wallet_data(character_id)
                elif e.response.status_code == 400:
                    print(f"❌ ESI API请求参数错误 (页面 {page}): {e.response.status_code}")
                    print(f"❌ 错误详情: {e.response.text}")
                    # 400错误通常是请求参数问题，不应该重试
                    break
                elif e.response.status_code == 401:
                    print(f"❌ Token已过期，需要刷新: {e.response.status_code}")
                    raise Exception('token_expired')
                elif e.response.status_code == 403:
                    print(f"❌ 权限不足，无法访问钱包数据: {e.response.status_code}")
                    break
                elif e.response.status_code == 404:
                    print(f"❌ 角色不存在或钱包数据不可用: {e.response.status_code}")
                    break
                elif e.response.status_code == 429:  # Rate Limited
                    retry_after = e.response.headers.get('Retry-After', '60')
                    print(f"⚠️ API限流，{retry_after}秒后重试")
                    raise Exception(f'rate_limited:{retry_after}')
                elif e.response.status_code >= 500:
                    print(f"❌ ESI服务器错误 (页面 {page}): {e.response.status_code}，跳过此页")
                    break
                else:
                    print(f"❌ 钱包数据获取失败 (页面 {page}): {e.response.status_code}")
                    break
            except Exception as e:
                print(f"❌ 请求钱包数据时发生异常 (页面 {page}): {str(e)}")
                break
        
        print(f"✅ 成功获取钱包日志数据: {new_entries_count} 条新记录")
        return wallet_journal
        
    except Exception as e:
        print(f"❌ 获取钱包日志异常: {str(e)}")
        if 'token_expired' in str(e):
            raise e  # 重新抛出token过期异常，让上层处理
        return []

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
            DROP INDEX IF EXISTS idx_user_character_journal
        ''')
        
        # 创建新的复合唯一索引，处理journal_id为NULL的情况
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_character_journal_unique 
            ON eve_wallet_journal (user_id, character_id, 
                                  COALESCE(journal_id, date || '_' || ref_type || '_' || amount))
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
            SELECT DISTINCT character_name, amount, ref_type, date, description, 
                           first_party_id, second_party_id, timestamp
            FROM eve_wallet_journal 
            WHERE ref_type IN ('player_donation', 'corporation_account_withdrawal')
            GROUP BY character_name, amount, ref_type, date, description
            ORDER BY MAX(COALESCE(date, timestamp)) DESC
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
                    # 对于军团账户支取，从description中提取ATM名称
                    import re
                    
                    # 方案1: 匹配到" transferred"关键词前的所有内容
                    # 这样可以处理包含空格、符号、数字等的ATM名称
                    match = re.search(r'^(.+?)\s+transferred\s+cash\s+from', desc)
                    if match:
                        atm_name = match.group(1).strip()
                        return atm_name
                    
                    # 方案2: 更宽松的匹配，只要求" transferred"关键词
                    match = re.search(r'^(.+?)\s+transferred', desc)
                    if match:
                        atm_name = match.group(1).strip()
                        return atm_name
                    
                    # 方案3: 如果description格式完全不同，尝试其他模式
                    # 例如可能的其他格式
                    match = re.search(r'^(.+?)\s+(withdrew|moved|sent)', desc, re.IGNORECASE)
                    if match:
                        atm_name = match.group(1).strip()
                        return atm_name
                    
                    # 如果所有模式都不匹配，回退到character_name
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
        response = make_esi_request(url, headers_with_token, timeout=30)
        
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
                try:
                    publisher_info = get_publisher_info(publisher_id, user_name, password)
                except Exception as e:
                    print(f"获取publisher_id={publisher_id}信息时出错: {e}")
                    continue
                
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

def create_optimized_database_schema():
    """
    创建优化的数据库结构
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'eve_data.db')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 🆕 添加缓存表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS esi_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                etag TEXT,
                last_modified TEXT,
                expires TEXT,
                cache_control TEXT,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(character_id, endpoint)
            )
        ''')
        
        # 🆕 优化钱包日志表结构
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS eve_wallet_journal_optimized (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                character_id TEXT NOT NULL,
                character_name TEXT NOT NULL,
                journal_id BIGINT UNIQUE,  -- ESI journal ID
                date TEXT NOT NULL,
                ref_type TEXT NOT NULL,
                first_party_id BIGINT,
                second_party_id BIGINT,
                amount REAL NOT NULL,
                balance REAL,
                reason TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # 🆕 创建优化索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_wallet_journal_user_char ON eve_wallet_journal_optimized (user_id, character_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_wallet_journal_date ON eve_wallet_journal_optimized (date DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_wallet_journal_amount ON eve_wallet_journal_optimized (amount)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_wallet_journal_ref_type ON eve_wallet_journal_optimized (ref_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_esi_cache_lookup ON esi_cache (character_id, endpoint)')
        
        conn.commit()
        return True, "数据库结构优化完成"
        
    except Exception as e:
        if conn:
            conn.rollback()
        return False, f"数据库结构优化失败: {str(e)}"
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    user_name = 'chuanqiong'
    password = 'zhr1530043602'
    success, message = collect_publisher_data(user_name, password)
    print(message)
