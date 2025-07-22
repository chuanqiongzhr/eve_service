import requests
import os

def download_echarts():
    # 创建目录（如果不存在）
    os.makedirs('static/js', exist_ok=True)
    
    # 下载 ECharts（使用 bootcdn）
    url = 'https://cdn.bootcdn.net/ajax/libs/echarts/5.4.3/echarts.min.js'
    response = requests.get(url)
    
    if response.status_code == 200:
        # 保存文件
        with open('static/js/echarts.min.js', 'wb') as f:
            f.write(response.content)
        print('ECharts 下载成功！')
    else:
        print(f'下载失败，状态码：{response.status_code}')

if __name__ == '__main__':
    download_echarts() 