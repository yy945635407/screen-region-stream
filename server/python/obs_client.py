"""
OBS投屏服务器 - 使用obs-source-screenshot

依赖:
    pip install obs-source-screenshot

这个库可以直接从OBS获取截图，兼容性更好。
"""

import asyncio
import json
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional
import websockets

# ============== 配置 ==============
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8080
WEBSOCKET_PORT = 8765


# ============== HTTP 服务器 ==============
class QuietHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        server_python_dir = os.path.dirname(os.path.abspath(__file__))
        self.web_root = os.path.join(os.path.dirname(os.path.dirname(server_python_dir)), 'web')
        super().__init__(*args, directory=self.web_root, **kwargs)
    
    def log_message(self, format, *args):
        pass


# ============== 主程序 ==============
class OBSCaptureServer:
    def __init__(self):
        self.clients = set()
        self.running = False
        self.obs = None
        self.fps = 0
    
    def init_obs(self) -> bool:
        """初始化OBS连接"""
        try:
            # 尝试使用 obs-source-screenshot
            from obs_source_screenshot import OBS
            self.obs = OBS()
            self.obs.connect()
            print("✅ 已连接OBS (obs-source-screenshot)")
            return True
        except ImportError:
            print("❌ 未安装 obs-source-screenshot")
            print("\n请安装:")
            print("  pip install obs-source-screenshot\n")
            return False
        except Exception as e:
            print(f"❌ 连接OBS失败: {e}")
            return False
    
    def capture(self) -> Optional[bytes]:
        """获取截图"""
        if not self.obs:
            return None
        
        try:
            return self.obs.get_screenshot()
        except Exception as e:
            print(f"截图错误: {e}")
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
            print(f"\n📺 HTTP服务器: http://localhost:{HTTP_PORT}")
            print(f"🌐 手机浏览器访问: http://你的电脑IP:{HTTP_PORT}\n")
            server.serve_forever()
        finally:
            os.chdir(original_cwd)
    
    async def handle_client(self, websocket):
        """处理浏览器客户端"""
        self.clients.add(websocket)
        print(f"🌐 手机客户端: {websocket.remote_address}")
        
        try:
            async for message in websocket:
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        if data.get('type') == 'ping':
                            await websocket.send(json.dumps({'type': 'pong'}))
                    except:
                        pass
        finally:
            self.clients.discard(websocket)
    
    async def start_websocket_server(self):
        self.running = True
        print(f"🚀 WebSocket: ws://{HTTP_HOST}:{WEBSOCKET_PORT}")
        async with websockets.serve(self.handle_client, HTTP_HOST, WEBSOCKET_PORT):
            await asyncio.Future()
    
    async def stream_loop(self):
        """主循环"""
        import time
        
        last_time = time.time()
        
        while self.running:
            try:
                if self.clients:
                    frame = self.capture()
                    if frame:
                        await asyncio.gather(
                            *[client.send(frame) for client in self.clients.copy()],
                            return_exceptions=True
                        )
                        self.clients = {c for c in self.clients if c.open}
                        self.fps += 1
                
                now = time.time()
                if now - last_time >= 1.0:
                    print(f"📊 FPS: {self.fps}, 客户端: {len(self.clients)}")
                    self.fps = 0
                    last_time = now
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(1)
    
    def stop(self):
        self.running = False


async def main():
    print("=" * 50)
    print("🎮 Screen Region Stream - OBS投屏")
    print("=" * 50)
    
    server = OBSCaptureServer()
    
    if not server.init_obs():
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
