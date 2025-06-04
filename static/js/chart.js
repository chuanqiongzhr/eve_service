// 图表相关函数
let myChart = null;

function initChart() {
    myChart = echarts.init(document.getElementById('main'));
    window.addEventListener('resize', () => myChart.resize());
}

function updateChart(data) {
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
            const priceMap = new Map(itemData.dates.map((date, index) => [date, itemData.highests[index]]));
            
            // 使用所有日期，如果某个日期没有数据则使用null
            const prices = allDates.map(date => priceMap.get(date) || null);
            
            series.push({
                name: itemName,
                type: 'line',
                data: prices,
                smooth: true,
                symbol: 'circle',
                symbolSize: 6,
                lineStyle: {
                    width: 2
                }
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
            symbol: 'none'
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
            axisPointer: { type: 'cross' },
            formatter: function(params) {
                let result = params[0].axisValue + '<br/>';
                params.forEach(param => {
                    if (param.value !== null) {
                        result += param.marker + ' ' + param.seriesName + ': ' + 
                            param.value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) + '<br/>';
                    }
                });
                return result;
            }
        },
        legend: {
            data: items.concat(data[0].max_buy_price_set ? ['一套总价'] : []),
            top: 30,
            type: 'scroll',
            pageButtonPosition: 'end'
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
                }
            }
        },
        yAxis: {
            type: 'value',
            name: '价格',
            axisLabel: {
                formatter: function(value) {
                    return value.toLocaleString();
                }
            }
        },
        series: series
    };
    myChart.setOption(option);
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
                <span style="font-size:1.2em;margin-right:20px;">一套总价</span>
                <span style="margin:0 30px;">卖单 <b style="color:#1976d2">${totalSell}</b></span>
                <span style="margin:0 30px;">买单 <b style="color:#43a047">${totalBuy}</b></span>
                <span style="margin:0 30px;">中位 <b style="color:#ffb300">${totalMiddle}</b></span>
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