import sqlite3
import hashlib
import secrets
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from eve_service.scripts.get_blood_lp import get_blood_cooperatives_task_data

class UserManager:
    def __init__(self, db_path=None):
        if db_path is None:
            # 获取当前文件所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 构建数据库文件的绝对路径
            self.db_path = os.path.join(current_dir, 'eve_data.db')
        else:
            self.db_path = db_path
        self.init_user_table()
    
    def init_user_table(self):
        """初始化用户表"""
        # 确保数据库目录存在
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                email TEXT,
                access_level TEXT DEFAULT 'standard',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                login_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP
            )
        ''')
        
        # 创建会话表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def hash_password(self, password):
        """生成密码哈希"""
        salt = secrets.token_hex(32)
        password_hash = generate_password_hash(password + salt)
        return password_hash, salt
    
    def verify_password(self, password, password_hash, salt):
        """验证密码"""
        return check_password_hash(password_hash, password + salt)
    
    def create_user(self, username, password, email=None):
        """创建新用户"""
        try:
            # 首先验证用户是否有效（调用外部API）
            data = get_blood_cooperatives_task_data(username, password)
            if not data:
                return False, "外部验证失败"
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查用户名是否已存在
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            if cursor.fetchone():
                conn.close()
                return False, "用户名已存在"
            
            # 生成密码哈希
            password_hash, salt = self.hash_password(password)
            
            # 插入新用户
            cursor.execute('''
                INSERT INTO users (username, password_hash, salt, email)
                VALUES (?, ?, ?, ?)
            ''', (username, password_hash, salt, email))
            
            conn.commit()
            conn.close()
            return True, "注册成功"
            
        except Exception as e:
            return False, f"注册失败: {str(e)}"
    
    def authenticate_user(self, username, password):
        """验证用户登录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 获取用户信息
            cursor.execute('''
                SELECT id, username, password_hash, salt, access_level, 
                       is_active, login_attempts, locked_until
                FROM users WHERE username = ?
            ''', (username,))
            
            user_data = cursor.fetchone()
            if not user_data:
                return None, "用户不存在"
            
            user_id, username, password_hash, salt, access_level, is_active, login_attempts, locked_until = user_data
            
            # 检查账户是否被锁定
            if locked_until:
                locked_time = datetime.fromisoformat(locked_until)
                if datetime.now() < locked_time:
                    return None, "账户已被锁定，请稍后再试"
            
            # 检查账户是否激活
            if not is_active:
                return None, "账户已被禁用"
            
            # 验证密码
            if self.verify_password(password, password_hash, salt):
                # 重置登录尝试次数
                cursor.execute('''
                    UPDATE users 
                    SET login_attempts = 0, locked_until = NULL, last_login = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (user_id,))
                conn.commit()
                
                user_info = {
                    'id': user_id,
                    'username': username,
                    'access_level': access_level
                }
                return user_info, "登录成功"
            else:
                # 增加登录尝试次数
                new_attempts = login_attempts + 1
                if new_attempts >= 5:  # 5次失败后锁定30分钟
                    locked_until = datetime.now() + timedelta(minutes=30)
                    cursor.execute('''
                        UPDATE users 
                        SET login_attempts = ?, locked_until = ?
                        WHERE id = ?
                    ''', (new_attempts, locked_until.isoformat(), user_id))
                else:
                    cursor.execute('''
                        UPDATE users 
                        SET login_attempts = ?
                        WHERE id = ?
                    ''', (new_attempts, user_id))
                
                conn.commit()
                return None, "密码错误"
                
        except Exception as e:
            return None, f"登录失败: {str(e)}"
        finally:
            conn.close()
    
    def create_session(self, user_id, remember_me=False):
        """创建用户会话"""
        session_id = secrets.token_urlsafe(32)
        
        # 根据记住我选项设置不同的过期时间
        if remember_me:
            # 设置30天的过期时间
            expires_at = datetime.now() + timedelta(days=30)
        else:
            # 默认24小时过期
            expires_at = datetime.now() + timedelta(hours=24)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_sessions (session_id, user_id, expires_at)
            VALUES (?, ?, ?)
        ''', (session_id, user_id, expires_at.isoformat()))
        
        conn.commit()
        conn.close()
        
        return session_id
    
    def validate_session(self, session_id):
        """验证会话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.id, u.username, u.access_level, s.expires_at
            FROM user_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.session_id = ? AND s.is_active = 1
        ''', (session_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return None
        
        user_id, username, access_level, expires_at = result
        expires_time = datetime.fromisoformat(expires_at)
        
        if datetime.now() > expires_time:
            self.invalidate_session(session_id)
            return None
        
        return {
            'id': user_id,
            'username': username,
            'access_level': access_level
        }
    
    def invalidate_session(self, session_id):
        """使会话失效"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE user_sessions 
            SET is_active = 0 
            WHERE session_id = ?
        ''', (session_id,))
        
        conn.commit()
        conn.close()