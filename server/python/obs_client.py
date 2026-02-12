"""
OBS投屏服务器 - 简化版

工作原理：
1. OBS配置"虚拟摄像机"输出
2. Python通过HTTP接收画面并转发到WebSocket

如果obs-websocket的截图API不工作，这个版本先测试基本功能。
"""

import asyncio
import json
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional
import websockets
from obswebsocket import obsws, requests

# ============== 配置 ==============
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8080
WEBSOCKET_PORT = 8765

OBS_HOST = "localhost"
OBS_PORT = 4455


# ============== HTTP 服务器 ==============
class QuietHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        server_python_dir = os.path.dirname(os.path.abspath(__file__))
        self.web_root = os.path.join(os.path.dirname(os.path.dirname(server_python_dir)), 'web')
        super().__init__(*args, directory=self.web_root, **kwargs)
    
    def log_message(self, format, *args):
        pass


# ============== 主程序 ==============
class RadarServer:
    def __init__(self):
        self.clients = set()
        self.running = False
        self.ws = None
        self.connected = False
        self.fps = 0
    
    def connect_obs(self) -> bool:
        """连接OBS"""
        try:
            print(f"🔌 连接OBS: ws://{OBS_HOST}:{OBS_PORT}...")
            self.ws = obsws(OBS_HOST, OBS_PORT, "")
            self.ws.connect()
            self.connected = True
            print("✅ 已连接OBS\n")
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            print("\n请确保:")
            print("  1. OBS正在运行")
            print("  2. 已安装obs-websocket插件")
            print("  3. WebSocket服务器已启动 (工具 → WebSocket)\n")
            return False
    
    def try_screenshot(self, source_name: str) -> Optional[bytes]:
        """尝试截图"""
        try:
            result = self.ws.call(requests.GetSourceScreenshot(
                sourceName=source_name,
                imageFormat="jpeg",
                imageWidth=320,
                imageHeight=240
            ))
            
            # 检查返回
            if hasattr(result, 'imageData') and result.imageData:
                import base64
                return base64.b64decode(result.imageData)
            
        except Exception as e:
            print(f"  '{source_name}': {e}")
        
        return None
    
    def find_working_source(self) -> Optional[str]:
        """查找可截图的来源"""
        sources = ["屏幕捕获", "显示器捕获", "窗口捕获", "场景"]
        
        print("🔍 查找可用来源...\n")
        
        for source in sources:
            print(f"  尝试 '{source}'...", end=" ")
            frame = self.try_screenshot(source)
            if frame and len(frame) > 100:
                print(f"✅ ({len(frame)} bytes)")
                return source
            else:
                print("❌")
        
        print("\n❌ 未找到可用的来源")
        print("\n💡 可能的原因:")
        print("  1. obs-websocket版本不兼容")
        print("  2. 来源类型不支持截图")
        print("  3. 需要在OBS中启用截图权限")
        return None
    
    def start_http_server(self):
        """启动HTTP服务器"""
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
            print(f"🌐 手机浏览器访问: http://电脑IP:{HTTP_PORT}\n")
            server.serve_forever()
        finally:
            os.chdir(original_cwd)
    
    async def handle_client(self, websocket):
        """处理客户端"""
        self.clients.add(websocket)
        print(f"🌐 客户端: {websocket.remote_address}")
        
        try:
            async for message in websocket:
                pass  # 只接收，暂不处理
        finally:
            self.clients.discard(websocket)
    
    async def start_websocket_server(self):
        self.running = True
        print(f"🚀 WebSocket: ws://{HTTP_HOST}:{WEBSOCKET_PORT}\n")
        async with websockets.serve(self.handle_client, HTTP_HOST, WEBSOCKET_PORT):
            await asyncio.Future()
    
    async def stream_loop(self):
        """主循环"""
        import time
        
        # 查找来源
        source = self.find_working_source() if self.connected else None
        
        last_time = time.time()
        
        while self.running:
            try:
                if self.clients and source:
                    frame = self.try_screenshot(source)
                    if frame:
                        await asyncio.gather(
                            *[client.send(frame) for client in self.clients.copy()],
                            return_exceptions=True
                        )
                        self.clients = {c for c in self.clients if c.open}
                        self.fps += 1
                
                now = time.time()
                if now - last_time >= 2.0:
                    if self.clients:
                        print(f"📊 FPS: {self.fps//2}, 客户端: {len(self.clients)}")
                    self.fps = 0
                    last_time = now
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(1)
    
    def stop(self):
        self.running = False
        if self.ws:
            self.ws.disconnect()


async def main():
    print("=" * 50)
    print("🎮 Screen Region Stream - OBS投屏")
    print("=" * 50)
    
    server = RadarServer()
    
    if not server.connect_obs():
        return
    
    http_thread = threading.Thread(target=server.start_http_server, daemon=True)
    http_thread.start()
    
    try:
        await asyncio.gather(
            server.start_websocket_server(),
            server.stream_loop()
        )
    except KeyboardInterrupt:
        print("\n停止...")
        server.stop()


if __name__ == "__main__":
    asyncio.run(main())
