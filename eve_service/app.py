from flask import Flask, render_template, jsonify, request, send_from_directory, session
from eve_service.scripts.get_price_history import name_to_id, get_price_history
from eve_service.scripts.get_icon import get_item_icon
from eve_service.scripts.get_buy_sell import get_buy_sell_data, get_max_buy_price_from_data, get_min_sell_price_from_data, get_middle_price_from_data
from eve_service.scripts.search_items import search_items
# 在文件顶部导入新函数
from eve_service.scripts.get_blood_lp import get_blood_lp_rate, get_blood_cooperatives_task_data, save_blood_data_to_db, get_mission_status_summary
from eve_service.scripts.models import UserManager  # 修改导入路径
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from datetime import datetime
import secrets
import os
import requests

app = Flask(__name__)

# 配置会话密钥（生产环境中应该从环境变量读取）
# 在文件顶部导入
from datetime import timedelta

# 配置会话 - 统一配置（保留这一份）
app.secret_key = os.environ.get('SECRET_KEY', 'b7c820226a1891011f53889d5e0d1295bbdd4b0d1faa12a1757cbd2644339ea4')
print(f"[DEBUG] 当前 Flask SECRET_KEY: {app.secret_key}")

# 统一的session配置
app.config['SESSION_COOKIE_NAME'] = 'eve_session'
app.config['SESSION_COOKIE_SECURE'] = False  # 临时设置为 False 以测试 HTTP 环境
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_COOKIE_DOMAIN'] = None
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# 初始化用户管理器
user_manager = UserManager()

# 禁用静态文件缓存
@app.after_request
def add_header(response):
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/price_history")
def price_history_page():
    return render_template("price_history.html")

@app.route("/xuexi_ranshao")
def xuexi_ranshao_page():
    max_isk_lp = get_blood_lp_rate()
    # 获取任务状态统计信息 - 不传user_id，显示所有用户数据（首次加载）
    mission_status = get_mission_status_summary()
    return render_template("xuexi_ranshao.html", max_isk_lp=max_isk_lp, mission_status=mission_status)

def process_item_data(item_id, item_name, region_id):
    """处理单个物品的数据获取"""
    item_price_history = get_price_history(region_id=region_id, type_id=item_id)
    if not item_price_history:
        return None
    station_id = 60003760    
    buy_data, sell_data = get_buy_sell_data(item_id, region_id)
    
    max_buy_price = get_max_buy_price_from_data(buy_data, station_id)
    min_sell_price = get_min_sell_price_from_data(sell_data, station_id)
    middle_price = get_middle_price_from_data(buy_data, sell_data, station_id)
    
    icon_url = get_item_icon(item_id)
    
    for entry in item_price_history:
        entry['item_name'] = item_name
        entry['icon_url'] = icon_url
        entry['max_buy_price'] = max_buy_price
        entry['min_sell_price'] = min_sell_price
        entry['middle_price'] = middle_price
    
    return {
        'price_history': item_price_history,
        'max_buy_price': max_buy_price,
        'min_sell_price': min_sell_price,
        'middle_price': middle_price
    }

