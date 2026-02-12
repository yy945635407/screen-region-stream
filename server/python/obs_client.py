"""
OBS WebSocket Client - 接收OBS画面流并转发到Web浏览器

依赖:
    pip install obs-websocket-py websocket-client numpy opencv-python

配置:
    1. 安装 OBS Studio
    2. 安装 obs-websocket 插件 (https://github.com/obsproject/obs-websocket)
    3. 在OBS中启动 obs-websocket (端口: 4444)
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
from obswebsocket.events import StreamStarting, StreamStarted, StreamStopped

# 配置
OBS_HOST = "localhost"
OBS_PORT = 4444
OBS_PASSWORD = ""  # 如有密码则填写

WEBSOCKET_HOST = "0.0.0.0"
WEBSOCKET_PORT = 8765
JPEG_QUALITY = 85

# 区域配置（从OBS场景中裁剪）
CROP_REGION = {
    "left": 0,
    "top": 0,
    "width": 200,
    "height": 200
}


class OBSStreamer:
    """OBS WebSocket 流接收器"""
    
    def __init__(self):
        self.ws = None
        self.clients = set()
        self.running = False
        self.obs_connected = False
        
        # 最后收到画面的时间
        self.last_frame_time = 0
        self.fps = 0
        self.frame_count = 0
        
    def connect_obs(self):
        """连接OBS WebSocket"""
        try:
            self.ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
            self.ws.connect()
            self.obs_connected = True
            print(f"✓ 已连接OBS: ws://{OBS_HOST}:{OBS_PORT}")
            
            # 注册回调
            self.ws.call(requests.SetHeartbeat(True))
            
            return True
        except Exception as e:
            print(f"✗ 连接OBS失败: {e}")
            return False
    
    def setup_callbacks(self):
        """设置回调"""
        @self.ws.callback
        def on_stream_started(data=None):
            print("▶ OBS开始推流")
        
        @self.ws.callback
        def on_stream_stopped(data=None):
            print("⏸ OBS停止推流")
    
    async def capture_thumbnail(self) -> Optional[bytes]:
        """获取当前画面缩略图"""
        if not self.obs_connected:
            return None
        
        try:
            # 获取当前场景画面
            result = self.ws.call(requests.GetSourceScreenshot(
                sourceName="场景",  # 或具体来源名称
                imageFormat="jpeg",
                imageWidth=400,
                imageHeight=300
            ))
            
            if result:
                # 解析base64图片
                img_data = base64.b64decode(result.imageData)
                return img_data
            
        except Exception as e:
            print(f"获取截图失败: {e}")
        
        return None
    
    async def get_stream_status(self) -> dict:
        """获取流状态"""
        try:
            stats = self.ws.call(requests.GetStreamStatus())
            return {
                "streaming": stats.outputActive,
                "fps": stats.outputFPS,
                "kbps": stats.outputKbps,
            }
        except:
            return {"streaming": False}
    
    async def broadcast(self, data: bytes):
        """广播到所有Web客户端"""
        if self.clients:
            await asyncio.gather(
                *[client.send(data) for client in self.clients.copy()],
                return_exceptions=True
            )
            self.clients = {c for c in self.clients if c.open}
    
    async def handle_client(self, websocket):
        """处理Web客户端连接"""
        self.clients.add(websocket)
        print(f"Web客户端连接: {websocket.remote_address}")
        
        try:
            async for message in websocket:
                # 处理客户端消息
                if isinstance(message, str):
                    try:
                        cmd = json.loads(message)
                        
                        if cmd.get("type") == "status":
                            # 返回OBS状态
                            status = await self.get_stream_status()
                            await websocket.send(json.dumps({
                                "type": "status",
                                "data": status
                            }))
                            
                        elif cmd.get("type") == "crop":
                            # 更新裁剪区域
                            CROP_REGION.update(cmd.get("region", {}))
                            print(f"裁剪区域更新: {CROP_REGION}")
                            
                    except json.JSONDecodeError:
                        pass
                        
        finally:
            self.clients.discard(websocket)
            print(f"Web客户端断开: {websocket.remote_address}")
    
    async def start_server(self):
        """启动WebSocket服务器"""
        async with websockets.serve(self.handle_client, WEBSOCKET_HOST, WEBSOCKET_PORT):
            print(f"🚀 Web服务器启动: ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
            await asyncio.Future()
    
    async def stream_loop(self, interval: float = 0.1):
        """主循环：定期获取OBS画面"""
        while self.running:
            try:
                # 获取画面
                frame = await self.capture_thumbnail()
                
                if frame and self.clients:
                    # 可选：裁剪图片
                    # 这里不做裁剪，让OBS配置处理
                    
                    # 广播
                    await self.broadcast(frame)
                    
                    # FPS统计
                    self.frame_count += 1
                    now = time.time()
                    if now - self.last_frame_time >= 1.0:
                        self.fps = self.frame_count
                        self.frame_count = 0
                        self.last_frame_time = now
                        
            except Exception as e:
                print(f"Stream error: {e}")
            
            await asyncio.sleep(interval)
    
    def stop(self):
        self.running = False
        if self.ws:
            self.ws.disconnect()


import time


class OBSCapture:
    """OBS捕获器（简化版，轮询模式）"""
    
    def __init__(self, region: dict = None):
        self.region = region or CROP_REGION
        self.clients = set()
        self.running = False
        self.ws = None
        self.obs_connected = False
        
    def connect(self) -> bool:
        """连接OBS"""
        try:
            self.ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
            self.ws.connect()
            self.obs_connected = True
            print(f"✓ 已连接OBS")
            return True
        except Exception as e:
            print(f"✗ 连接OBS失败: {e}")
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
                imageWidth=320,  # 缩小尺寸减少带宽
                imageHeight=240
            ))
            
            if result:
                return base64.b64decode(result.imageData)
                
        except Exception as e:
            print(f"Capture error: {e}")
        
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
        print(f"客户端: {websocket.remote_address}")
        try:
            async for message in websocket:
                if isinstance(message, str):
                    try:
                        cmd = json.loads(message)
                        if cmd.get("type") == "region":
                            self.region.update(cmd.get("region", {}))
                    except:
                        pass
        finally:
            self.clients.discard(websocket)
    
    async def start_server(self):
        """启动服务器"""
        self.running = True
        async with websockets.serve(self.handler, WEBSOCKET_HOST, WEBSOCKET_PORT):
            print(f"Server: ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
            await asyncio.Future()
    
    async def stream_loop(self, interval: float = 0.1):
        """流循环"""
        while self.running:
            try:
                frame = await self.capture_frame()
                if frame and self.clients:
                    await self.broadcast(frame)
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
    capture = OBSCapture()
    
    # 连接OBS
    if not capture.connect():
        print("无法连接到OBS，请检查:")
        print("1. OBS是否运行")
        print("2. obs-websocket插件是否安装")
        print("3. WebSocket端口是否为4444")
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
