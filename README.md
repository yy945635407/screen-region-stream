# CS2 Radar Stream

将 CS2 游戏中的雷达地图以低延迟、高分辨率传输到移动端浏览器。

## 架构概览

```
┌─────────────┐    WebSocket    ┌─────────────┐
│   Windows   │ ───────────────▶ │   浏览器    │
│  Python采集 │     (JPEG流)     │  (接收显示) │
└─────────────┘                  └─────────────┘
```

## 核心特性

- ✅ 低延迟视频流传输
- ✅ 区域裁剪（只捕获雷达区域）
- ✅ WebSocket 实时传输
- ✅ 跨平台浏览器支持
- 🔄 移动端适配（后续）
- 🔄 手环支持（后续）

## 快速开始

### 1. 安装依赖

```bash
cd server/python
pip install -r requirements.txt
```

### 2. 运行采集服务

```bash
python radar_capture.py
```

### 3. 打开浏览器

访问 `http://localhost:8080`

## 项目结构

```
cs2-radar-stream/
├── server/
│   ├── python/          # Python采集端
│   │   ├── capture.py   # 屏幕捕获
│   │   ├── server.py    # WebSocket服务
│   │   └── requirements.txt
│   └── go/              # Go采集端（可选高性能方案）
├── web/                  # Web接收端
│   ├── index.html       # 主页面
│   ├── style.css        # 样式
│   └── app.js           # WebSocket客户端
└── docs/                 # 文档
```

## 技术栈

- **采集端**: Python + DXGI / OpenCV
- **传输**: WebSocket (JPEG二进制流)
- **接收端**: HTML5 + Canvas

## TODO

- [ ] 基础屏幕捕获
- [ ] 雷达区域识别与裁剪
- [ ] WebSocket 传输
- [ ] 浏览器接收显示
- [ ] 延迟测试与优化
- [ ] 移动端适配

## 许可证

MIT
