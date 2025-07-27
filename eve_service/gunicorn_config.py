import multiprocessing
import os

# 设置固定的SECRET_KEY
os.environ['SECRET_KEY'] = 'b7c820226a1891011f53889d5e0d1295bbdd4b0d1faa12a1757cbd2644339ea4'

# 绑定的地址和端口
bind = "0.0.0.0:5000"

# 工作进程数
# workers = multiprocessing.cpu_count() * 2 + 1
workers = 1
# 工作模式
worker_class = "sync"

# 超时时间
timeout = 120

# 最大请求数
max_requests = 1000
max_requests_jitter = 50

# 访问日志和错误日志
accesslog = "/var/www/eve_service/eve_service/logs/access.log"
errorlog = "/var/www/eve_service/eve_service/logs/error.log"
loglevel = "info"

# 进程名称
proc_name = "eve_service"

# 守护进程模式
daemon = False