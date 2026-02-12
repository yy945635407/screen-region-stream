"""
Screen Region Capture - Windows 屏幕区域捕获与WebSocket传输
"""
import asyncio
import json
import mss
import mss.tools
import cv2
import numpy as np
import websockets
import time
from typing import Optional

# 配置
RADAR_REGION = {
    "left": 0,      # 雷达区域左上角X
    "top": 0,       # 雷达区域左上角Y
    "width": 200,   # 雷达区域宽度
    "height": 200   # 雷达区域高度
}

WEBSOCKET_HOST = "0.0.0.0"
WEBSOCKET_PORT = 8765
JPEG_QUALITY = 85


class RadarCapture:
    """雷达区域捕获器"""
    
    def __init__(self, region: dict = None):
        self.region = region or RADAR_REGION
        self.clients = set()
        self.running = False
        
    async def capture_region(self) -> bytes:
        """捕获指定区域的屏幕，返回JPEG字节"""
        with mss.mss() as sct:
            # 捕获指定区域
            monitor = {
                "left": self.region["left"],
                "top": self.region["top"],
                "width": self.region["width"],
                "height": self.region["height"]
            }
            sct_img = sct.grab(monitor)
            
            # 转换为numpy数组
            img = np.array(sct_img)
            
            # BGR转RGB（mss返回BGRA）
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            # 编码为JPEG
            _, jpeg = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            return jpeg.tobytes()
    
    async def broadcast(self, data: bytes):
        """向所有连接的客户端广播图像"""
        if self.clients:
            await asyncio.gather(
                *[client.send(data) for client in self.clients.copy()],
                return_exceptions=True
            )
            # 清理断开的客户端
            self.clients = {c for c in self.clients if c.open}
    
    async def handler(self, websocket):
        """处理客户端连接"""
        self.clients.add(websocket)
        print(f"客户端连接: {websocket.remote_address}")
        try:
            async for message in websocket:
                # 处理客户端消息（如：调整区域）
                if isinstance(message, str):
                    try:
                        config = json.loads(message)
                        if "region" in config:
                            self.region.update(config["region"])
                            print(f"区域更新: {self.region}")
                    except:
                        pass
        finally:
            self.clients.discard(websocket)
            print(f"客户端断开: {websocket.remote_address}")
    
    async def start_server(self):
        """启动WebSocket服务器"""
        self.running = True
        async with websockets.serve(self.handler, WEBSOCKET_HOST, WEBSOCKET_PORT):
            print(f"🚀 服务器启动: ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
            print("按 Ctrl+C 停止")
            await asyncio.Future()  # 永久运行
    
    async def stream_loop(self, interval: float = 0.05):
        """主循环：捕获并发送图像"""
        while self.running:
            try:
                start_time = time.time()
                
                # 捕获图像
                frame = await self.capture_region()
                
                # 广播
                if self.clients:
                    await self.broadcast(frame)
                
                # 控制帧率
                elapsed = time.time() - start_time
                sleep_time = max(0, interval - elapsed)
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                print(f"错误: {e}")
                await asyncio.sleep(0.1)
    
    def stop(self):
        """停止服务"""
        self.running = False


async def main():
    """主入口"""
    capture = RadarCapture()
    
    try:
        # 同时运行服务器和流循环
        await asyncio.gather(
            capture.start_server(),
            capture.stream_loop(interval=0.033)  # ~30 FPS
        )
    except KeyboardInterrupt:
        print("\n正在停止...")
        capture.stop()


if __name__ == "__main__":
    asyncio.run(main())
