"""
OBS投屏服务器 - 增强调试版

问题诊断：
- 检测可用来源
- 尝试多种截图方式
"""

import asyncio
import json
import base64
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional, Any
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


# ============== 辅助函数 ==============
def result_to_dict(result) -> dict:
    """将obs-websocket响应转为dict"""
    if hasattr(result, '__dict__'):
        return {k: v for k, v in result.__dict__.items() if not k.startswith('_')}
    elif isinstance(result, dict):
        return result
    else:
        return {'raw': str(result)}


# ============== 主程序 ==============
class OBSStreamServer:
    def __init__(self):
        self.clients = set()
        self.running = False
        self.ws = None
        self.obs_connected = False
        self.working_source = None
    
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
            print(f"\n{'='*50}")
            print("📺 HTTP服务器已启动: http://localhost:{HTTP_PORT}")
            print(f"{'='*50}")
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
            print(f"✅ 已连接OBS\n")
            return True
        except Exception as e:
            print(f"❌ 连接OBS失败: {e}")
            return False
    
    def list_all_sources(self):
        """列出所有来源并测试截图"""
        if not self.obs_connected:
            print("❌ 未连接OBS")
            return
        
        print("🔍 扫描可用来源...\n")
        
        # 方法1: GetSourcesList
        sources_tried = set()
        
        try:
            # 尝试GetSourcesList
            result = self.ws.call(requests.GetSourcesList())
            print("GetSourcesList 返回:")
            
            data = result_to_dict(result)
            if 'sources' in data:
                sources = data['sources']
                for s in sources[:20]:
                    name = s.get('name', str(s))
                    print(f"  - {name}")
            else:
                print(f"  返回数据: {data}\n")
        
        except Exception as e:
            print(f"GetSourcesList 失败: {e}\n")
        
        # 方法2: 尝试预定义名称
        print("\n尝试截图...")
        test_sources = [
            "屏幕捕获",
            "显示器捕获", 
            "窗口捕获",
            "游戏捕获",
            "场景",
            "Scene",
            "",
        ]
        
        for source in test_sources:
            if source in sources_tried:
                continue
                
            try:
                kwargs = {
                    'imageFormat': "jpeg",
                    'imageWidth': 320,
                    'imageHeight': 240
                }
                if source:
                    kwargs['sourceName'] = source
                
                print(f"  尝试 '{source}'...", end=" ")
                result = self.ws.call(requests.GetSourceScreenshot(**kwargs))
                
                data = result_to_dict(result)
                
                # 检查各种可能的数据字段
                img_data = None
                for field in ['imageData', 'image_data', 'data', 'image']:
                    if field in data and data[field]:
                        try:
                            decoded = base64.b64decode(data[field])
                            if len(decoded) > 100:
                                img_data = decoded
                                break
                        except:
                            continue
                
                if img_data:
                    print(f"✅ 成功! ({len(img_data)} bytes)")
                    self.working_source = source
                    return img_data
                else:
                    print(f"❌ (返回: {list(data.keys())})")
                    sources_tried.add(source)
                    
            except Exception as e:
                print(f"❌ ({type(e).__name__})")
                sources_tried.add(source)
        
        print("\n❌ 未找到可截图的来源")
        return None
    
    def capture_with_source(self, source_name: str = "") -> Optional[bytes]:
        """使用指定来源截图"""
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
            data = result_to_dict(result)
            
            for field in ['imageData', 'image_data', 'data']:
                if field in data and data[field]:
                    decoded = base64.b64decode(data[field])
                    if len(decoded) > 100:
                        return decoded
        
        except Exception as e:
            pass
        
        return None
    
    async def handle_client(self, websocket):
        """处理浏览器客户端"""
        self.clients.add(websocket)
        print(f"🌐 客户端: {websocket.remote_address}")
        
        try:
            async for message in websocket:
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        if data.get('type') == 'request_screenshot':
                            frame = self.capture_with_source(self.working_source)
                            if frame:
                                await websocket.send(json.dumps({
                                    'type': 'screenshot',
                                    'data': base64.b64encode(frame).decode()
                                }))
                    except:
                        pass
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
        
        # 首先扫描来源
        if self.obs_connected:
            self.list_all_sources()
        
        fps = 0
        last_time = time.time()
        
        while self.running:
            try:
                if self.clients and self.working_source:
                    frame = self.capture_with_source(self.working_source)
                    if frame:
                        msg = json.dumps({
                            'type': 'screenshot',
                            'data': base64.b64encode(frame).decode()
                        })
                        
                        await asyncio.gather(
                            *[client.send(msg) for client in self.clients.copy()],
                            return_exceptions=True
                        )
                        self.clients = {c for c in self.clients if c.open}
                        fps += 1
                
                now = time.time()
                if now - last_time >= 2.0:
                    if self.clients:
                        print(f"📊 FPS: {fps//2}, 客户端: {len(self.clients)}")
                    fps = 0
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
    print("🎮 Screen Region Stream - OBS投屏(增强调试)")
    print("=" * 50)
    
    server = OBSStreamServer()
    
    if not server.connect_obs():
        return
    
    # 启动HTTP
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
