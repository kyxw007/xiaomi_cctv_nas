# 小米摄像头 NAS 视频监控系统

一个基于 Python Flask 后端和 React 前端的视频监控系统，支持通过 WebDAV 协议访问存储在 NAS 上的小米摄像头录像文件，并提供基于时间的视频播放功能。

## 功能特性

- 🎥 **多摄像头支持**: 支持多个小米摄像头的视频管理
- 📅 **时间导航**: 基于时间轴的视频播放，支持按日期/时间快速跳转
- ⚡ **实时流媒体**: 使用 FFmpeg 进行实时视频转码和流媒体传输
- 🌐 **WebDAV 集成**: 直接从 NAS 存储读取视频文件
- 🎛️ **播放控制**: 支持多种播放速度（0.5x, 1x, 2x, 4x）
- 📱 **响应式设计**: 基于 Material-UI 的现代化用户界面
- 🔍 **智能文件匹配**: 根据时间自动匹配对应的视频文件

## 系统架构

```
┌─────────────────┐    HTTP/WebDAV    ┌─────────────────┐
│   React 前端    │ ◄──────────────► │  Flask 后端     │
│                 │                   │                 │
│ - 视频播放器    │                   │ - WebDAV 客户端 │
│ - 时间导航      │                   │ - FFmpeg 集成   │
│ - 摄像头列表    │                   │ - 视频流处理    │
└─────────────────┘                   └─────────────────┘
                                               │
                                               │ WebDAV
                                               ▼
                                      ┌─────────────────┐
                                      │   NAS 存储      │
                                      │                 │
                                      │ /CCTV/          │
                                      │ ├── Camera_01/  │
                                      │ ├── Camera_02/  │
                                      │ └── ...         │
                                      └─────────────────┘
```

## 技术栈

### 后端
- **Python 3.8+**
- **Flask**: Web 框架
- **Flask-CORS**: 跨域资源共享
- **webdav3**: WebDAV 客户端库
- **requests**: HTTP 请求库
- **FFmpeg**: 视频处理和转码

### 前端
- **React 18**: 用户界面框架
- **Material-UI (MUI)**: UI 组件库
- **React Router**: 路由管理
- **Day.js**: 日期时间处理

## 安装部署

### 环境要求

- Python 3.8 或更高版本
- Node.js 16 或更高版本
- FFmpeg（用于视频处理）
- 支持 WebDAV 的 NAS 设备

### 后端安装

1. **克隆项目**
```bash
git clone <repository-url>
cd xiaomi_cctv_nas
```

2. **创建虚拟环境**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **安装 FFmpeg**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# Windows
# 下载 FFmpeg 并添加到 PATH
```

5. **配置设置**

编辑 `backend/app.py` 中的配置：
```python
# WebDAV 服务器配置
WEBDAV_SERVER = "https://your-nas-server.com:5008"
WEBDAV_USERNAME = "your-username"
WEBDAV_PASSWORD = "your-password"

# 摄像头名称映射
CAM_NAMES = {
    'XiaomiCamera_00_78DF72F2BD91': '主卧',
    'XiaomiCamera_01_78DF72F2F3CE': '客厅',
    # 添加更多摄像头...
}
```

6. **启动后端服务**
```bash
python app.py
```

后端服务将在 `http://localhost:5001` 启动。

### 前端安装

1. **进入前端目录**
```bash
cd frontend
```

2. **安装依赖**
```bash
npm install
```

3. **配置 API 地址**

编辑 `frontend/src/config.js`：
```javascript
const config = {
  API_BASE_URL: 'http://localhost:5001'
};
```

4. **启动前端服务**
```bash
npm start
```

前端服务将在 `http://localhost:3000` 启动。

## 使用说明

### 视频文件命名规范

系统要求视频文件按以下格式命名：
```
00_YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4
```

例如：
- `00_20250613133147_20250613133705.mp4`
  - 开始时间：2025年6月13日 13:31:47
  - 结束时间：2025年6月13日 13:37:05

### 目录结构

NAS 上的目录结构应如下：
```
/CCTV/
├── XiaomiCamera_00_78DF72F2BD91/
│   ├── 00_20250613133147_20250613133705.mp4
│   ├── 00_20250613140000_20250613143000.mp4
│   └── ...
├── XiaomiCamera_01_78DF72F2F3CE/
│   ├── 00_20250613133200_20250613134500.mp4
│   └── ...
└── ...
```

### 基本操作

1. **选择摄像头**: 在首页选择要查看的摄像头
2. **时间导航**: 使用日期导航按钮或时间轴选择播放时间
3. **播放控制**: 点击播放/暂停按钮控制视频播放
4. **调整速度**: 使用速度选择器调整播放速度
5. **时间跳转**: 拖动时间轴快速跳转到指定时间

## API 接口

### 获取摄像头列表
```http
GET /api/cameras
```

### 视频流播放
```http
GET /api/video/stream?start_time=YYYY-MM-DD HH:mm:ss&video_dir=/CCTV/CameraName&playback_rate=1
```

参数说明：
- `start_time`: 开始播放时间
- `video_dir`: 摄像头目录路径
- `playback_rate`: 播放速率（0.5, 1, 2, 4）

## 配置说明

### WebDAV 配置

在 `backend/webdav_client.py` 中配置 WebDAV 连接：

```python
class WebDAVClient:
    def __init__(self, 
                 server_url: str = "https://your-nas-server.com:5008",
                 username: str = "your-username",
                 password: str = "your-password"):
```

### FFmpeg 参数调优

在 `backend/app.py` 中的 FFmpeg 命令可以根据需要调整：

```python
cmd = [
    'ffmpeg',
    '-headers', 'User-Agent: FFmpeg',
    '-i', webdav_url,
    '-c:v', 'libx264',      # 视频编码器
    '-c:a', 'aac',          # 音频编码器
    '-preset', 'ultrafast', # 编码速度预设
    '-crf', '23',           # 质量参数
    # ... 其他参数
]
```

## 故障排除

### 常见问题

1. **视频无法播放**
   - 检查 FFmpeg 是否正确安装
   - 确认 WebDAV 连接配置正确
   - 检查视频文件命名格式

2. **时间跳转不准确**
   - 确认视频文件名中的时间戳正确
   - 检查系统时间是否同步

3. **连接超时**
   - 检查网络连接
   - 调整 WebDAV 超时设置
   - 确认 NAS 服务正常运行

### 日志调试

启用详细日志：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

查看 FFmpeg 输出：
```python
cmd.extend(['-loglevel', 'info'])
```

## 性能优化

### 后端优化
- 使用连接池管理 WebDAV 连接
- 实现视频文件缓存机制
- 优化 FFmpeg 参数以平衡质量和性能

### 前端优化
- 实现视频预加载
- 添加播放进度缓存
- 优化时间轴渲染性能

## 安全考虑

- 使用 HTTPS 连接 WebDAV 服务器
- 实现用户认证和授权
- 限制 API 访问频率
- 定期更新依赖包

## 开发计划

- [ ] 添加用户认证系统
- [ ] 支持多种视频格式
- [ ] 实现视频下载功能
- [ ] 添加移动端适配
- [ ] 支持实时监控流
- [ ] 添加视频分析功能

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 联系方式

如有问题或建议，请通过以下方式联系：

- 项目 Issues: [GitHub Issues](https://github.com/your-repo/issues)
- 邮箱: your-email@example.com

---

**注意**: 本项目仅供学习和个人使用，请确保遵守相关法律法规和隐私政策。