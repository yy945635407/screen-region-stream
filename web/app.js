/**
 * Screen Region Stream - Web 客户端 (Debug版)
 */

// 配置
const WS_PORT = 8765;
const SERVER_URL = `ws://${window.location.hostname || 'localhost'}:${WS_PORT}`;

// 状态
let ws = null;
let connected = false;
let frameCount = 0;
let lastFpsTime = Date.now();
let currentFps = 0;

// DOM元素
const canvas = document.getElementById('radarCanvas');
const ctx = canvas.getContext('2d');
const statusEl = document.getElementById('status');
const fpsEl = document.getElementById('fps');
const latencyEl = document.getElementById('latency');
const serverUrlEl = document.getElementById('serverUrl');

// 校准模式
let calibrationMode = false;
let calibrationPoints = [];

// DEBUG: 初始化
function init() {
    console.log('[DEBUG] init() 开始执行');
    console.log('[DEBUG] SERVER_URL =', SERVER_URL);
    
    // 显示服务器地址
    serverUrlEl.textContent = SERVER_URL;
    showStatus('connecting', '连接中...');
    
    console.log('[DEBUG] 准备调用 connect()');
    connect();
    
    // 3秒后检查连接状态
    setTimeout(() => {
        console.log('[DEBUG] 3秒后检查连接状态');
        console.log('[DEBUG] ws =', ws);
        console.log('[DEBUG] ws.readyState =', ws ? ws.readyState : 'ws is null');
        if (ws) {
            console.log('[DEBUG] WebSocket状态:', 
                ws.readyState === 0 ? 'CONNECTING' :
                ws.readyState === 1 ? 'OPEN' :
                ws.readyState === 2 ? 'CLOSING' : 'CLOSED');
        }
        if (!connected) {
            showStatus('disconnected', '连接失败 - 请检查控制台');
        }
    }, 3000);
}

// 连接服务器
function connect() {
    console.log('[DEBUG] connect() 开始');
    
    try {
        console.log('[DEBUG] 创建WebSocket连接...');
        ws = new WebSocket(SERVER_URL);
        console.log('[DEBUG] WebSocket对象已创建');
        
        ws.onopen = () => {
            connected = true;
            showStatus('connected', '已连接');
            console.log('[DEBUG] ✓ onopen 触发 - 连接成功');
        };
        
        ws.onclose = (event) => {
            connected = false;
            showStatus('disconnected', '已断开');
            console.log('[DEBUG] ✗ onclose 触发');
            console.log('[DEBUG] close event:', event);
            
            // 3秒后重连
            setTimeout(() => {
                if (!connected) {
                    console.log('[DEBUG] 自动重连...');
                    connect();
                }
            }, 3000);
        };
        
        ws.onerror = (error) => {
            console.error('[DEBUG] ✗ onerror 触发');
            console.error('[DEBUG] WebSocket错误:', error);
            showStatus('disconnected', '连接错误 - 请检查控制台');
        };
        
        ws.onmessage = (event) => {
            console.log('[DEBUG] onmessage 收到数据');
            
            if (event.data instanceof Blob) {
                console.log('[DEBUG] 收到Blob数据，大小:', event.data.size);
                const blob = event.data;
                const url = URL.createObjectURL(blob);
                
                const img = new Image();
                img.onload = () => {
                    ctx.drawImage(img, 0, 0);
                    URL.revokeObjectURL(url);
                    updateFps();
                    console.log('[DEBUG] 图像绘制完成');
                };
                img.onerror = () => {
                    console.error('[DEBUG] 图像加载失败');
                };
                img.src = url;
            } else if (typeof event.data === 'string') {
                console.log('[DEBUG] 收到文本:', event.data);
                try {
                    const msg = JSON.parse(event.data);
                    handleMessage(msg);
                } catch (e) {
                    console.log('[DEBUG] JSON解析失败:', e);
                }
            }
        };
        
    } catch (e) {
        console.error('[DEBUG] 创建WebSocket异常:', e);
    }
}

// 断开连接
function disconnect() {
    if (ws) {
        console.log('[DEBUG] 手动断开连接');
        ws.close();
        ws = null;
    }
    connected = false;
}

// 处理消息
function handleMessage(msg) {
    console.log('[DEBUG] handleMessage:', msg);
    if (msg.type === 'config') {
        console.log('配置:', msg.data);
    } else if (msg.type === 'latency') {
        latencyEl.textContent = msg.latency.toFixed(0);
    }
}

// 更新FPS
function updateFps() {
    frameCount++;
    const now = Date.now();
    const elapsed = now - lastFpsTime;
    
    if (elapsed >= 1000) {
        currentFps = Math.round(frameCount * 1000 / elapsed);
        fpsEl.textContent = currentFps;
        frameCount = 0;
        lastFpsTime = now;
        console.log('[DEBUG] FPS:', currentFps);
    }
}

// 校准模式
function startCalibration() {
    console.log('[DEBUG] startCalibration 点击');
    calibrationMode = !calibrationMode;
    
    if (calibrationMode) {
        calibrationPoints = [];
        alert('校准模式：点击雷达区域的四个角');
        console.log('[DEBUG] 进入校准模式');
        
        canvas.onclick = (e) => {
            console.log('[DEBUG] canvas.onclick');
            const rect = canvas.getBoundingClientRect();
            const x = (e.clientX - rect.left) * (canvas.width / rect.width);
            const y = (e.clientY - rect.top) * (canvas.height / rect.height);
            
            calibrationPoints.push({ x, y });
            console.log('[DEBUG] 点击点:', calibrationPoints);
            
            // 绘制点击点
            ctx.fillStyle = calibrationPoints.length % 2 === 1 ? '#00ff00' : '#ff0000';
            ctx.beginPath();
            ctx.arc(x, y, 5, 0, Math.PI * 2);
            ctx.fill();
            
            if (calibrationPoints.length === 4) {
                finishCalibration();
            }
        };
    } else {
        canvas.onclick = null;
    }
}

function finishCalibration() {
    calibrationMode = false;
    canvas.onclick = null;
    
    const xs = calibrationPoints.map(p => p.x);
    const ys = calibrationPoints.map(p => p.y);
    
    const config = {
        region: {
            left: Math.min(...xs),
            top: Math.min(...ys),
            width: Math.max(...xs) - Math.min(...xs),
            height: Math.max(...ys) - Math.min(...ys)
        }
    };
    
    console.log('[DEBUG] 发送校准配置:', config);
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(config));
    }
    
    alert('校准完成！区域已更新。');
}

// 显示状态
function showStatus(type, text) {
    statusEl.className = 'status ' + type;
    statusEl.textContent = text;
    console.log('[DEBUG] 状态更新:', type, text);
}

// 页面加载完成后初始化
window.onload = init;
