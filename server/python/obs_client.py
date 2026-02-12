"""
OBS WebSocket Client - 接收OBS画面流并转发到Web浏览器

依赖:
    pip install obs-websocket-py websocket-client numpy opencv-python

OBS配置:
    1. 安装 OBS Studio
    2. 安装 obs-websocket 插件 (v5.x版本)
    3. 工具 → WebSocket → 确认服务器端口 (默认4455)
    4. 配置来源为"窗口捕获"或"显示器捕获"
"""

import asyncio
import json
import base64
import numpy as np
import cv2
import websockets
from typing import Optional
from obswebsocket import obsws, requests

# 配置
OBS_HOST = "localhost"
OBS_PORT = 4455  # v5 API 默认端口 (旧版v4是4444)
OBS_PASSWORD = ""  # 如有密码则填写

WEBSOCKET_HOST = "0.0.0.0"
WEBSOCKET_PORT = 8765
JPEG_QUALITY = 85

# 区域配置
CROP_REGION = {
    "left": 0,
    "top": 0,
    "width": 200,
    "height": 200
}


class OBSCapture:
    """OBS捕获器"""
    
    def __init__(self, region: dict = None):
        self.region = region or CROP_REGION
        self.clients = set()
        self.running = False
        self.ws = None
        self.obs_connected = False
        self.frame_count = 0
        self.last_fps_time = 0
        self.fps = 0
        
    def connect(self) -> bool:
        """连接OBS"""
        try:
            print(f"连接OBS: ws://{OBS_HOST}:{OBS_PORT}...")
            self.ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
            self.ws.connect()
            self.obs_connected = True
            print("✓ 已连接OBS")
            
            # 测试连接
            version = self.ws.call(requests.GetVersion())
            print(f"  OBS版本: {version.getObsStudioVersion()}")
            
            return True
        except Exception as e:
            print(f"✗ 连接OBS失败: {e}")
            print("\n请检查:")
            print("  1. OBS是否运行")
            print("  2. obs-websocket插件是否安装")
            print(f"  3. WebSocket端口是否为{OBS_PORT}")
            return False
    
    async def capture_frame(self) -> Optional[bytes]:
        """获取一帧"""
        if not self.obs_connected:
            return None
        
        try:
            # 获取截图 (使用v5 API)
            result = self.ws.call(requests.GetSourceScreenshot(
                sourceName="场景",  # 修改为你的来源名称
                imageFormat="jpeg",
                imageWidth=320,
                imageHeight=240
            ))
            
            if result and hasattr(result, 'imageData'):
                return base64.b64decode(result.imageData)
                
        except Exception as e:
            # 连接可能断开
            if "not connected" in str(e).lower():
                self.obs_connected = False
            # 可能是来源名称错误，尝试通用方式
            try:
                result = self.ws.call(requests.GetSourceScreenshot(
                    imageFormat="jpeg",
                    imageWidth=320,
                    imageHeight=240
                ))
                if result and hasattr(result, 'imageData'):
                    return base64.b64decode(result.imageData)
            except:
                pass
        
        return None
    
    async def broadcast(self, data: bytes):
        """广播"""
        if self.clients:
            await asyncio.gather(
                *[client.send(data) for client in self.clients.copy()],
                return_exceptions=True
            )
            self.clients = {c for c in self.clients if c.open}
    
    async def handler(self, websocket):
        """Web客户端处理"""
        self.clients.add(websocket)
        print(f"客户端连接: {websocket.remote_address}")
        try:
            async for message in websocket:
                if isinstance(message, str):
                    try:
                        cmd = json.loads(message)
                        if cmd.get("type") == "region":
                            self.region.update(cmd.get("region", {}))
                        elif cmd.get("type") == "ping":
                            await websocket.send(json.dumps({"type": "pong"}))
                    except:
                        pass
        finally:
            self.clients.discard(websocket)
    
    async def start_server(self):
        """启动服务器"""
        self.running = True
        async with websockets.serve(self.handler, WEBSOCKET_HOST, WEBSOCKET_PORT):
            print(f"\n🚀 Web服务器启动: ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
            print(f"📺 浏览器访问: http://localhost:{WEBSOCKET_PORT-8765+80} (如8765→8080)")
            await asyncio.Future()
    
    async def stream_loop(self, interval: float = 0.1):
        """流循环"""
        import time
        while self.running:
            try:
                frame = await self.capture_frame()
                if frame and self.clients:
                    await self.broadcast(frame)
                    self.frame_count += 1
                    
                    # FPS统计
                    now = time.time()
                    if now - self.last_fps_time >= 1.0:
                        self.fps = self.frame_count
                        self.frame_count = 0
                        self.last_fps_time = now
                        print(f"FPS: {self.fps}")
                
                await asyncio.sleep(interval)
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(1)
    
    def stop(self):
        self.running = False
        if self.ws:
            self.ws.disconnect()


async def main():
    """主入口"""
    import time
    
    capture = OBSCapture()
    
    # 连接OBS
    if not capture.connect():
        return
    
    try:
        await asyncio.gather(
            capture.start_server(),
            capture.stream_loop(interval=0.1)  # 10 FPS
        )
    except KeyboardInterrupt:
        print("\n停止...")
        capture.stop()


if __name__ == "__main__":
    asyncio.run(main())
