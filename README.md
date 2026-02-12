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

## 第一步：安装依赖

```bash
cd server/python
pip install -r requirements.txt
```

## 第二步：安装 OBS Studio

1. 下载地址：https://obsproject.com/
2. 安装并打开 OBS Studio

## 第三步：安装 obs-websocket 插件

**⚠️ 必须安装插件，否则程序无法连接OBS**

1. 下载地址：https://github.com/obsproject/obs-websocket/releases
2. 下载对应版本的插件（根据你的OBS版本）
   - OBS 28+: 用 5.x.x 版本
   - OBS 27及以下: 用 4.x.x 版本
3. 解压到 OBS 安装目录的 `obs-plugins` 文件夹

**验证安装：**
- 打开 OBS
- 菜单栏 → 工具 → WebSocket
- ✅ 看到 "Server ... connected" 表示成功

## 第四步：配置 OBS

1. **添加捕获源**
   - 源 → + → "显示器捕获" 或 "窗口捕获"
   - 选择要捕获的显示器或游戏窗口
   - 💡 游戏雷达建议用"窗口捕获"，只捕获游戏窗口

2. **配置 WebSocket（如果需要）**
   - 工具 → WebSocket
   - 端口号：
     - v5 API: 默认 4455 ✅ 推荐
     - v4 API: 默认 4444
   - 如果设置了密码，记下来

## 第五步：启动服务

```bash
cd server/python
python obs_client.py
```

**成功会看到：**
```
连接OBS: ws://localhost:4455...
✓ 已连接OBS
  OBS版本: xx.x.x

🚀 Web服务器启动: ws://0.0.0.0:8765
📺 浏览器访问: http://localhost:8080
```

## 第六步：打开浏览器

访问 http://localhost:8080

## 常见问题

### Q: pip install obs-websocket-py 报错？

A: 尝试以下命令：
```bash
pip install obs-websocket-py --force-reinstall
```

### Q: 连接OBS失败？

A: 依次检查：
1. OBS是否运行？
2. obs-websocket插件是否安装？（工具 → WebSocket）
3. 端口是否正确？（v5=4455, v4=4444）
4. 防火墙是否拦截？

### Q: 看不到游戏画面？

A: 
1. OBS中重新添加捕获源
2. 尝试"窗口捕获"而非"显示器捕获"
3. 以管理员身份运行 OBS

### Q: 延迟太高？

A: 
- 减小截图尺寸（修改代码中的 imageWidth）
- 使用有线网络
- 关闭不必要的后台程序

## 依赖

```
obs-websocket-py
websocket-client
numpy
opencv-python
websockets
```

## 项目结构

```
screen-region-stream/
├── server/python/
│   ├── obs_client.py      # OBS WebSocket客户端 ✅ 推荐
│   ├── capture.py         # 通用捕获（旧版MSS方案）
│   └── requirements.txt   # 依赖
├── web/
│   ├── index.html         # 接收页面
│   └── app.js             # WebSocket客户端
└── README.md              # 本文档
```

## TODO

- [x] OBS WebSocket 客户端
- [x] 浏览器接收端
- [ ] 自动重连
- [ ] 多来源支持
- [ ] 延迟测试与优化

## 许可证

MIT
