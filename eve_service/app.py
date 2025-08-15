from flask import Flask, render_template, jsonify, request, send_from_directory, session, redirect
from eve_service.scripts.get_price_history import name_to_id, get_price_history
from eve_service.scripts.get_icon import get_item_icon
from eve_service.scripts.get_buy_sell import get_buy_sell_data, get_max_buy_price_from_data, get_min_sell_price_from_data, get_middle_price_from_data
from eve_service.scripts.search_items import search_items
from eve_service.scripts.get_blood_lp import get_blood_lp_rate, get_blood_cooperatives_task_data, save_blood_data_to_db, get_mission_status_summary, get_blood_raider_lp_from_db
from eve_service.scripts.models import UserManager 
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from datetime import datetime, timedelta
import os
import requests
import base64
import secrets
import urllib.parse

app = Flask(__name__)

# 配置会话密钥（生产环境中应该从环境变量读取）
# 在文件顶部导入
from datetime import timedelta

# 配置会话 - 统一配置（保留这一份）
app.secret_key = os.environ.get('SECRET_KEY', 'b7c820226a1891011f53889d5e0d1295bbdd4b0d1faa12a1757cbd2644339ea4')
print(f"[DEBUG] 当前 Flask SECRET_KEY: {app.secret_key}")
#
# Generated with the EVE Online Developer Portal
# Application: EVEservice
# Description:
#   for personal account information get and process
#

# The client identifier to use when authenticating with the EVE Online SSO.
client_id = "d2be126e6b31486daa8229156cecba15"

# You should treat your client secret as you would a password. Do not share it outside of your application,
# or package it along with your application in a way that would expose it to users.
client_secret = "kL06gnPLF5n3fOefVuG4uiqZcZl5XNKNRxJP6n52"

# The SSO will only accept this as a valid callback URL:
callback_url = "http://eve.chuanqiong.work/auth/callback"

# This application can only request the following scopes:
scopes = ["publicData","esi-calendar.respond_calendar_events.v1","esi-calendar.read_calendar_events.v1","esi-location.read_location.v1","esi-location.read_ship_type.v1","esi-mail.organize_mail.v1","esi-mail.read_mail.v1","esi-mail.send_mail.v1","esi-skills.read_skills.v1","esi-skills.read_skillqueue.v1","esi-wallet.read_character_wallet.v1","esi-wallet.read_corporation_wallet.v1","esi-search.search_structures.v1","esi-clones.read_clones.v1","esi-characters.read_contacts.v1","esi-universe.read_structures.v1","esi-killmails.read_killmails.v1","esi-corporations.read_corporation_membership.v1","esi-assets.read_assets.v1","esi-planets.manage_planets.v1","esi-fleets.read_fleet.v1","esi-fleets.write_fleet.v1","esi-ui.open_window.v1","esi-ui.write_waypoint.v1","esi-characters.write_contacts.v1","esi-fittings.read_fittings.v1","esi-fittings.write_fittings.v1","esi-markets.structure_markets.v1","esi-corporations.read_structures.v1","esi-characters.read_loyalty.v1","esi-characters.read_chat_channels.v1","esi-characters.read_medals.v1","esi-characters.read_standings.v1","esi-characters.read_agents_research.v1","esi-industry.read_character_jobs.v1","esi-markets.read_character_orders.v1","esi-characters.read_blueprints.v1","esi-characters.read_corporation_roles.v1","esi-location.read_online.v1","esi-contracts.read_character_contracts.v1","esi-clones.read_implants.v1","esi-characters.read_fatigue.v1","esi-killmails.read_corporation_killmails.v1","esi-corporations.track_members.v1","esi-wallet.read_corporation_wallets.v1","esi-characters.read_notifications.v1","esi-corporations.read_divisions.v1","esi-corporations.read_contacts.v1","esi-assets.read_corporation_assets.v1","esi-corporations.read_titles.v1","esi-corporations.read_blueprints.v1","esi-contracts.read_corporation_contracts.v1","esi-corporations.read_standings.v1","esi-corporations.read_starbases.v1","esi-industry.read_corporation_jobs.v1","esi-markets.read_corporation_orders.v1","esi-corporations.read_container_logs.v1","esi-industry.read_character_mining.v1","esi-industry.read_corporation_mining.v1","esi-planets.read_customs_offices.v1","esi-corporations.read_facilities.v1","esi-corporations.read_medals.v1","esi-characters.read_titles.v1","esi-alliances.read_contacts.v1","esi-characters.read_fw_stats.v1","esi-corporations.read_fw_stats.v1"]

