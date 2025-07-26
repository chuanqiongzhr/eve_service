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

# 配置会话
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False  # 默认非永久
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'eve_service:'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # 永久会话30天过期

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
    # 获取任务状态统计信息
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

# 移除旧的USERS字典和相关函数
# 删除 validate_xuexi_user 和 register_xuexi_user 函数

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

        user_info, message = user_manager.authenticate_user(username, password)
        
        if user_info:
            # 创建会话，根据记住我选项设置不同的过期时间
            session_id = user_manager.create_session(user_info['id'], remember_me)
            session['user_id'] = user_info['id']
            session['username'] = user_info['username']
            session['session_id'] = session_id
            
            # 如果选择了记住我，设置会话为永久
            if remember_me:
                session.permanent = True
            
            return jsonify({
                'success': True,
                'message': message,
                'user': user_info['username'],
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
        app.logger.error(f'血袭燃烧登录异常: {str(e)}')
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
    """检查用户认证状态"""
    try:
        session_id = session.get('session_id')
        if not session_id:
            return jsonify({'authenticated': False})
        
        user_info = user_manager.validate_session(session_id)
        if user_info:
            return jsonify({
                'authenticated': True,
                'user': user_info
            })
        else:
            session.clear()
            return jsonify({'authenticated': False})
    except Exception as e:
        app.logger.error(f'检查认证状态异常: {str(e)}')
        return jsonify({'authenticated': False})

@app.route('/api/blood_cooperatives_data', methods=['GET'])
def get_blood_cooperatives_data():
    """获取血袭合作社任务数据API"""
    try:
        # 检查用户是否已登录
        session_id = session.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        # 验证会话
        user_info = user_manager.validate_session(session_id)
        if not user_info:
            session.clear()
            return jsonify({
                'success': False,
                'message': '会话已过期，请重新登录'
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
        cooperatives_data = get_blood_cooperatives_task_data(blood_username, blood_password)
        
        if not cooperatives_data:
            return jsonify({
                'success': False,
                'message': '获取合作社数据失败'
            }), 500
        
        # 将到达数据保存到数据库
        save_success, save_message = save_blood_data_to_db(
            user_info['id'], 
            user_info['username'], 
            cooperatives_data
        )
        
        # 数据处理和统计
        from collections import defaultdict
        
        # 按状态统计任务数据
        bounty_summary = defaultdict(lambda: {'count': 0, 'total_bounty': 0})
        total_missions = len(cooperatives_data)
        total_bounty = 0
        
        for mission in cooperatives_data:
            status = mission.get('status', 'unknown')
            bounty = mission.get('bounty', 0)
            
            bounty_summary[status]['count'] += 1
            bounty_summary[status]['total_bounty'] += bounty
            total_bounty += bounty
        
        # 转换为普通字典以便JSON序列化
        summary_dict = dict(bounty_summary)
        
        return jsonify({
            'success': True,
            'data': {
                'missions': cooperatives_data,
                'summary': {
                    'total_missions': total_missions,
                    'total_bounty': total_bounty,
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
        
    except requests.exceptions.RequestException as e:
        app.logger.error(f'合作社API请求异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': '网络请求失败，请检查网络连接'
        }), 500
        
    except KeyError as e:
        app.logger.error(f'合作社数据解析异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': '数据解析失败，可能是API响应格式变更'
        }), 500
        
    except Exception as e:
        app.logger.error(f'获取合作社数据异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'服务器内部错误: {str(e)}'
        }), 500

@app.route('/api/blood_cooperatives_summary', methods=['GET'])
def get_blood_cooperatives_summary():
    """获取血袭合作社数据摘要API（仅统计信息）"""
    try:
        # 检查用户是否已登录
        session_id = session.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        # 验证会话
        user_info = user_manager.validate_session(session_id)
        if not user_info:
            session.clear()
            return jsonify({
                'success': False,
                'message': '会话已过期，请重新登录'
            }), 401
        
        # 获取参数
        username = request.args.get('username')
        password = request.args.get('password')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': '缺少血袭合作社用户名或密码'
            }), 400
        
        # 从请求参数获取血袭合作社凭据
        blood_username = request.args.get('blood_username')  # 修改参数名
        blood_password = request.args.get('blood_password')  # 修改参数名
        
        if not blood_username or not blood_password:
            return jsonify({
                'success': False,
                'message': '缺少血袭合作社用户名或密码'
            }), 400
        
        # 获取合作社数据
        cooperatives_data = get_blood_cooperatives_task_data(blood_username, blood_password)  # 使用正确的变量名
        
        if not cooperatives_data:
            return jsonify({
                'success': False,
                'message': '获取合作社数据失败'
            }), 500
        
        # 仅返回统计摘要，不返回详细任务数据
        from collections import defaultdict
        
        bounty_summary = defaultdict(lambda: {'count': 0, 'total_bounty': 0})
        total_missions = len(cooperatives_data)
        total_bounty = 0
        
        for mission in cooperatives_data:
            status = mission.get('status', 'unknown')
            bounty = mission.get('bounty', 0)
            
            bounty_summary[status]['count'] += 1
            bounty_summary[status]['total_bounty'] += bounty
            total_bounty += bounty
        
        return jsonify({
            'success': True,
            'data': {
                'summary': {
                    'total_missions': total_missions,
                    'total_bounty': total_bounty,
                    'status_breakdown': dict(bounty_summary)
                },
                'user': user_info['username'],
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        app.logger.error(f'获取合作社摘要异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'服务器内部错误: {str(e)}'
        }), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)
    