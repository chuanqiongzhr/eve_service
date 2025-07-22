import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import time
from functools import lru_cache

def get_total_pages(item_id, region_id=10000002):
    url = f'https://esi.evetech.net/latest/markets/{region_id}/orders/?datasource=tranquility&order_type=all&page=1&type_id={item_id}'
    response = requests.get(url)
    if 'x-pages' in response.headers:
        return int(response.headers['x-pages'])
    return 1

def fetch_page(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return []

# 添加缓存装饰器
@lru_cache(maxsize=1000)
def get_buy_sell_data(item_id):
    '''Fetches buy and sell data for a given item ID from the API, with progress bar and multithreading.'''
    region_id = 10000002  # 伏尔戈
    total_pages = get_total_pages(item_id, region_id)
    buy_data = []
    sell_data = []
    urls = [
        f'https://esi.evetech.net/latest/markets/{region_id}/orders/?datasource=tranquility&order_type=all&page={page}&type_id={item_id}'
        for page in range(1, total_pages + 1)
    ]
    with ThreadPoolExecutor(max_workers=40) as executor:
        futures = {executor.submit(fetch_page, url): url for url in urls}
        for future in tqdm(as_completed(futures), total=total_pages, desc="获取数据"):
            data = future.result()
            if data:
                buy_data.extend([order for order in data if order['is_buy_order']])
                sell_data.extend([order for order in data if not order['is_buy_order']])
    return buy_data, sell_data

def get_max_buy_price_from_data(buy_data, station_id):
    station_orders = [order for order in buy_data if order['location_id'] == station_id]
    prices = [order['price'] for order in station_orders]
    return max(prices) if prices else None

def get_min_sell_price_from_data(sell_data, station_id):
    station_orders = [order for order in sell_data if order['location_id'] == station_id]
    prices = [order['price'] for order in station_orders]
    return min(prices) if prices else None

def get_middle_price_from_data(buy_data, sell_data, station_id):
    max_buy_price = get_max_buy_price_from_data(buy_data, station_id)
    min_sell_price = get_min_sell_price_from_data(sell_data, station_id)
    if max_buy_price is not None and min_sell_price is not None:
        return round((float(max_buy_price) + float(min_sell_price)) / 2, 2)
    return None

# Example usage:
if __name__ == '__main__':
    item_id = 34  # Example item ID
    station_id = 60003760  # jita IV - Moon 4 - Caldari Navy Assembly Plant
    buy_data, sell_data = get_buy_sell_data(item_id)
    max_buy_price = get_max_buy_price_from_data(buy_data, station_id)
    min_sell_price = get_min_sell_price_from_data(sell_data, station_id)
    middle_price = get_middle_price_from_data(buy_data, sell_data, station_id)
    print(max_buy_price)
    print(min_sell_price)
    print(middle_price)

