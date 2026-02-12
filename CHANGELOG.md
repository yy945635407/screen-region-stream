# Screen Region Stream - 开发追踪

## v0.3.0 (2026-02-12) - OBS 方案

### 完成 ✅
- [x] **切换到 OBS 方案**
  - [x] obs-websocket-py 客户端
  - [x] 自动重连
  - [x] 浏览器接收端适配
- [x] README 文档更新
- [x] 依赖 requirements.txt 更新

### 关键变更

**原因**：Python直接调用DXGI困难，MSS无法捕获游戏。

**方案**：OBS Studio + obs-websocket
- OBS解决所有游戏兼容性问题
- Python只负责转发
- 零反作弊拦截

## v0.2.0 (2026-02-12)
- DXGI 捕获框架（理论支持）
- 自动回退到 MSS

## v0.1.0 (2026-02-12)
- 初始版本（MSS基础框架）
