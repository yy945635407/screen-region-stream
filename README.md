# Screen Region Stream

将 Windows 屏幕上任意区域以低延迟实时传输到浏览器。

> **游戏投屏最佳方案**：基于 OBS Studio + obs-websocket

## 典型用途

- 🎮 游戏小地图/雷达投屏（CS2, Valorant, Apex等）
- 📊 监控面板投屏
- 📺 视频/直播流传输
- 🖥️ 远程屏幕监控

## 为什么用 OBS？

```
直接捕获 ──────✗ 反作弊拦截 / GDI限制
OBS捕获 ──────✓ 完美兼容所有游戏 / 零兼容问题
```

**优势**：
- ✅ 完美兼容所有游戏（包括有反作弊保护的）
- ✅ 支持任意区域裁剪
- ✅ 社区成熟，稳定可靠
- ✅ 低延迟（可配置）

## 快速开始

### 1. 安装依赖

```bash
cd server/python
pip install -r requirements.txt
```

### 2. 配置 OBS

1. 下载并安装 [OBS Studio](https://obsproject.com/)
2. 安装 [obs-websocket 插件](https://github.com/obsproject/obs-websocket/releases)
3. 打开 OBS，添加"显示器捕获"或"窗口捕获"
4. 工具 → WebSocket → 确认服务器端口为 4444

### 3. 启动捕获服务

```bash
python obs_client.py
```

### 4. 打开浏览器

访问 `http://localhost:8765`

## 项目结构

```
screen-region-stream/
├── server/python/
│   ├── obs_client.py      # OBS WebSocket客户端
│   ├── capture.py         # 通用捕获（旧版MSS方案）
│   └── requirements.txt   # 依赖
├── web/
│   ├── index.html         # 接收页面
│   └── app.js             # WebSocket客户端
└── docs/
```

## 依赖

```txt
obs-websocket-py>=1.6.0
websocket-client>=1.6.0
numpy>=1.24.0
opencv-python>=4.8.0
websockets>=12.0
```

## 配置说明

编辑 `obs_client.py` 中的配置：

```python
OBS_HOST = "localhost"
OBS_PORT = 4444
OBS_PASSWORD = ""  # 如有密码

WEBSOCKET_HOST = "0.0.0.0"
WEBSOCKET_PORT = 8765
```

## 延迟优化

| 配置 | 效果 |
|-----|------|
| 减小截图尺寸 | 降低带宽和延迟 |
| 调整OBS输出编码 | NVENC/QuickSync最优 |
| 局域网传输 | WiFi可能有不稳定 |

## 故障排除

**无法连接OBS？**
- 检查OBS是否运行
- 检查obs-websocket插件是否安装
- 确认端口4444未被占用

**游戏画面黑屏？**
- 在OBS中重新添加捕获源
- 尝试"窗口捕获"而非"显示器捕获"
- 以管理员运行OBS

**延迟太高？**
- 减小截图尺寸（imageWidth/imageHeight）
- 使用有线网络
- 关闭不必要的后台程序

## TODO

- [x] OBS WebSocket 客户端
- [x] 浏览器接收端
- [ ] 自动重连
- [ ] 多来源支持
- [ ] 延迟测试与优化

## 许可证

MIT
