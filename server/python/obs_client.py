"""
OBS WebSocket Client - 接收OBS画面流并转发到Web浏览器
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
OBS_PORT = 4455
OBS_PASSWORD = ""

HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8080
WEBSOCKET_PORT = 8765

# 尝试的来源名称列表
SOURCE_NAMES = [
    "",              # 空=当前活动来源
    "场景",          # Scene
    "Scene", 
    "屏幕捕获",      # 用户实际使用的名称
    "显示器捕获",    # Display Capture
    "Display Capture",
    "窗口捕获",      # Window Capture
    "Window Capture",
    "游戏捕获",      # Game Capture
    "Game Capture",
    "浏览器",        # Browser
    "Browser",
]

# ============== HTTP 服务器 ==============
class QuietHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        server_python_dir = os.path.dirname(os.path.abspath(__file__))
        self.web_root = os.path.join(os.path.dirname(os.path.dirname(server_python_dir)), 'web')
        super().__init__(*args, directory=self.web_root, **kwargs)
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.path = '/index.html'
        return SimpleHTTPRequestHandler.do_GET(self)


def start_http_server():
    server_python_dir = os.path.dirname(os.path.abspath(__file__))
    web_dir = os.path.join(os.path.dirname(os.path.dirname(server_python_dir)), 'web')
    
    if not os.path.exists(web_dir):
        print(f"❌ Web目录不存在: {web_dir}")
        return
    
    original_cwd = os.getcwd()
    os.chdir(web_dir)
    
    try:
        server = HTTPServer((HTTP_HOST, HTTP_PORT), QuietHTTPHandler)
        print(f"📺 HTTP服务器: http://localhost:{HTTP_PORT}")
        server.serve_forever()
    finally:
        os.chdir(original_cwd)


# ============== OBS 捕获 ==============
class OBSCapture:
    def __init__(self):
        self.clients = set()
        self.running = False
        self.ws = None
        self.obs_connected = False
        self.working_source = None
    
    def connect(self) -> bool:
        try:
            print(f"🔌 连接OBS: ws://{OBS_HOST}:{OBS_PORT}...")
            self.ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
            self.ws.connect()
            self.obs_connected = True
            print(f"✅ 已连接OBS")
            
            try:
                version = self.ws.call(requests.GetVersion())
                print(f"  OBS版本: {version.getObsVersion()}")
            except:
                pass
            
            return True
        except Exception as e:
            print(f"❌ 连接OBS失败: {e}")
            return False
    
    def get_screenshot(self, source_name: str = "") -> Optional[bytes]:
        """获取截图"""
        if not self.obs_connected:
            return None
        
        try:
            kwargs = {
                'imageFormat': "jpeg",
                'imageWidth': 320,
                'imageHeight': 240
            }
            
            if source_name:
                kwargs['sourceName'] = source_name
            
            result = self.ws.call(requests.GetSourceScreenshot(**kwargs))
            
            # 尝试不同属性名
            for attr in ['imageData', 'image_data', 'data']:
                if hasattr(result, attr):
                    data = getattr(result, attr)
                    if data:
                        return base64.b64decode(data)
            
            return None
            
        except Exception as e:
            return None
    
    def find_working_source(self) -> Optional[str]:
        """查找可用的来源"""
        print("\n🔍 查找可用来源...")
        
        for name in SOURCE_NAMES:
            print(f"  尝试: '{name}'...", end=" ")
            frame = self.get_screenshot(name)
            if frame and len(frame) > 100:  # 确保不是空图片
                print(f"✅ 成功! ({len(frame)} bytes)")
                return name
            else:
                print("❌")
        
        print("❌ 未找到可用的来源")
        return None
    
    async def broadcast(self, data: bytes):
        if self.clients:
            await asyncio.gather(
                *[client.send(data) for client in self.clients.copy()],
                return_exceptions=True
            )
            self.clients = {c for c in self.clients if c.open}
    
    async def handler(self, websocket):
        self.clients.add(websocket)
        print(f"🌐 客户端: {websocket.remote_address}")
        try:
            async for message in websocket:
                if isinstance(message, str):
                    try:
                        cmd = json.loads(message)
                        if cmd.get("type") == "ping":
                            await websocket.send(json.dumps({"type": "pong"}))
                    except:
                        pass
        finally:
            self.clients.discard(websocket)
    
    async def start_websocket_server(self):
        self.running = True
        print(f"🚀 WebSocket: ws://{HTTP_HOST}:{WEBSOCKET_PORT}")
        async with websockets.serve(self.handler, HTTP_HOST, WEBSOCKET_PORT):
            await asyncio.Future()
    
    async def stream_loop(self, interval: float = 0.1):
        import time
        
        # 查找可用来源
        if self.obs_connected:
            self.working_source = self.find_working_source()
        
        tested = set()
        fps_count = 0
        last_time = time.time()
        
        while self.running:
            try:
                if self.working_source:
                    frame = self.get_screenshot(self.working_source)
                    
                    if frame and self.clients:
                        await self.broadcast(frame)
                        fps_count += 1
                        
                        # 每秒打印FPS
                        now = time.time()
                        if now - last_time >= 1.0:
                            print(f"📊 FPS: {fps_count}")
                            fps_count = 0
                            last_time = now
                else:
                    # 尝试重新检测
                    if len(tested) < len(SOURCE_NAMES):
                        for name in SOURCE_NAMES:
                            if name not in tested:
                                tested.add(name)
                                if self.get_screenshot(name):
                                    self.working_source = name
                                    print(f"✅ 找到来源: '{name}'")
                                    break
                    
                    await asyncio.sleep(1)
                
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
    print("=" * 50)
    print("🎮 Screen Region Stream - OBS投屏方案")
    print("=" * 50)
    
    capture = OBSCapture()
    
    if not capture.connect():
        return
    
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
    asyncio.run(main())
