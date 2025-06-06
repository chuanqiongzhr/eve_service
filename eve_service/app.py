from flask import Flask, render_template, jsonify, request, send_from_directory
from eve_service.scripts.get_price_history import name_to_id, get_price_history
from eve_service.scripts.get_icon import get_item_icon
from eve_service.scripts.get_buy_sell import get_buy_sell_data, get_max_buy_price_from_data, get_min_sell_price_from_data, get_middle_price_from_data
from eve_service.scripts.database_init import from_ids_get_info
from eve_service.scripts.search_items import search_items
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

app = Flask(__name__)

def calculate_special_prices(name, max_buy_price, min_sell_price, middle_price):
    """计算特殊物品的额外价格信息"""
    special_prices = {}

    # id,chinese_name = name_to_id(name)
    # info = from_ids_get_info(id)
    # group_id = info.get('group_id')

    # if group_id == 300:
    #     if len(search_items(name)) != 1 and len(search_items(name)) == 6:
    #         max_buy = []
    #         min_sell = []
    #         middle = []
    #         for id, Name in search_items(name):
    #             buy_sell_data = get_buy_sell_data(id)
    #             max_buy.appdend(get_max_buy_price_from_data(buy_sell_data,station_id = 60003760))
    #             min_sell.appdend(get_min_sell_price_from_data(buy_sell_data,station_id = 60003760))
    #             middle.appdend((float(max_buy) + float(min_sell)) / 2)

    #         special_prices = {
    #             "max_buy_price_set": round(sum(max_buy) if max_buy else 0, 2),
    #             "min_sell_price_set": round(sum(min_sell) if min_sell else 0, 2),
    #             "middle_price_set": round(sum(middle) if middle else 0, 2),
    #             "unit": "一套"
    #         }


    if name == "伊甸币":
        # 伊甸币 500个一组
        special_prices = {
            "max_buy_price_500": round(max_buy_price * 500, 2) if max_buy_price else None,
            "min_sell_price_500": round(min_sell_price * 500, 2) if min_sell_price else None,
            "middle_price_500": round(middle_price * 500, 2) if middle_price else None,
            "unit": "500个"
        }
    # 可以继续添加其他特殊物品
    
    return special_prices

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

def process_item_data(item_id, item_name, region_id):
    """处理单个物品的数据获取"""
    item_price_history = get_price_history(region_id=region_id, type_id=item_id)
    if not item_price_history:
        return None
        
    buy_data, sell_data = get_buy_sell_data(item_id)
    max_buy_price = get_max_buy_price_from_data(buy_data, 60003760)
    min_sell_price = get_min_sell_price_from_data(sell_data, 60003760)
    middle_price = get_middle_price_from_data(buy_data, sell_data, 60003760)
    
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
    region_id = 10000002
    price_history = get_price_history(region_id=region_id, type_id=type_id)
    
    if not price_history:
        return jsonify([]), 200
    
    # 获取icon url
    icon_url = get_item_icon(type_id)
    
    buy_data, sell_data = get_buy_sell_data(type_id)
    # 获取买卖价格
    max_buy_price = get_max_buy_price_from_data(buy_data, 60003760)
    min_sell_price = get_min_sell_price_from_data(sell_data, 60003760)
    middle_price = get_middle_price_from_data(buy_data, sell_data, 60003760)
    
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

if __name__ == "__main__":
    app.run(debug=True, port=5001)