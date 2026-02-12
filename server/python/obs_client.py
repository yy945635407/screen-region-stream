"""
OBS投屏服务器 - 通过浏览器中转

工作原理：
1. Python服务器启动HTTP + WebSocket
2. OBS添加"浏览器"来源，URL=http://localhost:8080/obs.html
3. 页面连接WebSocket接收截图并显示
4. Python通过WebSocket发送截图到页面
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


# ============== HTTP 服务器 ==============
class QuietHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        server_python_dir = os.path.dirname(os.path.abspath(__file__))
        self.web_root = os.path.join(os.path.dirname(os.path.dirname(server_python_dir)), 'web')
        super().__init__(*args, directory=self.web_root, **kwargs)
    
    def log_message(self, format, *args):
        pass


# ============== 主程序 ==============
class OBSStreamServer:
    def __init__(self):
        self.clients = set()  # Web浏览器客户端
        self.running = False
        self.ws = None
        self.obs_connected = False
        self.screenshot_interval = 0.1  # 10 FPS
    
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
            print(f"\n{'='*50}")
            print("📋 OBS配置步骤:")
            print(f"   1. OBS中添加 '浏览器' 来源")
            print(f"   2. URL填写: http://localhost:{HTTP_PORT}/obs.html")
            print(f"   3. 宽度: 320, 高度: 240")
            print(f"   4. 勾选 '使输出可见' → '虚拟摄像机'")
            print(f"{'='*50}\n")
            server.serve_forever()
        finally:
            os.chdir(original_cwd)
    
    def connect_obs(self) -> bool:
        """连接OBS"""
        try:
            print(f"🔌 连接OBS: ws://{OBS_HOST}:{OBS_PORT}...")
            self.ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
            self.ws.connect()
            self.obs_connected = True
            print(f"✅ 已连接OBS")
            return True
        except Exception as e:
            print(f"❌ 连接OBS失败: {e}")
            return False
    
    def capture_screenshot(self) -> Optional[bytes]:
        """从OBS获取截图"""
        if not self.obs_connected:
            return None
        
        # 尝试多个可能的来源
        sources = ["屏幕捕获", "显示器捕获", "窗口捕获", "场景"]
        
        for source in sources:
            try:
                result = self.ws.call(requests.GetSourceScreenshot(
                    sourceName=source,
                    imageFormat="jpeg",
                    imageWidth=320,
                    imageHeight=240
                ))
                
                # 检查返回数据
                if hasattr(result, 'imageData') and result.imageData:
                    data = base64.b64decode(result.imageData)
                    if len(data) > 100:
                        return data
                        
            except Exception as e:
                continue
        
        return None
    
    async def handle_client(self, websocket):
        """处理浏览器客户端"""
        self.clients.add(websocket)
        client_id = len(self.clients)
        print(f"🌐 客户端 #{client_id}: {websocket.remote_address}")
        
        try:
            async for message in websocket:
                # 接收来自页面的消息
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        
                        if data.get('type') == 'request_screenshot':
                            # 页面请求截图
                            frame = self.capture_screenshot()
                            if frame:
                                # 发送base64编码的图片
                                await websocket.send(json.dumps({
                                    'type': 'screenshot',
                                    'data': base64.b64encode(frame).decode()
                                }))
                        
                        elif data.get('type') == 'pong':
                            # 心跳响应
                            pass
                    
                    except json.JSONDecodeError:
                        pass
                    
        finally:
            self.clients.discard(websocket)
            print(f"   客户端 #{client_id} 断开")
    
    async def start_websocket_server(self):
        """启动WebSocket服务器"""
        self.running = True
        print(f"🚀 WebSocket: ws://{HTTP_HOST}:{WEBSOCKET_PORT}")
        async with websockets.serve(self.handle_client, HTTP_HOST, WEBSOCKET_PORT):
            await asyncio.Future()
    
    async def stream_loop(self):
        """主循环 - 定时推送截图"""
        import time
        
        while self.running:
            try:
                if self.clients:
                    frame = self.capture_screenshot()
                    if frame:
                        # 广播到所有客户端
                        msg = json.dumps({
                            'type': 'screenshot',
                            'data': base64.b64encode(frame).decode()
                        })
                        
                        await asyncio.gather(
                            *[client.send(msg) for client in self.clients.copy()],
                            return_exceptions=True
                        )
                        self.clients = {c for c in self.clients if c.open}
                
                await asyncio.sleep(self.screenshot_interval)
                
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(1)
    
    def stop(self):
        self.running = False
        if self.ws:
            self.ws.disconnect()


async def main():
    print("=" * 50)
    print("🎮 Screen Region Stream - OBS投屏方案")
    print("=" * 50)
    
    server = OBSStreamServer()
    
    # 连接OBS
    if not server.connect_obs():
        return
    
    # 启动HTTP服务器（后台）
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