# 统一的session配置
app.config['SESSION_COOKIE_NAME'] = 'eve_session'
app.config['SESSION_COOKIE_SECURE'] = True  
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

# 在现有路由后添加
@app.route('/api/blood_raider_lp')
def get_blood_raider_lp_api():
    """获取血袭者LP点数API接口"""
    try:
        blood_raider_lp = get_blood_raider_lp_from_db()
        return jsonify({
            'success': True,
            'blood_raider_lp': blood_raider_lp
        })
    except Exception as e:
        app.logger.error(f'获取血袭者LP点数失败: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'获取血袭者LP点数失败: {str(e)}'
        }), 500
        
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
    # 获取血袭者LP点数
    blood_raider_lp = get_blood_raider_lp_from_db()
    return render_template("xuexi_ranshao.html", max_isk_lp=max_isk_lp, mission_status=mission_status, blood_raider_lp=blood_raider_lp)

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
    """获取血袭合作社任务数据API - 增强认证并集成EVE SSO数据"""
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
        cooperatives_response = get_blood_cooperatives_task_data(blood_username, blood_password)
        
        # 从返回的完整数据中提取任务列表
        cooperatives_data = cooperatives_response.get('data', []) if cooperatives_response else []
        
        if not cooperatives_data:
            app.logger.warning('获取合作社数据失败或数据为空')
            return jsonify({
                'success': False,
                'message': '获取合作社数据失败，请检查用户名和密码是否正确'
            }), 400
        
        app.logger.info(f'✅ 成功获取 {len(cooperatives_data)} 条合作社数据')
        
        # 将血袭合作社数据保存到数据库
        try:
            save_success, save_message = save_blood_data_to_db(
                user_info['id'], 
                user_info['username'], 
                cooperatives_data
            )
            app.logger.info(f'💾 血袭合作社数据保存结果: {save_success}, 消息: {save_message}')
        except Exception as save_error:
            app.logger.error(f'❌ 血袭合作社数据保存异常: {str(save_error)}')
            save_success, save_message = False, f'血袭合作社数据保存失败: {str(save_error)}'
        
        # 检查并获取EVE SSO数据
        eve_data_result = {'success': False, 'message': '未登录EVE SSO'}
        eve_character_id = session.get('eve_character_id')
        eve_access_token = session.get('eve_access_token')
        eve_token_expires = session.get('eve_token_expires')
        
        if eve_character_id and eve_access_token:
            # 检查令牌是否过期
            try:
                if eve_token_expires:
                    expires_time = datetime.fromisoformat(eve_token_expires)
                    now = datetime.now()
                    
                    # 🔧 修复：在调用ESI API前检查并刷新token
                    if (expires_time - now).total_seconds() < 300:  # 如果token在5分钟内过期
                        app.logger.info('🔄 Token即将过期，尝试刷新')
                        refresh_success = refresh_eve_token()
                        if not refresh_success:
                            app.logger.error('❌ Token刷新失败')
                            eve_data_result = {'success': False, 'message': 'EVE SSO token已过期且刷新失败，请重新登录EVE SSO'}
                            # 清除过期的session数据
                            eve_keys = ['eve_access_token', 'eve_refresh_token', 'eve_character_id', 
                                       'eve_character_name', 'eve_token_expires']
                            for key in eve_keys:
                                session.pop(key, None)
                        else:
                            app.logger.info('✅ EVE SSO令牌刷新成功，继续获取数据')
                            # 更新token信息
                            eve_access_token = session.get('eve_access_token')
                    
                    # 如果token有效或刷新成功，继续获取数据
                    if eve_access_token and (datetime.now() < datetime.fromisoformat(session.get('eve_token_expires', '1970-01-01'))):
                        # 令牌有效，获取EVE数据
                        app.logger.info(f'🚀 开始获取EVE SSO数据，角色ID: {eve_character_id}')
                        
                        # 导入EVE数据获取函数
                        from .scripts.get_blood_lp import get_eve_character_data, save_eve_character_data_to_db

                        eve_data = get_eve_character_data(eve_character_id, eve_access_token)

                        # 🔧 修复：处理token过期错误
                        if isinstance(eve_data, dict) and eve_data.get('error') == 'token_expired':
                            app.logger.warning('🔄 检测到token过期，尝试刷新')
                            refresh_success = refresh_eve_token()
                            if refresh_success:
                                # 重新尝试获取数据
                                eve_data = get_eve_character_data(eve_character_id, session['eve_access_token'])
                            else:
                                eve_data_result = {'success': False, 'message': 'EVE SSO token已过期且刷新失败，请重新登录EVE SSO'}
                                # 清除过期的session数据
                                eve_keys = ['eve_access_token', 'eve_refresh_token', 'eve_character_id', 
                                           'eve_character_name', 'eve_token_expires']
                                for key in eve_keys:
                                    session.pop(key, None)

                        if eve_data and not (isinstance(eve_data, dict) and eve_data.get('error')):
                            eve_save_success, eve_save_message = save_eve_character_data_to_db(
                                user_info['id'], 
                                eve_character_id, 
                                session.get('eve_character_name', 'Unknown'),
                                eve_data
                            )
                            
                            if eve_save_success:
                                app.logger.info('✅ EVE SSO数据获取并保存成功')
                                eve_data_result = {
                                    'success': True, 
                                    'message': 'EVE SSO数据更新成功',
                                    'data': eve_data
                                }
                            else:
                                app.logger.error(f'❌ EVE SSO数据保存失败: {eve_save_message}')
                                eve_data_result = {'success': False, 'message': f'EVE SSO数据保存失败: {eve_save_message}'}
                        else:
                            app.logger.warning('⚠️ EVE SSO数据获取失败')
                            eve_data_result = {'success': False, 'message': 'EVE SSO数据获取失败'}
                else:
                    eve_data_result = {'success': False, 'message': '令牌过期时间未知'}
            except Exception as eve_error:
                app.logger.error(f'❌ EVE SSO数据处理异常: {str(eve_error)}')
                eve_data_result = {'success': False, 'message': f'EVE SSO数据处理失败: {str(eve_error)}'}
        
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
                },
                'eve_sso_status': eve_data_result
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
@app.route('/api/paid_missions_summary')
def get_paid_missions_api():
    """获取已支付任务汇总API"""
    try:
        from eve_service.scripts.get_blood_lp import get_paid_missions_summary
        data = get_paid_missions_summary()
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/recent_wallet_donations')
def get_recent_wallet_donations_api():
    """获取最近钱包捐赠记录API"""
    try:
        from eve_service.scripts.get_blood_lp import get_recent_wallet_donations
        data = get_recent_wallet_donations(10)
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/wallet_incremental_update', methods=['POST'])
def wallet_incremental_update_api():
    """钱包增量更新API"""
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
        
        # 获取请求数据
        data = request.get_json() or {}
        force_refresh = data.get('force_refresh', False)
        
        # 🔧 修复：从Flask session中获取EVE角色信息
        character_id = session.get('eve_character_id')
        access_token = session.get('eve_access_token')
        character_name = session.get('eve_character_name', 'Unknown')
        
        if not character_id or not access_token:
            return jsonify({
                'success': False,
                'message': 'EVE角色信息不完整，请先进行EVE SSO登录'
            }), 400
        
        # 检查token是否过期
        eve_token_expires = session.get('eve_token_expires')
        if eve_token_expires:
            expires_time = datetime.fromisoformat(eve_token_expires)
            if datetime.now() >= expires_time:
                return jsonify({
                    'success': False,
                    'message': 'EVE SSO token已过期，请刷新token',
                    'error_type': 'token_expired'
                }), 401
        
        # 准备ESI请求头
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'EVE Service Wallet Updater'
        }
        
        # 调用增量更新函数
        from eve_service.scripts.get_blood_lp import get_wallet_journal_incremental, save_eve_character_data_to_db
        
        try:
            wallet_journal = get_wallet_journal_incremental(character_id, headers, force_refresh)
        except Exception as e:
            if 'token_expired' in str(e):
                return jsonify({
                    'success': False,
                    'message': 'EVE SSO token已过期，请刷新token',
                    'error_type': 'token_expired'
                }), 401
            else:
                raise e
        
        # 保存到数据库
        if wallet_journal:
            eve_data = {'wallet_journal': wallet_journal}
            user_id = user_info.get('id')  # 🔧 修复：使用正确的字段名
            
            success, message = save_eve_character_data_to_db(user_id, character_id, character_name, eve_data)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'增量更新成功，获取到 {len(wallet_journal)} 条新记录',
                    'new_entries': len(wallet_journal)
                })
            else:
                return jsonify({
                    'success': False,
                    'message': f'数据保存失败: {message}'
                }), 500
        else:
            return jsonify({
                'success': True,
                'message': '没有新的钱包记录',
                'new_entries': 0
            })
        
    except Exception as e:
        app.logger.error(f'钱包增量更新异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'服务器内部错误: {str(e)}'
        }), 500

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

