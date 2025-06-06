// 主要功能函数
async function loadChart(name = '伊甸币') {
    console.log('开始加载图表，物品名称:', name);
    
    // 显示加载动画
    document.body.classList.add('loading');
    
    try {
        // 首先尝试从缓存获取数据
        const cachedData = getCache(name);
        let data;
        
        if (cachedData) {
            console.log('使用缓存数据');
            data = cachedData;
        } else {
            console.log('从服务器获取数据');
            data = await fetchPriceHistory(name);
            if (data && data.length > 0) {
                // 将数据存入缓存
                setCache(name, data);
            }
        }
        
        console.log('获取到的数据:', data);
        
        if (!data || data.length === 0) {
            console.error('没有获取到数据');
            // 清空图表和信息
            if (myChart) {
                myChart.clear();
            }
            document.getElementById('title-bar').innerHTML = '';
            document.getElementById('info-bar').innerHTML = '';
            return;
        }

        // 处理数据，将每个物品的价格历史数据组织成数组
        const processedData = [];
        const uniqueItems = [...new Set(data.map(item => item.item_name))];
        
        uniqueItems.forEach(itemName => {
            const itemData = data.filter(d => d.item_name === itemName);
            if (itemData.length > 0) {
                // 按日期排序
                const sortedData = itemData.sort((a, b) => new Date(a.date) - new Date(b.date));
                processedData.push({
                    item_name: itemName,
                    icon_url: itemData[0].icon_url,
                    max_buy_price: itemData[0].max_buy_price,
                    min_sell_price: itemData[0].min_sell_price,
                    middle_price: itemData[0].middle_price,
                    max_buy_price_set: itemData[0].max_buy_price_set,
                    min_sell_price_set: itemData[0].min_sell_price_set,
                    middle_price_set: itemData[0].middle_price_set,
                    dates: sortedData.map(d => d.date),
                    highests: sortedData.map(d => d.highest),
                    lowest: sortedData.map(d => d.lowest)
                });
            }
        });

        console.log('处理后的数据:', processedData);

        // 更新图表
        updateChart(processedData);
        
        // 更新信息栏
        updateInfoBar(processedData);
        
        // 更新标题栏
        updateTitleBar(processedData);
    } catch (error) {
        console.error('加载数据时出错:', error);
        // 清空图表和信息
        if (myChart) {
            myChart.clear();
        }
        document.getElementById('title-bar').innerHTML = '';
        document.getElementById('info-bar').innerHTML = '';
    } finally {
        // 隐藏加载动画
        document.body.classList.remove('loading');
    }
}

// 搜索功能
function searchItem() {
    const searchInput = document.getElementById('searchInput');
    const name = searchInput.value.trim();
    if (name) {
        loadChart(name);
    }
}

// 回车搜索
document.getElementById('searchInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        searchItem();
    }
});

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initChart();
    loadChart();
}); 