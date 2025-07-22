// 图表相关函数
let myChart = null;
let currentData = null;  // 存储当前数据

// 缓存相关配置
const CACHE_PREFIX = 'eve_price_cache_';
const CACHE_EXPIRY = 30 * 60 * 1000; // 30分钟缓存过期

// 缓存管理函数
function getCacheKey(name) {
    return CACHE_PREFIX + name;
}

// function setCache(name, data) {
//     const cacheData = {
//         timestamp: Date.now(),
//         data: data
//     };
//     try {
//         localStorage.setItem(getCacheKey(name), JSON.stringify(cacheData));
//     } catch (e) {
//         console.warn('缓存存储失败:', e);
//         // 如果存储失败，清理过期缓存后重试
//         clearExpiredCache();
//         try {
//             localStorage.setItem(getCacheKey(name), JSON.stringify(cacheData));
//         } catch (e) {
//             console.error('缓存存储重试失败:', e);
//         }
//     }
// }

// function getCache(name) {
//     try {
//         const cacheStr = localStorage.getItem(getCacheKey(name));
//         if (!cacheStr) return null;
        
//         const cache = JSON.parse(cacheStr);
//         if (Date.now() - cache.timestamp > CACHE_EXPIRY) {
//             // 缓存已过期，删除它
//             localStorage.removeItem(getCacheKey(name));
//             return null;
//         }
//         return cache.data;
//     } catch (e) {
//         console.warn('缓存读取失败:', e);
//         return null;
//     }
// }

function clearExpiredCache() {
    try {
        const now = Date.now();
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key.startsWith(CACHE_PREFIX)) {
                const cacheStr = localStorage.getItem(key);
                if (cacheStr) {
                    const cache = JSON.parse(cacheStr);
                    if (now - cache.timestamp > CACHE_EXPIRY) {
                        localStorage.removeItem(key);
                    }
                }
            }
        }
    } catch (e) {
        console.error('清理过期缓存失败:', e);
    }
}

function initChart() {
    myChart = echarts.init(document.getElementById('main'));
    window.addEventListener('resize', () => myChart.resize());
    // 初始化时清理过期缓存
    clearExpiredCache();
}