@app.route("/api/price_history")
def price_history():
    name = request.args.get("name", "plex")
    
    # 首先尝试直接通过name_to_id匹配
    type_id, chinese_name = name_to_id(name)
    
    if not type_id:
        # 如果直接匹配失败，尝试使用search_items搜索
        search_results = search_items(name)
        if not search_results:
            return jsonify([]), 200  # 如果搜索也没有结果，返回空列表
            
        # 如果有搜索结果，并发处理所有匹配项
        
        region_id = 10000002
        station_id = 60003760  
        all_price_history = []
        total_max_buy = 0
        total_min_sell = 0
        total_middle = 0
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(process_item_data, item_id, item_name, region_id): (item_id, item_name)
                for item_id, item_name in search_results
            }
            
            for future in tqdm(as_completed(futures), total=len(search_results), desc="处理物品数据"):
                result = future.result()
                if result:
                    all_price_history.extend(result['price_history'])
                    if result['max_buy_price']:
                        total_max_buy += float(result['max_buy_price'])
                    if result['min_sell_price']:
                        total_min_sell += float(result['min_sell_price'])
                    if result['middle_price']:
                        total_middle += float(result['middle_price'])
        
        # 计算特殊价格
        special_prices = {
            "max_buy_price_set": round(total_max_buy, 2),
            "min_sell_price_set": round(total_min_sell, 2),
            "middle_price_set": round(total_middle, 2),
            "unit": "一套"
        }
        
        # 给所有数据添加特殊价格信息
        for entry in all_price_history:
            entry.update(special_prices)
            
        return jsonify(all_price_history)
    
    # 如果直接匹配成功，使用原有逻辑
    if type_id == 44992:
        region_id = 19000001
    else:
        region_id = 10000002
        station_id = 60003760  
    price_history = get_price_history(region_id=region_id, type_id=type_id)
    
    if not price_history:
        return jsonify([]), 200
    
    # 获取icon url
    icon_url = get_item_icon(type_id)
    
    buy_data, sell_data = get_buy_sell_data(type_id, region_id)
    # 获取买卖价格
    if type_id == 44992:
        max_buy_price = get_max_buy_price_from_data(buy_data)
        min_sell_price = get_min_sell_price_from_data(sell_data)
        middle_price = get_middle_price_from_data(buy_data, sell_data)
    else:
        max_buy_price = get_max_buy_price_from_data(buy_data, station_id)
        min_sell_price = get_min_sell_price_from_data(sell_data, station_id)
        middle_price = get_middle_price_from_data(buy_data, sell_data, station_id)

    # 给每条数据加上物品名称和icon url
    for entry in price_history:
        entry['item_name'] = chinese_name
        entry['icon_url'] = icon_url
        entry['max_buy_price'] = max_buy_price
        entry['min_sell_price'] = min_sell_price
        entry['middle_price'] = middle_price
        # 如果是伊甸币，单独添加 500 个一组的价格字段
        if chinese_name == "伊甸币":
            entry['max_buy_price_500'] = round(max_buy_price * 500, 2) if max_buy_price else None
            entry['min_sell_price_500'] = round(min_sell_price * 500, 2) if min_sell_price else None
            entry['middle_price_500'] = round(middle_price * 500, 2) if middle_price else None
            entry['unit_500'] = "500个"
    
    return jsonify(price_history)