@app.route('/api/mark_missions_done', methods=['POST'])
def mark_missions_done():
    """标记任务完成的代理API"""
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
            return jsonify({
                'success': False,
                'message': '会话已过期，请重新登录'
            }), 401
        
        # 获取请求数据
        data = request.get_json()
        mission_ids = data.get('mission_ids', [])
        
        if not mission_ids:
            return jsonify({
                'success': False,
                'message': '没有提供任务ID'
            }), 400
        
        # 这里需要获取用户的血袭合作社凭据
        # 你可能需要从数据库或其他地方获取
        # 暂时使用硬编码，实际应该从安全存储中获取
        blood_username = "your_username"  # 需要替换
        blood_password = "your_password"  # 需要替换
        
        # 获取token
        login_url = "https://bloodapi.cs-eve.com/api/tokens"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic Y2h1YW5xaW9uZzp6aHIxNTMwMDQzNjAy',
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        token_data = {
            "username": blood_username,
            "password": blood_password
        }
        
        token_response = requests.post(login_url, headers=headers, json=token_data)
        if not token_response.ok:
            return jsonify({
                'success': False,
                'message': '获取token失败'
            }), 400
        
        token_result = token_response.json()
        access_token = token_result.get('access_token')
        
        # 标记任务完成
        results = []
        headers_with_token = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        for mission_id in mission_ids:
            try:
                done_url = f"https://bloodapi.cs-eve.com/api/missions/{mission_id}/done"
                done_response = requests.post(done_url, headers=headers_with_token)
                
                if done_response.ok:
                    results.append({'mission_id': mission_id, 'status': 'success'})
                else:
                    results.append({
                        'mission_id': mission_id, 
                        'status': 'failed', 
                        'error': done_response.text
                    })
            except Exception as e:
                results.append({
                    'mission_id': mission_id, 
                    'status': 'error', 
                    'error': str(e)
                })
        
        # 1. 从数据库中删除已支付任务汇总中的相应条目
        try:
            from eve_service.scripts.get_blood_lp import get_paid_missions_summary
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(os.path.dirname(current_dir), 'scripts', 'eve_data.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 删除已支付任务中的相应条目
            for mission_id in mission_ids:
                cursor.execute('''
                    DELETE FROM blood_cooperative_data 
                    WHERE status = 'paid' AND mission_id = ?
                ''', (mission_id,))
            
            conn.commit()
            app.logger.info(f'✅ 成功从数据库中删除 {len(mission_ids)} 条已支付任务记录')
            
        except Exception as db_error:
            app.logger.error(f'❌ 删除已支付任务记录失败: {str(db_error)}')
        finally:
            if conn:
                conn.close()
        
        # 2. 触发从学习合作社获取新数据的更新
        try:
            from eve_service.scripts.get_blood_lp import collect_publisher_data, get_blood_cooperatives_task_data
            
            # 获取最新的合作社数据
            app.logger.info(f'📡 开始获取最新合作社数据，用户: {blood_username}')
            cooperatives_response = get_blood_cooperatives_task_data(blood_username, blood_password)
            
            # 从返回的完整数据中提取任务列表
            cooperatives_data = cooperatives_response.get('data', []) if cooperatives_response else []
            
            if cooperatives_data:
                # 将血袭合作社数据保存到数据库
                save_success, save_message = save_blood_data_to_db(
                    user_info['id'], 
                    user_info['username'], 
                    cooperatives_data
                )
                app.logger.info(f'💾 血袭合作社数据更新结果: {save_success}, 消息: {save_message}')
                
                # 收集发布者数据
                publisher_success, publisher_message = collect_publisher_data(blood_username, blood_password)
                app.logger.info(f'💾 发布者数据更新结果: {publisher_success}, 消息: {publisher_message}')
            else:
                app.logger.warning('⚠️ 获取合作社数据失败或数据为空')
                
        except Exception as update_error:
            app.logger.error(f'❌ 更新合作社数据失败: {str(update_error)}')
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        app.logger.error(f'标记任务完成异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500
        
# 在 get_mission_status_summary_api 路由之后，if __name__ == "__main__": 之前添加以下代码：

@app.route('/auth/login')
def eve_sso_login():
    """启动EVE SSO认证流程"""
    try:
        # 生成state参数用于防止CSRF攻击
        state = secrets.token_urlsafe(32)
        session['sso_state'] = state
        
        # 构建SSO授权URL
        auth_params = {
            'response_type': 'code',
            'redirect_uri': callback_url,
            'client_id': client_id,
            'scope': ' '.join(scopes),
            'state': state
        }
        
        auth_url = 'https://login.eveonline.com/v2/oauth/authorize?' + urllib.parse.urlencode(auth_params)
        
        app.logger.info(f'🚀 启动EVE SSO认证，重定向到: {auth_url}')
        
        return redirect(auth_url)
        
    except Exception as e:
        app.logger.error(f'❌ EVE SSO登录异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'SSO登录失败: {str(e)}'
        }), 500

@app.route('/auth/callback')
def eve_sso_callback():
    """处理EVE SSO回调"""
    try:
        # 验证state参数
        state = request.args.get('state')
        if not state or state != session.get('sso_state'):
            app.logger.error('❌ SSO state验证失败')
            return jsonify({
                'success': False,
                'message': 'SSO认证失败：state验证失败'
            }), 400
        
        # 获取授权码
        code = request.args.get('code')
        if not code:
            app.logger.error('❌ 未收到授权码')
            return jsonify({
                'success': False,
                'message': 'SSO认证失败：未收到授权码'
            }), 400
        
        # 交换访问令牌
        token_data = exchange_code_for_token(code)
        if not token_data:
            return jsonify({
                'success': False,
                'message': 'SSO认证失败：令牌交换失败'
            }), 400
        
        # 获取角色信息
        character_info = get_character_info(token_data['access_token'])
        if not character_info:
            return jsonify({
                'success': False,
                'message': 'SSO认证失败：获取角色信息失败'
            }), 400
        
        # 保存认证信息到session
        session['eve_access_token'] = token_data['access_token']
        session['eve_refresh_token'] = token_data.get('refresh_token')
        session['eve_character_id'] = character_info['CharacterID']
        session['eve_character_name'] = character_info['CharacterName']
        session['eve_token_expires'] = (datetime.now() + timedelta(seconds=max(token_data.get('expires_in', 1200), 3600))).isoformat()
        
        # 清理临时state
        session.pop('sso_state', None)
        
        app.logger.info(f'✅ EVE SSO认证成功: {character_info["CharacterName"]} (ID: {character_info["CharacterID"]})')
        app.logger.info(f'🔑 访问令牌: {token_data["access_token"]}')
        
        return redirect('/')
        
    except Exception as e:
        app.logger.error(f'❌ EVE SSO回调异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'SSO认证失败: {str(e)}'
        }), 500

