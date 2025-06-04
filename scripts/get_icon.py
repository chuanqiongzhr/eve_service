import sqlite3
import requests

def get_item_icon(item_id):
    """获取物品图标"""
    url = f'https://esi.evetech.net/latest/universe/types/{item_id}/?datasource=tranquility'
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        icon_id = data.get('icon_id')
        if icon_id:
            return f'https://images.evetech.net/types/{item_id}/icon?size=64'
        else:
            print(f"未找到物品 {item_id} 的图标")
            return None
    else:
        print(f"获取物品 {item_id} 信息失败，状态码: {response.status_code}")
        return None
    
if __name__ == '__main__':
    item_id = 34
    icon_url = get_item_icon(item_id)
    if icon_url:
        print(f"物品 {item_id} 的图标 URL: {icon_url}")
    else:
        print("未能获取物品图标")