# Screen Region Stream

将 Windows 屏幕上任意区域以低延迟实时传输到浏览器。

## 典型用途

- 🎮 游戏小地图/雷达投屏
- 📊 监控面板投屏
- 📺 视频/直播流传输
- 🖥️ 远程屏幕监控

## 架构概览

```
┌─────────────┐    WebSocket    ┌─────────────┐
│   Windows   │ ───────────────▶ │   浏览器    │
│  区域采集   │     (JPEG流)     │  (接收显示) │
└─────────────┘                  └─────────────┘
```

## 核心特性

- ✅ 低延迟视频流传输
- ✅ 可配置区域裁剪
- ✅ WebSocket 实时传输
- ✅ 跨平台浏览器支持
- ✅ 局域网/跨网络支持
- 🔄 移动端优化
- 🔄 多区域同时传输

## 快速开始

### 1. 安装依赖

```bash
cd server/python
pip install -r requirements.txt
```

### 2. 运行采集服务

```bash
python capture.py
```

### 3. 打开浏览器

访问 `http://localhost:8765`

## 项目结构

```
screen-region-stream/
├── server/
│   ├── python/          # Python采集端
│   │   ├── capture.py   # 屏幕捕获 + WebSocket服务
│   │   └── requirements.txt
│   └── go/              # Go采集端（可选高性能方案）
├── web/                 # Web接收端
│   ├── index.html       # 主页面
│   ├── style.css        # 样式
│   └── app.js           # WebSocket客户端
└── docs/                # 文档
```

## 技术栈

- **采集端**: Python + MSS + OpenCV
- **传输**: WebSocket (JPEG二进制流)
- **接收端**: HTML5 + Canvas

## 配置说明

编辑 `capture.py` 中的 `RADAR_REGION` 自定义捕获区域：

```python
RADAR_REGION = {
    "left": 0,      # 左上角X坐标
    "top": 0,       # 左上角Y坐标
    "width": 200,   # 区域宽度
    "height": 200  # 区域高度
}
```

或在浏览器中点击"校准区域"手动选择。

## TODO

- [x] 基础屏幕捕获
- [x] WebSocket 传输
- [x] 浏览器接收显示
- [ ] 延迟测试与优化 (<100ms目标)
- [ ] 自动区域识别
- [ ] 移动端适配
- [ ] 信令服务器（跨网络传输）
- [ ] 多区域支持

## 许可证

MIT
