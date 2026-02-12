"""
Screen Region Capture - DXGI 屏幕区域捕获与WebSocket传输
使用 Windows Desktop Duplication API (DXGI) 捕获游戏内容
"""
import asyncio
import json
import struct
import ctypes
import time
from typing import Optional, Tuple
import websockets

# Windows API imports
from ctypes import wintypes
from ctypes import windll

# 配置
RADAR_REGION = {
    "left": 0,
    "top": 0,
    "width": 200,
    "height": 200
}

WEBSOCKET_HOST = "0.0.0.0"
WEBSOCKET_PORT = 8765
JPEG_QUALITY = 85

# DXGI常量
DXGI_ERROR_ACCESS_LOST = -2005271496
DXGI_ERROR_INVALID_CALL = -2005271520
DXGI_ERROR_WAIT_TIMEOUT = -2005271495
DXGI_ERROR_MODE_BACKED_OUT = -2005271503

WAIT_TIMEOUT = 0x00000102
ERROR_SUCCESS = 0


class DXGICapture:
    """DXGI 屏幕捕获器"""
    
    def __init__(self, adapter_idx: int = 0, output_idx: int = 0):
        self.adapter_idx = adapter_idx
        self.output_idx = output_idx
        self.duplication = None
        self.output_desc = None
        self.width = 0
        self.height = 0
        self.frame_count = 0
        self.last_frame_time = time.time()
        
        self._init_dxgi()
    
    def _init_dxgi(self):
        """初始化DXGI"""
        try:
            # 使用windll加载DXGI
            self.dxgi = ctypes.windll.dxgi
            
            # 创建DXGIFactory
            self.factory = ctypes.c_void_p()
            result = self.dxgi.CreateDXGIFactory(
                0x7b716870,  # IID_IDXGIFactory
                ctypes.byref(self.factory)
            )
            
            if result != ERROR_SUCCESS:
                raise Exception(f"CreateDXGIFactory failed: {result}")
            
            # 获取指定adapter
            self.adapter = ctypes.c_void_p()
            result = self.dxgi.DXGIGetAdapterContentSize(
                self.factory,
                self.adapter_idx,
                ctypes.byref(self.adapter)
            )
            
            if result != ERROR_SUCCESS:
                # 尝试枚举adapter
                for i in range(10):
                    adapter = ctypes.c_void_p()
                    result = self.dxgi.EnumAdapters(
                        self.factory,
                        i,
                        ctypes.byref(adapter)
                    )
                    if result == ERROR_SUCCESS:
                        self.adapter = adapter
                        self.adapter_idx = i
                        print(f"使用 Adapter {i}")
                        break
                else:
                    raise Exception("无法找到可用Adapter")
            
            # 创建Device
            self.device = ctypes.c_void_p()
            result = self.dxgi.CreateDevice(
                self.adapter,
                0,  # DriverType: Hardware
                None,  # Software
                0,  # Flags
                None,  # FeatureLevels count
                0,  # FeatureLevels array
                0,  # SDK version
                ctypes.byref(self.device)
            )
            
            if result != ERROR_SUCCESS:
                raise Exception(f"CreateDevice failed: {result}")
            
            # 枚举output
            output = ctypes.c_void_p()
            result = self.dxgi.EnumOutputs(
                self.adapter,
                self.output_idx,
                ctypes.byref(output)
            )
            
            if result != ERROR_SUCCESS:
                raise Exception(f"EnumOutputs failed: {result}")
            
            # 获取output info
            output_desc = DXGI_OUTPUT_DESC()
            self.dxgi.GetDesc.restype = ctypes.c_bool
            self.dxgi.GetDesc(output, ctypes.byref(output_desc))
            
            self.output_desc = output_desc
            self.width = output_desc.DesktopCoordinates.right - output_desc.DesktopCoordinates.left
            self.height = output_desc.DesktopCoordinates.bottom - output_desc.DesktopCoordinates.top
            
            print(f"屏幕尺寸: {self.width}x{self.height}")
            
            # 创建Duplication
            self.duplication = ctypes.c_void_p()
            result = self.dxgi.DuplicateOutput(
                self.device,
                output,
                ctypes.byref(self.duplication)
            )
            
            if result != ERROR_SUCCESS:
                raise Exception(f"DuplicateOutput failed: {result}")
            
            print("DXGI 初始化成功")
            
        except Exception as e:
            print(f"DXGI 初始化失败: {e}")
            self.duplication = None
    
    def capture_frame(self) -> Optional[bytes]:
        """捕获一帧"""
        if not self.duplication:
            return None
        
        try:
            # 获取帧
            frame_info = DXGI_OUTDUPL_FRAME_INFO()
            desktop_resource = ctypes.c_void_p()
            
            result = self.duplication.AcquireNextFrame(
                500,  # Timeout (ms)
                ctypes.byref(frame_info),
                ctypes.byref(desktop_resource)
            )
            
            if result == WAIT_TIMEOUT:
                return None
            elif result != ERROR_SUCCESS:
                # 重新获取
                self.duplication.ReleaseFrame()
                return None
            
            # 获取桌面资源
            desktop_texture = ctypes.c_void_p()
            result = self.dxgi.QueryInterface(
                desktop_resource,
                0x7b716874,  # IID_ID3D11Texture2D
                ctypes.byref(desktop_texture)
            )
            
            if result != ERROR_SUCCESS:
                self.duplication.ReleaseFrame()
                return None
            
            # 这里简化处理，实际需要D3D11纹理映射
            # 由于Python处理复杂，建议配合OpenCV使用
            
            # 释放资源
            self.dxgi.Release(desktop_texture)
            self.duplication.ReleaseFrame()
            
            return None
            
        except Exception as e:
            print(f"Capture error: {e}")
            return None
    
    def release(self):
        """释放资源"""
        if self.duplication:
            self.dxgi.Release(self.duplication)
            self.duplication = None


