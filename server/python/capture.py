"""
屏幕捕获服务器 - 直接截图 + WebSocket传输

支持:
1. MSS直接截图（简单场景）
2. 发送到浏览器显示
"""

import asyncio
import json
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional
import websockets
import mss
import numpy as np
import cv2

# ============== 配置 ==============
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8080
WEBSOCKET_PORT = 8765

# 截图区域配置
CAPTURE_REGION = {
    "left": 0,
    "top": 0,
    "width": 320,
    "height": 240
}


# ============== HTTP 服务器 ==============
class QuietHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        server_python_dir = os.path.dirname(os.path.abspath(__file__))
        self.web_root = os.path.join(os.path.dirname(os.path.dirname(server_python_dir)), 'web')
        super().__init__(*args, directory=self.web_root, **kwargs)
    
    def log_message(self, format, *args):
        pass


def start_http_server():
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
        print(f"🌐 浏览器访问: http://localhost:{HTTP_PORT}")
        server.serve_forever()
    finally:
        os.chdir(original_cwd)


# ============== 截图服务 ==============
class CaptureServer:
    def __init__(self):
        self.clients = set()
        self.running = False
        self.sct = None
        
    def init_capture(self) -> bool:
        """初始化截图"""
        try:
            self.sct = mss.mss()
            print("✅ MSS截图初始化成功")
            
            # 测试截图
            monitor = {
                "left": CAPTURE_REGION["left"],
                "top": CAPTURE_REGION["top"],
                "width": CAPTURE_REGION["width"],
                "height": CAPTURE_REGION["height"]
            }
            img = self.sct.grab(monitor)
            print(f"✅ 测试截图成功: {len(img)} bytes")
            return True
        except Exception as e:
            print(f"❌ MSS初始化失败: {e}")
            return False
    
    def capture_screen(self) -> Optional[bytes]:
        """截图并返回JPEG"""
        if not self.sct:
            return None
        
        try:
            monitor = {
                "left": CAPTURE_REGION["left"],
                "top": CAPTURE_REGION["top"],
                "width": CAPTURE_REGION["width"],
                "height": CAPTURE_REGION["height"]
            }
            
            img = self.sct.grab(monitor)
            img_np = np.array(img)
            
            # BGRA转BGR
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
            
            # JPEG编码
            _, jpeg = cv2.imencode('.jpg', img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return jpeg.tobytes()
            
        except Exception as e:
            print(f"截图错误: {e}")
            return None
    
    async def handle_client(self, websocket):
        """处理Web客户端"""
        self.clients.add(websocket)
        print(f"🌐 客户端: {websocket.remote_address}")
        
        try:
            async for message in websocket:
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        
                        if data.get('type') == 'ping':
                            await websocket.send(json.dumps({'type': 'pong'}))
                        
                        elif data.get('type') == 'region':
                            CAPTURE_REGION.update(data.get('region', {}))
                            print(f"📐 区域更新: {CAPTURE_REGION}")
                    
                    except:
                        pass
        finally:
            self.clients.discard(websocket)
    
    async def start_websocket_server(self):
        """启动WebSocket服务器"""
        self.running = True
        print(f"🚀 WebSocket: ws://{HTTP_HOST}:{WEBSOCKET_PORT}")
        async with websockets.serve(self.handle_client, HTTP_HOST, WEBSOCKET_PORT):
            await asyncio.Future()
    
    async def stream_loop(self):
        """主循环"""
        import time
        
        fps = 0
        last_time = time.time()
        
        while self.running:
            try:
                frame = self.capture_screen()
                
                if frame and self.clients:
                    await asyncio.gather(
                        *[client.send(frame) for client in self.clients.copy()],
                        return_exceptions=True
                    )
                    self.clients = {c for c in self.clients if c.open}
                    
                    fps += 1
                    
                    now = time.time()
                    if now - last_time >= 1.0:
                        print(f"📊 FPS: {fps}, 客户端: {len(self.clients)}")
                        fps = 0
                        last_time = now
                
                await asyncio.sleep(0.05)  # 20 FPS
                
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(1)
    
    def stop(self):
        self.running = False
        if self.sct:
            self.sct.close()


# ============== 主入口 ==============
async def main():
    print("=" * 50)
    print("🎮 Screen Region Stream - 直接截图方案")
    print("=" * 50)
    
    server = CaptureServer()
    
    # 初始化截图
    if not server.init_capture():
        print("\n💡 提示: 如果MSS无法截图，请:")
        print("   1. 确保以管理员身份运行")
        print("   2. 或者改用OBS方案")
        return
    
    # 启动HTTP服务器
    http_thread = threading.Thread(target=start_http_server, daemon=True)
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
