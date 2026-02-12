# Screen Region Stream - 开发追踪

## v0.2.0 (2026-02-12) - DXGI 改进

### 完成 ✅
- [x] DXGI 捕获框架（理论支持）
- [x] 自动回退到 MSS
- [x] WebSocket 传输

### 待实现 🔄
- [ ] **DXGI 完整实现**（Python直接调用困难）
  - 原因：DXGI需要D3D11配合，Python ctypes调用复杂
  - 方案A：使用 OpenCV + Windows Graphics Capture (Win11)
  - 方案B：改用 Go/C++ 实现捕获端
  - 方案C：复用 OBS 的捕获能力（推荐）

### 推荐：OBS 方案

如果DXGI方案在Python中难以实现，最佳替代方案：

```bash
# 1. 安装 OBS Studio
# 2. 安装 obs-websocket 插件
# 3. 配置来源为"显示器捕获"或"窗口捕获"
# 4. 启动 obs-websocket
# 5. 用 Python 连接 ws://localhost:4444 获取画面
```

**优势**：
- OBS 已经解决了所有游戏兼容性问题
- 支持所有游戏，包括有反作弊保护的
- 可配置区域裁剪
- 社区成熟

### 待办
- [ ] 评估 OBS 集成方案
- [ ] 或切换到 Go/C++ 实现
- [ ] 延迟测试与优化

## v0.1.0 (2026-02-12)
- 初始版本（MSS基础框架）
