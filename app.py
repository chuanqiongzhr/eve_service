from flask import Flask, render_template, jsonify, request, send_from_directory
from scripts.get_price_history import name_to_id, get_price_history
from scripts.get_icon import get_item_icon
from scripts.get_buy_sell import get_buy_sell_data, get_max_buy_price_from_data, get_min_sell_price_from_data, get_middle_price_from_data

app = Flask(__name__)

# 禁用静态文件缓存
@app.after_request
def add_header(response):
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-store'
    return response

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/price_history")
def price_history_page():
    return render_template("price_history.html")

@app.route("/api/price_history")
def price_history():
    name = request.args.get("name", "伊甸币")
    type_id, chinese_name = name_to_id(name)
    region_id = 10000002
    station_id = 60003760
    price_history = get_price_history(region_id=region_id, type_id=type_id)
    # 获取icon url
    icon_url = get_item_icon(type_id)
    buy_data, sell_data = get_buy_sell_data(type_id)
    # 获取买卖价格
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
    return jsonify(price_history)

if __name__ == "__main__":
    app.run(debug=True, port=5001)