@app.route('/auth/logout')
def eve_sso_logout():
    """EVE SSO登出"""
    try:
        # 清除EVE相关的session数据
        eve_keys = ['eve_access_token', 'eve_refresh_token', 'eve_character_id', 
                   'eve_character_name', 'eve_token_expires']
        for key in eve_keys:
            session.pop(key, None)
        
        app.logger.info('✅ EVE SSO登出成功')
        
        return redirect('/')
        
    except Exception as e:
        app.logger.error(f'❌ EVE SSO登出异常: {str(e)}')
        return redirect('/')

def exchange_code_for_token(code):
    """交换授权码获取访问令牌"""
    try:
        # 准备认证头
        auth_string = f"{client_id}:{client_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Host': 'login.eveonline.com'
        }
        
        data = {
            'grant_type': 'authorization_code',
            'code': code
        }
        
        response = requests.post(
            'https://login.eveonline.com/v2/oauth/token',
            headers=headers,
            data=data,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            app.logger.error(f'❌ 令牌交换失败: {response.status_code} - {response.text}')
            return None
            
    except Exception as e:
        app.logger.error(f'❌ 令牌交换异常: {str(e)}')
        return None

def get_character_info(access_token):
    """获取角色信息"""
    try:
        headers = {
            'Authorization': f'Bearer {access_token}',
            'User-Agent': 'EVEservice/1.0'
        }
        
        response = requests.get(
            'https://login.eveonline.com/oauth/verify',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            app.logger.error(f'❌ 获取角色信息失败: {response.status_code} - {response.text}')
            return None
            
    except Exception as e:
        app.logger.error(f'❌ 获取角色信息异常: {str(e)}')
        return None



def refresh_eve_token():
    """改进的EVE SSO访问令牌刷新机制"""
    try:
        if 'eve_refresh_token' not in session:
            app.logger.warning('没有refresh_token，无法刷新令牌')
            return False
            
        # 准备认证头
        auth_string = f"{client_id}:{client_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Host': 'login.eveonline.com'
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': session['eve_refresh_token']
        }
        
        response = requests.post(
            'https://login.eveonline.com/v2/oauth/token',
            headers=headers,
            data=data,
            timeout=10
        )
        
        if response.status_code == 200:
            token_data = response.json()
            
            # 更新session中的令牌信息
            session['eve_access_token'] = token_data['access_token']
            
            # 🆕 处理refresh token轮换
            if 'refresh_token' in token_data:
                session['eve_refresh_token'] = token_data['refresh_token']
                app.logger.info('✅ Refresh token已更新（支持token轮换）')
            
            # 🆕 智能过期时间计算
            expires_in = token_data.get('expires_in', 1200)
            # 提前5分钟刷新，避免边界情况
            safe_expires_in = max(expires_in - 300, 300)
            session['eve_token_expires'] = (datetime.now() + timedelta(seconds=safe_expires_in)).isoformat()
            
            # 🆕 记录token版本信息
            session['eve_token_version'] = 'v2'
            session['eve_token_last_refresh'] = datetime.now().isoformat()
            
            app.logger.info(f'✅ EVE SSO令牌刷新成功，{safe_expires_in}秒后过期')
            return True
        else:
            app.logger.error(f'❌ 令牌刷新失败: {response.status_code} - {response.text}')
            return False
            
    except Exception as e:
        app.logger.error(f'❌ 令牌刷新异常: {str(e)}')
        return False

@app.route('/auth/refresh', methods=['POST'])
def refresh_token_api():
    """刷新EVE SSO令牌的API端点"""
    try:
        if refresh_eve_token():
            return jsonify({
                'success': True,
                'message': 'Token刷新成功',
                'token_info': {
                    'character_id': session.get('eve_character_id'),
                    'character_name': session.get('eve_character_name'),
                    'token_expires': session.get('eve_token_expires'),
                    'has_access_token': bool(session.get('eve_access_token'))
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Token刷新失败，请重新登录'
            }), 401
    except Exception as e:
        app.logger.error(f'Token刷新API异常: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Token刷新失败: {str(e)}'
        }), 500

@app.before_request
def check_eve_token():
    if 'eve_token_expires' in session:
        expires_time = datetime.fromisoformat(session['eve_token_expires'])
        # 提前10分钟刷新令牌（增加缓冲时间）
        if datetime.now() >= expires_time - timedelta(minutes=10):
            try:
                # 使用refresh_token刷新访问令牌
                if not refresh_eve_token():
                    # 刷新失败，清除令牌信息
                    session.pop('eve_token_expires', None)
                    session.pop('eve_access_token', None)
                    session.pop('eve_refresh_token', None)
                    app.logger.warning('令牌刷新失败，已清除session信息')
            except Exception as e:
                app.logger.warning(f'令牌刷新失败: {e}')
                # 清除过期令牌，强制重新登录
                session.pop('eve_token_expires', None)
                session.pop('eve_access_token', None)
                session.pop('eve_refresh_token', None)


if __name__ == "__main__":
    app.run(debug=True, port=5001)