function updateChart(data) {
    // 存储当前数据
    currentData = data;
    
    // 获取所有日期
    const allDates = [...new Set(data.flatMap(item => item.dates))].sort();
    
    // 为每个物品创建价格序列
    const series = [];
    const items = [...new Set(data.map(item => item.item_name))];
    
    // 为每个物品创建价格序列
    items.forEach(itemName => {
        const itemData = data.find(d => d.item_name === itemName);
        if (itemData) {
            // 创建日期和价格的映射
            const highestMap = new Map(itemData.dates.map((date, index) => [date, itemData.highests[index]]));
            const lowestMap = new Map(itemData.dates.map((date, index) => [date, itemData.lowest[index]]));
            
            // 使用所有日期，如果某个日期没有数据则使用null
            const highestPrices = allDates.map(date => highestMap.get(date) || null);
            const lowestPrices = allDates.map(date => lowestMap.get(date) || null);
            
            series.push({
                name: itemName + ' (最高价)',
                type: 'line',
                data: highestPrices,
                smooth: true,
                symbol: 'circle',
                symbolSize: 6,
                lineStyle: {
                    width: 2
                },
                sampling: 'lttb',  // 使用 LTTB 采样算法
                progressive: 1000,  // 渐进式渲染
                progressiveThreshold: 5000  // 数据量超过5000时启用渐进式渲染
            });
            
            series.push({
                name: itemName + ' (最低价)',
                type: 'line',
                data: lowestPrices,
                smooth: true,
                symbol: 'circle',
                symbolSize: 6,
                lineStyle: {
                    width: 2
                },
                sampling: 'lttb',
                progressive: 1000,
                progressiveThreshold: 5000
            });
        }
    });
    
    // 如果有总价，添加总价线
    if (data[0].max_buy_price_set) {
        // 计算每个日期的总价
        const totalPrices = allDates.map(date => {
            const total = data.reduce((sum, item) => {
                const index = item.dates.indexOf(date);
                return sum + (index !== -1 ? item.highests[index] : 0);
            }, 0);
            return total;
        });

        series.push({
            name: '一套总价',
            type: 'line',
            data: totalPrices,
            lineStyle: {
                width: 3,
                type: 'dashed',
                color: '#ff5722'
            },
            symbol: 'none',
            sampling: 'lttb',
            progressive: 1000,
            progressiveThreshold: 5000
        });
    }

    const option = {
        title: { 
            text: '',
            subtext: '数据来源：宁静', 
            left: 'center',
            textStyle: { color: '#333', fontSize: 40, fontWeight: 'bold' },
            subtextStyle: { color: '#666', fontSize: 16 }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: { 
                type: 'line',
                animation: false
            },
            formatter: function(params) {
                if (!params || !params.length) return '';
                
                let result = params[0].axisValue + '<br/>';
                params.forEach(param => {
                    if (param && param.value !== null && param.value !== undefined) {
                        const value = typeof param.value === 'number' ? 
                            param.value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) : 
                            param.value;
                        result += param.marker + ' ' + param.seriesName + ': ' + value + '<br/>';
                    }
                });
                return result;
            }
        },
        legend: {
            data: items.flatMap(item => [item + ' (最高价)', item + ' (最低价)']).concat(data[0].max_buy_price_set ? ['一套总价'] : []),
            top: 30,
            type: 'scroll',
            pageButtonPosition: 'end',
            pageIconSize: 12,
            pageTextStyle: {
                color: '#333'
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: { 
            data: allDates,
            type: 'category',
            axisLabel: {
                formatter: function(value) {
                    return value.split('T')[0];
                },
                interval: Math.ceil(allDates.length / 20),
                rotate: 45
            }
        },
        yAxis: {
            type: 'value',
            name: '价格',
            axisLabel: {
                formatter: function(value) {
                    return value.toLocaleString();
                }
            },
            splitLine: {
                show: true,
                lineStyle: {
                    type: 'dashed'
                }
            }
        },
        series: series.map(s => ({
            ...s,
            symbol: 'none',  // 移除数据点标记
            sampling: 'lttb',
            progressive: 1000,
            progressiveThreshold: 5000,
            animation: false,  // 关闭单个系列的动画
            emphasis: {
                disabled: true  // 禁用高亮效果
            }
        })),
        animation: false,  // 关闭整体动画
        animationDuration: 0,
        animationEasing: 'linear'
    };

    // 使用 setOption 的第二个参数来优化更新
    myChart.setOption(option, {
        notMerge: false,
        lazyUpdate: true,
        silent: true  // 静默更新
    });

    // 使用防抖处理resize事件
    let resizeTimer = null;
    window.addEventListener('resize', () => {
        if (resizeTimer) {
            clearTimeout(resizeTimer);
        }
        resizeTimer = setTimeout(() => {
            myChart.resize();
        }, 100);
    });
}

function updateInfoBar(data) {
    let infoHtml = '';
    // 显示每个物品的价格信息
    data.forEach(item => {
        const buy = formatPrice(item.max_buy_price);
        const sell = formatPrice(item.min_sell_price);
        const middle = formatPrice(item.middle_price);
        
        infoHtml += `
            <div class="item-info">
                <img src="${item.icon_url}" style="width:32px;height:32px;vertical-align:middle;margin-right:10px;">
                <span style="font-size:1.2em;margin-right:20px;">${item.item_name}</span>
                <span style="margin:0 30px;">卖单 <b style="color:#1976d2">${sell}</b></span>
                <span style="margin:0 30px;">买单 <b style="color:#43a047">${buy}</b></span>
                <span style="margin:0 30px;">中位 <b style="color:#ffb300">${middle}</b></span>
            </div>
        `;
    });
    
    // 如果有总价，显示总价信息
    if (data[0].max_buy_price_set) {
        const totalBuy = formatPrice(data[0].max_buy_price_set);
        const totalSell = formatPrice(data[0].min_sell_price_set);
        const totalMiddle = formatPrice(data[0].middle_price_set);
        
        infoHtml += `
            <div class="total-info">
                <span style="font-size:1.2em;margin-right:20px;">总价</span>
                <span style="margin:0 30px;">卖单 <b style="color:#1976d2">${totalSell}</b></span>
                <span style="margin:0 30px;">买单 <b style="color:#43a047">${totalBuy}</b></span>
                <span style="margin:0 30px;">中位 <b style="color:#ffb300">${totalMiddle}</b></span>
            </div>
        `;
    }
    // 如果是伊甸币，显示500个一组的价格
    if (data[0].item_name === "伊甸币") {
        const buy500 = formatPrice(data[0].max_buy_price * 500);
        const sell500 = formatPrice(data[0].min_sell_price * 500);
        const middle500 = formatPrice(data[0].middle_price * 500);
        
        infoHtml += `
            <div class="total-info">
                <span style="font-size:1.2em;margin-right:20px;">500个</span>
                <span style="margin:0 30px;">卖单 <b style="color:#1976d2">${sell500}</b></span>
                <span style="margin:0 30px;">买单 <b style="color:#43a047">${buy500}</b></span>
                <span style="margin:0 30px;">中位 <b style="color:#ffb300">${middle500}</b></span>
            </div>
        `;
    }

    document.getElementById('info-bar').innerHTML = infoHtml;
}

function updateTitleBar(data) {
    if (data.length === 1) {
        // 单个物品显示
        const iconUrl = data[0].icon_url || '';
        const itemName = data[0].item_name || '';
        document.getElementById('title-bar').innerHTML = 
            (iconUrl ? `<img src="${iconUrl}" style="width:48px;height:48px;vertical-align:middle;margin-right:10px;">` : '') +
            `<span style="font-size:36px;font-weight:bold;vertical-align:middle;">${itemName}</span>`;
    } else {
        // 多个物品显示
        document.getElementById('title-bar').innerHTML = 
            `<span style="font-size:36px;font-weight:bold;">搜索结果</span>`;
    }
}

function formatPrice(price) {
    return (typeof price === 'number') 
        ? price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) 
        : (price || '-');
} 