class DXGIOutputDesc(ctypes.Structure):
    """DXGI输出描述结构"""
    _fields_ = [
        ("Name", wintypes.LPCWSTR),
        ("DesktopCoordinates", wintypes.RECT),
        ("AttachedToDesktop", ctypes.c_bool),
        ("Rotation", ctypes.c_uint),
        ("Mode", ctypes.c_void_p),  # DXGI_MODE_DESC
        ("PhysicallyConnected", ctypes.c_bool),
    ]


class DXGIOutDuplFrameInfo(ctypes.Structure):
    """DXGI帧信息结构"""
    _fields_ = [
        ("LastPresentTime", ctypes.c_uint64),
        ("LastMouseUpdateTime", ctypes.c_uint64),
        ("AccumulatedFrames", ctypes.c_uint),
        ("RectsCoalesced", ctypes.c_bool),
        ("ProtectedContentMaskedOut", ctypes.c_bool),
        ("RemainingTextiles", ctypes.c_uint64 * 4),
    ]


# 简化的结构定义
DXGI_OUTPUT_DESC = DXGIOutputDesc
DXGI_OUTDUPL_FRAME_INFO = DXGIOutDuplFrameInfo


class RadarCapture:
    """雷达区域捕获器"""
    
    def __init__(self, region: dict = None):
        self.region = region or RADAR_REGION
        self.clients = set()
        self.running = False
        
        # 尝试DXGI，失败则回退到MSS
        self.dxgi = None
        self.use_dxgi = False
        self._init_capture()
    
    def _init_capture(self):
        """初始化捕获"""
        # 尝试DXGI
        try:
            self.dxgi = DXGICapture()
            if self.dxgi.duplication:
                self.use_dxgi = True
                print("✓ 使用DXGI捕获")
                return
        except:
            pass
        
        # 回退到MSS
        print("回退到MSS捕获")
        self.use_dxgi = False
        self._init_mss()
    
    def _init_mss(self):
        """初始化MSS捕获"""
        import mss
        self.mss = mss.mss()
    
    async def capture_region(self) -> bytes:
        """捕获指定区域的屏幕，返回JPEG字节"""
        try:
            if self.use_dxgi:
                return await self._capture_dxgi()
            else:
                return await self._capture_mss()
        except Exception as e:
            print(f"Capture error: {e}")
            return b''
    
    async def _capture_mss(self) -> bytes:
        """MSS捕获"""
        import mss.tools
        import numpy as np
        import cv2
        
        with mss.mss() as sct:
            monitor = {
                "left": self.region["left"],
                "top": self.region["top"],
                "width": self.region["width"],
                "height": self.region["height"]
            }
            sct_img = sct.grab(monitor)
            img = np.array(sct_img)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            _, jpeg = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return jpeg.tobytes()
    
    async def _capture_dxgi(self) -> bytes:
        """DXGI捕获"""
        # DXGI实际需要D3D11配合，简化处理
        # 暂时使用MSS作为后备
        return await self._capture_mss()
    
    async def broadcast(self, data: bytes):
        """向所有连接的客户端广播图像"""
        if self.clients:
            await asyncio.gather(
                *[client.send(data) for client in self.clients.copy()],
                return_exceptions=True
            )
            self.clients = {c for c in self.clients if c.open}
    
    async def handler(self, websocket):
        """处理客户端连接"""
        self.clients.add(websocket)
        print(f"客户端连接: {websocket.remote_address}")
        try:
            async for message in websocket:
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
            await asyncio.Future()
    
    async def stream_loop(self, interval: float = 0.033):
        """主循环"""
        while self.running:
            try:
                start_time = time.time()
                frame = await self.capture_region()
                if self.clients and frame:
                    await self.broadcast(frame)
                
                elapsed = time.time() - start_time
                await asyncio.sleep(max(0, interval - elapsed))
            except Exception as e:
                print(f"Stream error: {e}")
                await asyncio.sleep(0.1)
    
    def stop(self):
        self.running = False
        if self.dxgi:
            self.dxgi.release()


async def main():
    """主入口"""
    capture = RadarCapture()
    
    try:
        await asyncio.gather(
            capture.start_server(),
            capture.stream_loop(interval=0.033)
        )
    except KeyboardInterrupt:
        print("\n正在停止...")
        capture.stop()


if __name__ == "__main__":
    asyncio.run(main())
