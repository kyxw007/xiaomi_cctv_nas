# 构建后端
FROM python:3.11-slim

# 设置非交互式安装
ENV DEBIAN_FRONTEND=noninteractive

# 设置时区为上海
ENV TZ=Asia/Shanghai

# 安装 ffmpeg、gcc 和时区数据
RUN apt-get update && apt-get install -y ffmpeg gcc tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制后端文件
COPY backend/app.py ./backend/
COPY backend/webdav_client.py ./backend/
COPY backend/cfg.json ./backend/
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置环境变量
ENV FLASK_APP=backend/app.py
ENV FLASK_ENV=production

# 暴露端口
EXPOSE 5001

# 启动应用，增加超时时间和 worker 配置
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--timeout", "300", "--worker-connections", "1000", "--max-requests", "1000", "--max-requests-jitter", "100", "backend.app:app"] 