import csv
import re
from typing import List, Tuple, Optional

def load_items_from_csv(csv_path: str = "scripts/naocha.csv") -> List[Tuple[str, str]]:
    """
    从CSV文件加载物品数据
    
    Args:
        csv_path: CSV文件路径
        
    Returns:
        List[Tuple[str, str]]: 包含(id, name)元组的列表
    """
    items = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                items.append((row['id'], row['name']))
    except Exception as e:
        print(f"读取CSV文件时出错: {e}")
        return []
    return items

def normalize_text(text: str) -> str:
    """
    标准化文本，移除特殊字符和空格
    
    Args:
        text: 输入文本
        
    Returns:
        str: 标准化后的文本
    """
    # 移除所有特殊字符和空格
    return re.sub(r'[^\w\u4e00-\u9fff]', '', text.lower())

def expand_keyword(keyword: str) -> List[str]:
    """
    扩展关键词，处理常见的简写
    
    Args:
        keyword: 原始关键词
        
    Returns:
        List[str]: 扩展后的关键词列表
    """
    expansions = {
        '高': '高级',
        '中': '中级',
        '低': '低级',
        '阿': '阿尔法',
        '贝': '贝它',
        '伽': '伽玛',
        '德': '德尔塔',
        '伊': '伊普西隆',
        '欧': '欧米伽'
    }
    
    # 标准化关键词
    normalized = normalize_text(keyword)
    
    # 生成所有可能的组合
    expanded = [normalized]
    for short, full in expansions.items():
        if short in normalized:
            expanded.append(normalized.replace(short, full))
    
    return expanded

def search_items(keyword: str, items: Optional[List[Tuple[str, str]]] = None) -> List[Tuple[str, str]]:
    """
    根据关键词搜索物品
    
    Args:
        keyword: 搜索关键词
        items: 物品列表，如果为None则从CSV文件加载
        
    Returns:
        List[Tuple[str, str]]: 匹配的物品列表，每个元素为(id, name)元组
    """
    if items is None:
        items = load_items_from_csv()
    
    if not keyword:
        return []
    
    # 获取扩展后的关键词列表
    expanded_keywords = expand_keyword(keyword)
    
    # 搜索匹配的物品
    matches = []
    for item_id, name in items:
        normalized_name = normalize_text(name)
        # 检查是否匹配任何一个扩展后的关键词
        if any(expanded in normalized_name for expanded in expanded_keywords):
            matches.append((item_id, name))
    
    return matches

def get_item_id_by_name(name: str) -> Optional[str]:
    """
    根据物品名称获取物品ID
    
    Args:
        name: 物品名称
        
    Returns:
        Optional[str]: 物品ID，如果未找到则返回None
    """
    matches = search_items(name)
    if matches:
        return matches[0][0]  # 返回第一个匹配项的ID
    return None

def get_all_items_by_type(item_type: str) -> List[Tuple[str, str]]:
    """
    获取指定类型的所有物品
    
    Args:
        item_type: 物品类型（如"高级"、"中级"、"低级"等）
        
    Returns:
        List[Tuple[str, str]]: 匹配的物品列表
    """
    return search_items(item_type)

# 使用示例
if __name__ == "__main__":
    test_keywords = ["中辟邪", "高护符", "低水","中阿"]
    
    for keyword in test_keywords:
        print(f"\n搜索关键词: {keyword}")
        print("匹配结果：")
        for item_id, name in search_items(keyword):
            print(f"ID: {item_id}, 名称: {name}") 