@app.route('/xuexi_ranshao/login', methods=['POST'])
def xuexi_login():
    try:
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = request.form.get('rememberMe') == 'on'

        if not username or not password:
            return jsonify({
                'success': False,
                'message': '用户名和密码不能为空'
            }), 400

        # 用户认证
        user_info, message = user_manager.authenticate_user(username, password)
        
        if user_info:
            # 创建数据库会话
            session_id = user_manager.create_session(user_info['id'], remember_me)
            
            if not session_id:
                app.logger.error('❌ 数据库会话创建失败')
                return jsonify({
                    'success': False,
                    'message': '会话创建失败，请重试'
                }), 500
            
            # 强制清空现有Flask session
            session.clear()
            
            # 设置Flask session
            session['user_id'] = user_info['id']
            session['username'] = user_info['username']
            session['session_id'] = session_id
            session['login_time'] = datetime.now().isoformat()
            
            # 根据remember_me设置会话持久性
            session.permanent = remember_me
            
            # 强制保存session
            session.modified = True
            
            # 添加详细日志
            app.logger.info(f'✅ 登录成功: {username}, session_id: {session_id}')
            app.logger.info(f'🔍 Flask session内容: {dict(session)}')
            app.logger.info(f'🔍 Session permanent: {session.permanent}')
            app.logger.info(f'🔍 Session cookie配置: {app.config["SESSION_COOKIE_NAME"]}')
            
            return jsonify({
                'success': True,
                'message': message,
                'user': user_info['username'],
                'session_id': session_id,  # 临时调试用
                'xuexi_specific_data': {
                    'access_level': user_info['access_level']
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 401

    except Exception as e:
        app.logger.error(f'❌ 血袭燃烧登录异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'服务器内部错误: {str(e)}'
        }), 500


@app.route('/xuexi_ranshao/logout', methods=['POST'])
def xuexi_logout():
    try:
        session_id = session.get('session_id')
        if session_id:
            user_manager.invalidate_session(session_id)
        
        session.clear()
        
        return jsonify({
            'success': True,
            'message': '已成功退出登录'
        })
    except Exception as e:
        app.logger.error(f'退出登录异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'退出登录失败: {str(e)}'
        }), 500

@app.route('/xuexi_ranshao/check_auth', methods=['GET'])
def check_auth():
    """检查用户认证状态 - 增强版"""
    try:
        app.logger.info(f'🔍 [check_auth] 收到认证检查请求')
        app.logger.info(f'🔍 [check_auth] Request headers: {dict(request.headers)}')
        app.logger.info(f'🔍 [check_auth] Request cookies: {dict(request.cookies)}')
        app.logger.info(f'🔍 [check_auth] Flask session: {dict(session)}')
        app.logger.info(f'🔍 [check_auth] Session cookie name: {app.config["SESSION_COOKIE_NAME"]}')
        app.logger.info(f'🔍 [check_auth] Session cookie domain: {app.config["SESSION_COOKIE_DOMAIN"]}')
        
        # 检查原始 Cookie 值
        raw_cookie = request.cookies.get(app.config['SESSION_COOKIE_NAME'])
        app.logger.info(f'🔍 [check_auth] 原始Cookie值: {raw_cookie}')
        
        session_id = session.get('session_id')
        app.logger.info(f'🔍 [check_auth] 提取session_id: {session_id}')
        
        if not session_id:
            app.logger.warning('❌ [check_auth] Flask session中没有session_id')
            return jsonify({
                'authenticated': False,
                'reason': 'no_session_id'
            })
        
        # 验证数据库中的session
        user_info = user_manager.validate_session(session_id)
        app.logger.info(f'{user_info}')
        if user_info:
            app.logger.info(f'✅ [check_auth] 认证成功: {user_info["username"]}')
            return jsonify({
                'authenticated': True,
                'user': user_info
            })
        else:
            app.logger.warning(f'❌ [check_auth] 数据库session验证失败: {session_id}')
            session.clear()
            return jsonify({
                'authenticated': False,
                'reason': 'invalid_session'
            })
            
    except Exception as e:
        app.logger.error(f'❌ [check_auth] 检查认证状态异常: {str(e)}')
        return jsonify({
            'authenticated': False,
            'reason': 'exception',
            'error': str(e)
        })

# 前端登录成功后，后续API请求没有正确传递会话ID
@app.route('/api/blood_cooperatives_data')
def get_blood_cooperatives_data():
    """获取血袭合作社任务数据API - 增强认证"""
    try:
        # 详细的会话调试信息
        app.logger.info(f'🔍 [API] 收到数据请求')
        app.logger.info(f'🔍 [API] Headers: {dict(request.headers)}')
        app.logger.info(f'🔍 [API] Cookies: {dict(request.cookies)}')
        app.logger.info(f'🔍 [API] Flask session: {dict(session)}')
        
        session_id = session.get('session_id')
        app.logger.info(f'🔍 [API] 提取session_id: {session_id}')
        
        if not session_id:
            app.logger.warning('❌ [API] 没有找到session_id')
            return jsonify({
                'success': False, 
                'message': '未找到会话ID，请重新登录',
                'error_code': 'NO_SESSION_ID'
            }), 401
        
        # 验证会话
        user_info = user_manager.validate_session(session_id)
        app.logger.info(f'🔍 [API] 用户验证结果: {user_info}')
        
        if not user_info:
            app.logger.warning(f'❌ [API] 会话验证失败: {session_id}')
            session.clear()
            return jsonify({
                'success': False,
                'message': '会话已过期，请重新登录',
                'error_code': 'INVALID_SESSION'
            }), 401
        
        # 从请求参数获取血袭合作社凭据
        blood_username = request.args.get('blood_username')
        blood_password = request.args.get('blood_password')
        
        if not blood_username or not blood_password:
            return jsonify({
                'success': False,
                'message': '缺少血袭合作社用户名或密码'
            }), 400
        
        # 获取合作社数据
        app.logger.info(f'📡 开始获取合作社数据，用户: {blood_username}')
        cooperatives_data = get_blood_cooperatives_task_data(blood_username, blood_password)
        
        if not cooperatives_data:
            app.logger.warning('获取合作社数据失败或数据为空')
            return jsonify({
                'success': False,
                'message': '获取合作社数据失败，请检查用户名和密码是否正确'
            }), 400
        
        app.logger.info(f'✅ 成功获取 {len(cooperatives_data)} 条合作社数据')
        
        # 将数据保存到数据库
        try:
            save_success, save_message = save_blood_data_to_db(
                user_info['id'], 
                user_info['username'], 
                cooperatives_data
            )
            app.logger.info(f'💾 数据保存结果: {save_success}, 消息: {save_message}')
        except Exception as save_error:
            app.logger.error(f'❌ 数据保存异常: {str(save_error)}')
            save_success, save_message = False, f'数据保存失败: {str(save_error)}'
        
        # 数据处理和统计
        from collections import defaultdict
        
        bounty_summary = defaultdict(lambda: {'count': 0, 'total_bounty': 0})
        total_missions = len(cooperatives_data)
        total_bounty = 0
        
        for mission in cooperatives_data:
            status = mission.get('status', 'unknown')
            bounty = float(mission.get('bounty', 0))  # 确保是数字类型
            
            bounty_summary[status]['count'] += 1
            bounty_summary[status]['total_bounty'] += bounty
            total_bounty += bounty
        
        # 转换为普通字典以便JSON序列化
        summary_dict = dict(bounty_summary)
        
        app.logger.info(f'📊 数据统计完成: 总任务数 {total_missions}, 总奖金 {total_bounty}')
        
        return jsonify({
            'success': True,
            'data': {
                'missions': cooperatives_data,
                'summary': {
                    'total_missions': total_missions,
                    'total_bounty': round(total_bounty, 2),  # 保留两位小数
                    'status_breakdown': summary_dict
                },
                'user': user_info['username'],
                'timestamp': datetime.now().isoformat(),
                'db_save_status': {
                    'success': save_success,
                    'message': save_message
                }
            }
        })
        
    except requests.exceptions.Timeout:
        app.logger.error('🕐 合作社API请求超时')
        return jsonify({
            'success': False,
            'message': '请求超时，请稍后重试'
        }), 408
        
    except requests.exceptions.ConnectionError:
        app.logger.error('🌐 合作社API连接错误')
        return jsonify({
            'success': False,
            'message': '网络连接失败，请检查网络连接'
        }), 503
        
    except requests.exceptions.RequestException as e:
        app.logger.error(f'📡 合作社API请求异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': '网络请求失败，请稍后重试'
        }), 500
        
    except KeyError as e:
        app.logger.error(f'🔑 合作社数据解析异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': '数据格式异常，可能是API响应格式变更'
        }), 500
        
    except ValueError as e:
        app.logger.error(f'💰 数据类型转换异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': '数据处理异常，请联系管理员'
        }), 500
        
    except Exception as e:
        app.logger.error(f'❌ 获取合作社数据异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'服务器内部错误: {str(e)}'
        }), 500

