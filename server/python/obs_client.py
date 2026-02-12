"""
OBS WebSocket Client + HTTP Server - 接收OBS画面流并转发到Web浏览器

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
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional
import websockets
from obswebsocket import obsws, requests

# ============== 配置 ==============
OBS_HOST = "localhost"
OBS_PORT = 4455  # v5 API 默认端口
OBS_PASSWORD = ""

HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8080  # 浏览器访问这个端口

WEBSOCKET_PORT = 8765  # 内部WebSocket端口

CROP_REGION = {
    "left": 0,
    "top": 0,
    "width": 200,
    "height": 200
}

# ============== HTTP 服务器 ==============
class QuietHTTPHandler(SimpleHTTPRequestHandler):
    """静默HTTP处理器"""
    def log_message(self, format, *args):
        pass  # 抑制日志

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.path = '/web/index.html'
        return SimpleHTTPRequestHandler.do_GET(self)


def start_http_server():
    """启动HTTP服务器"""
    # obs_client.py 在 server/python/，项目根目录在上一级的上一级
    server_python_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(server_python_dir))  # server/python/../../
    web_dir = os.path.join(project_root, 'web')
    
    print(f"📁 项目目录: {project_root}")
    print(f"📁 Web目录: {web_dir}")
    
    if not os.path.exists(web_dir):
        print(f"❌ Web目录不存在: {web_dir}")
        return
        
    os.chdir(web_dir)
    server = HTTPServer((HTTP_HOST, HTTP_PORT), QuietHTTPHandler)
    print(f"📺 HTTP服务器: http://localhost:{HTTP_PORT}")
    server.serve_forever()


# ============== OBS 捕获 ==============
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
            print(f"🔌 连接OBS: ws://{OBS_HOST}:{OBS_PORT}...")
            self.ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
            self.ws.connect()
            self.obs_connected = True
            print(f"✅ 已连接OBS")
            
            version = self.ws.call(requests.GetVersion())
            print(f"  OBS版本: {version.getObsVersion()}")
            
            return True
        except Exception as e:
            print(f"❌ 连接OBS失败: {e}")
            return False
    
    async def capture_frame(self) -> Optional[bytes]:
        """获取一帧"""
        if not self.obs_connected:
            return None
        
        try:
            # 获取截图
            result = self.ws.call(requests.GetSourceScreenshot(
                sourceName="场景",
                imageFormat="jpeg",
                imageWidth=320,
                imageHeight=240
            ))
            
            if result and hasattr(result, 'imageData'):
                return base64.b64decode(result.imageData)
                
        except Exception as e:
            if "not connected" in str(e).lower():
                self.obs_connected = False
            try:
                # 尝试不使用来源名称
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
        print(f"🌐 客户端连接: {websocket.remote_address}")
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
    
    async def start_websocket_server(self):
        """启动WebSocket服务器"""
        self.running = True
        async with websockets.serve(self.handler, HTTP_HOST, WEBSOCKET_PORT):
            print(f"🚀 WebSocket服务器: ws://{HTTP_HOST}:{WEBSOCKET_PORT}")
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
                    
                    now = time.time()
                    if now - self.last_fps_time >= 1.0:
                        self.fps = self.frame_count
                        self.frame_count = 0
                        self.last_fps_time = now
                        print(f"📊 FPS: {self.fps}")
                
                await asyncio.sleep(interval)
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(1)
    
    def stop(self):
        self.running = False
        if self.ws:
            self.ws.disconnect()


# ============== 主入口 ==============
async def main():
    import time
    
    capture = OBSCapture()
    
    # 连接OBS
    if not capture.connect():
        return
    
    # 启动HTTP服务器（后台线程）
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    try:
        await asyncio.gather(
            capture.start_websocket_server(),
            capture.stream_loop(interval=0.1)
        )
    except KeyboardInterrupt:
        print("\n停止...")
        capture.stop()


if __name__ == "__main__":
    print("=" * 50)
    print("🎮 Screen Region Stream - OBS投屏方案")
    print("=" * 50)
    asyncio.run(main())
