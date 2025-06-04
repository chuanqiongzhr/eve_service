// API 相关函数
async function fetchPriceHistory(name) {
    try {
        const response = await fetch(`/api/price_history?name=${name}`);
        if (!response.ok) {
            throw new Error('未找到物品数据');
        }
        const data = await response.json();
        if (!data || data.length === 0) {
            throw new Error('未找到物品数据');
        }
        return data;
    } catch (error) {
        console.error('获取价格历史失败:', error);
        showError('未找到物品数据，请检查物品名称是否正确');
        return null;
    }
}

// 显示错误提示
function showError(message) {
    const modal = document.getElementById('errorModal');
    const modalMessage = document.getElementById('modalMessage');
    modalMessage.textContent = message;
    modal.classList.add('show');
}

// 关闭弹窗
function closeModal() {
    const modal = document.getElementById('errorModal');
    modal.classList.remove('show');
} 