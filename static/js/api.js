// API 相关函数
async function fetchPriceHistory(name) {
    try {
        const response = await fetch(`/api/price_history?name=${encodeURIComponent(name)}`);
        if (!response.ok) {
            throw new Error('网络响应不正常');
        }
        return await response.json();
    } catch (error) {
        console.error('获取价格历史失败:', error);
        return null;
    }
} 