# 监控视频查看系统

这是一个基于 Flask 和 React 的监控视频查看系统，支持响应式设计，可以在手机、平板和电脑上访问。

## 功能特点

- 前后端分离架构
- 响应式设计，支持多设备访问
- 视频列表展示
- 视频播放功能
- 暗色主题界面

## 技术栈

### 后端
- Flask
- Flask-CORS
- Python 3.x

### 前端
- React
- Material-UI
- Axios
- React Router

## 安装和运行

### 后端设置

1. 创建并激活虚拟环境（可选）：
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 创建视频目录：
```bash
mkdir videos
```

4. 运行后端服务：
```bash
cd backend
python app.py
```

### 前端设置

1. 安装依赖：
```bash
cd frontend
npm install
```

2. 运行开发服务器：
```bash
npm start
```

## 使用说明

1. 将监控视频文件放入 `videos` 目录
2. 访问 http://localhost:3000 查看视频列表
3. 点击视频卡片进入播放页面

## 注意事项

- 确保视频文件格式为 mp4、avi 或 mkv
- 后端服务默认运行在 http://localhost:5001
- 前端开发服务器运行在 http://localhost:3000 