@app.route('/xuexi_ranshao/register', methods=['POST'])
def xuexi_register():
    try:
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')

        if not username or not password:
            return jsonify({
                'success': False,
                'message': '用户名和密码不能为空'
            }), 400

        # 密码强度验证
        if len(password) < 8:
            return jsonify({
                'success': False,
                'message': '密码长度至少8位'
            }), 400

        success, message = user_manager.create_user(username, password, email)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 409

    except Exception as e:
        app.logger.error(f'血袭燃烧注册异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'服务器内部错误: {str(e)}'
        }), 500
        

# 在 app.py 中添加调试路由
@app.route('/debug/session_test', methods=['GET', 'POST'])
def session_debug():
    """Session调试路由"""
    import json
    from flask import make_response
    
    debug_info = {
        'method': request.method,
        'timestamp': datetime.now().isoformat(),
        'flask_config': {
            'SECRET_KEY': app.secret_key[:10] + '...',  # 只显示前10位
            'SESSION_COOKIE_NAME': app.config.get('SESSION_COOKIE_NAME'),
            'SESSION_COOKIE_DOMAIN': app.config.get('SESSION_COOKIE_DOMAIN'),
            'SESSION_COOKIE_PATH': app.config.get('SESSION_COOKIE_PATH'),
            'SESSION_COOKIE_SECURE': app.config.get('SESSION_COOKIE_SECURE'),
            'SESSION_COOKIE_HTTPONLY': app.config.get('SESSION_COOKIE_HTTPONLY'),
            'SESSION_COOKIE_SAMESITE': app.config.get('SESSION_COOKIE_SAMESITE'),
        },
        'request_info': {
            'headers': dict(request.headers),
            'cookies': dict(request.cookies),
            'host': request.host,
            'url': request.url,
            'remote_addr': request.remote_addr,
        },
        'session_info': {
            'session_data': dict(session),
            'session_permanent': session.permanent,
            'session_new': session.new,
            'session_modified': session.modified,
        }
    }
    
    if request.method == 'POST':
        # 测试设置session
        test_data = {
            'test_key': 'test_value',
            'timestamp': datetime.now().isoformat(),
            'counter': session.get('counter', 0) + 1
        }
        
        session.clear()
        session.update(test_data)
        session.permanent = True
        session.modified = True
        
        debug_info['action'] = 'session_set'
        debug_info['set_data'] = test_data
        
        app.logger.info(f'🧪 [DEBUG] Session设置测试: {test_data}')
        
    else:
        debug_info['action'] = 'session_read'
        
    # 检查Cookie解析
    raw_cookie = request.cookies.get(app.config['SESSION_COOKIE_NAME'])
    if raw_cookie:
        try:
            # 尝试手动解析Cookie
            from flask.sessions import SecureCookieSessionInterface
            session_interface = SecureCookieSessionInterface()
            
            # 创建一个临时的session对象来测试解析
            from flask.sessions import SecureCookieSession
            test_session = SecureCookieSession()
            
            debug_info['cookie_analysis'] = {
                'raw_cookie_length': len(raw_cookie),
                'raw_cookie_preview': raw_cookie[:50] + '...' if len(raw_cookie) > 50 else raw_cookie,
                'cookie_starts_with_dot': raw_cookie.startswith('.'),
            }
            
        except Exception as e:
            debug_info['cookie_analysis'] = {
                'error': str(e),
                'raw_cookie_length': len(raw_cookie) if raw_cookie else 0
            }
    
    response = make_response(jsonify(debug_info))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    
    return response
    
# 在现有的API路由后添加
@app.route('/api/mission_status_summary')
def get_mission_status_summary_api():
    """获取任务状态统计信息API"""
    try:
        # 验证会话
        session_id = session.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'message': '未找到会话ID，请重新登录'
            }), 401
        
        user_info = user_manager.validate_session(session_id)
        if not user_info:
            session.clear()
            return jsonify({
                'success': False,
                'message': '会话已过期，请重新登录'
            }), 401
        
        # 获取最新的任务状态统计信息
        mission_status = get_mission_status_summary()
        
        return jsonify({
            'success': True,
            'data': mission_status,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f'获取任务状态统计信息异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'服务器内部错误: {str(e)}'
        }), 500
        
if __name__ == "__main__":
    app.run(debug=True, port=5001)
