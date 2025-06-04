// 图表相关函数
let myChart = null;

function initChart() {
    myChart = echarts.init(document.getElementById('main'));
    window.addEventListener('resize', () => myChart.resize());
}

function updateChart(dates, highests, lowest) {
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
            axisPointer: { type: 'cross' }
        },
        xAxis: { data: dates },
        yAxis: {},
        series: [{
            name: '最高价',
            type: 'line',
            data: highests
        }, {
            name: '最低价',
            type: 'line',
            data: lowest
        }]
    };
    myChart.setOption(option);
}

function updateInfoBar(latest) {
    const buy = formatPrice(latest.max_buy_price);
    const sell = formatPrice(latest.min_sell_price);
    const middle = formatPrice(latest.middle_price);

    document.getElementById('info-bar').innerHTML = `
        <span style="margin:0 30px;">卖单 <b style="color:#1976d2">${sell}</b></span>
        <span style="margin:0 30px;">买单 <b style="color:#43a047">${buy}</b></span>
        <span style="margin:0 30px;">中位 <b style="color:#ffb300">${middle}</b></span>
    `;
}

function updateTitleBar(iconUrl, itemName) {
    document.getElementById('title-bar').innerHTML = 
        (iconUrl ? `<img src="${iconUrl}" style="width:48px;height:48px;vertical-align:middle;margin-right:10px;">` : '') +
        `<span style="font-size:36px;font-weight:bold;vertical-align:middle;">${itemName}</span>`;
}

function formatPrice(price) {
    return (typeof price === 'number') 
        ? price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) 
        : (price || '-');
} 