// 主要功能函数
async function loadChart(name = '伊甸币') {
    console.log('开始加载图表，物品名称:', name);
    const data = await fetchPriceHistory(name);
    console.log('获取到的数据:', data);
    
    if (!data || data.length === 0) {
        console.error('没有获取到数据');
        return;
    }

    const dates = data.map(item => item.date);
    const highests = data.map(item => item.highest);
    const lowest = data.map(item => item.lowest);
    const latest = data[data.length - 1];

    console.log('处理后的数据:', {
        dates,
        highests,
        lowest,
        latest
    });

    // 更新图表
    updateChart(dates, highests, lowest);
    
    // 更新信息栏
    updateInfoBar(latest);
    
    // 更新标题栏
    const iconUrl = data[0].icon_url || '';
    const itemName = data[0].item_name || name;
    console.log('更新标题栏:', { iconUrl, itemName });
    updateTitleBar(iconUrl, itemName);
}

function searchItem() {
    const name = document.getElementById('searchInput').value.trim();
    if (name) {
        console.log('搜索物品:', name);
        loadChart(name);
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    console.log('页面加载完成，开始初始化');
    // 初始化图表
    initChart();
    
    // 添加回车键搜索功能
    document.getElementById('searchInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            searchItem();
        }
    });
    
    // 页面加载时默认查询
    loadChart();
}); 