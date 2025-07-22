import multiprocessing

# 绑定的地址和端口
bind = "0.0.0.0:5000"

# 工作进程数
workers = multiprocessing.cpu_count() * 2 + 1

# 工作模式
worker_class = "sync"

# 超时时间
timeout = 120

# 最大请求数
max_requests = 1000
max_requests_jitter = 50

# 访问日志和错误日志
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"

# 进程名称
proc_name = "eve_service"

# 守护进程模式
daemon = False 