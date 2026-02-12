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
HTTP_PORT = 8080
WEBSOCKET_PORT = 8765

# 来源名称 - 根据你的OBS设置修改
SOURCE_NAME = ""  # 空表示获取当前活动输出

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
    
    print(f"📁 Web目录: {web_dir}")
    
    if not os.path.exists(web_dir):
        print(f"❌ Web目录不存在")
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
        
    def connect(self) -> bool:
        try:
            print(f"🔌 连接OBS: ws://{OBS_HOST}:{OBS_PORT}...")
            self.ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
            self.ws.connect()
            self.obs_connected = True
            print(f"✅ 已连接OBS")
            
            # 获取版本信息
            try:
                version = self.ws.call(requests.GetVersion())
                print(f"  OBS版本: {version.getObsVersion()}")
            except:
                print(f"  (无法获取版本)")
            
            return True
        except Exception as e:
            print(f"❌ 连接OBS失败: {e}")
            return False
    
    def list_sources(self):
        """列出所有来源"""
        try:
            print("\n📋 可用来源:")
            result = self.ws.call(requests.GetSourcesList())
            
            # 解析返回结果
            sources = []
            if hasattr(result, 'sources'):
                sources = result.sources
            elif hasattr(result, '__dict__'):
                for key, value in result.__dict__.items():
                    if isinstance(value, list):
                        sources.extend(value)
            
            # 去重
            seen = set()
            unique_sources = []
            for s in sources:
                name = s.get('name', str(s)) if isinstance(s, dict) else str(s)
                if name not in seen:
                    seen.add(name)
                    unique_sources.append(name)
            
            for i, name in enumerate(unique_sources[:30]):
                print(f"  {i+1}. {name}")
            print()
            return unique_sources
        except Exception as e:
            print(f"❌ 获取来源列表失败: {e}")
            return []
    
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
            
            # v5 API: imageData 在响应中
            if hasattr(result, 'imageData') and result.imageData:
                return base64.b64decode(result.imageData)
            
            # 尝试其他属性名
            if hasattr(result, 'image_data'):
                return base64.b64decode(result.image_data)
            
            return None
            
        except Exception as e:
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
        print(f"🌐 客户端连接: {websocket.remote_address}")
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
        async with websockets.serve(self.handler, HTTP_HOST, WEBSOCKET_PORT):
            print(f"🚀 WebSocket服务器: ws://{HTTP_HOST}:{WEBSOCKET_PORT}")
            await asyncio.Future()
    
    async def stream_loop(self, interval: float = 0.1):
        """主循环"""
        import time
        
        # 首先列出来源
        if self.obs_connected:
            sources = self.list_sources()
            if SOURCE_NAME:
                print(f"📷 使用指定来源: {SOURCE_NAME}")
        
        # 尝试获取截图
        test_count = 0
        success_count = 0
        
        while self.running:
            try:
                frame = self.get_screenshot(SOURCE_NAME)
                
                if frame:
                    success_count += 1
                    if self.clients:
                        await self.broadcast(frame)
                else:
                    test_count += 1
                    if test_count <= 3:
                        print(f"⚠️ 无法获取截图 (尝试 {test_count}/3)")
                        if test_count == 1:
                            print("💡 提示: 在OBS中添加一个'显示器捕获'来源")
                    
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
