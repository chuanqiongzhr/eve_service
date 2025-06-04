import re
import unittest

class TestRegexExtraction(unittest.TestCase):
    def test_extract_zhongpixie(self):
        # 测试用例
        test_cases = [
            "中级辟邪 - 阿尔法型",
            "中辟邪",
            "中级辟邪",
            "中辟邪型",
            "中辟邪-阿尔法"
        ]
        
        # 正则表达式模式
        pattern = r"中(?:级)?辟邪"
        
        for test_str in test_cases:
            match = re.search(pattern, test_str)
            self.assertIsNotNone(match, f"在字符串 '{test_str}' 中未找到匹配")
            # 使用正则表达式的替换功能来移除"级"字
            result = re.sub(r"中(?:级)?辟邪", "中辟邪", match.group())
            self.assertEqual(result, "中辟邪", f"提取结果不正确: {result}")

if __name__ == '__main__':
    unittest.main()
