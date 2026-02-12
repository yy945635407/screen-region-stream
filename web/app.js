/**
 * Screen Region Stream - Web 客户端
 */

// 配置 - 自动检测服务器地址
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

// 初始化
function init() {
    // 显示服务器地址
    serverUrlEl.textContent = SERVER_URL;
    showStatus('connecting', '连接中...');
    
    // 自动连接
    connect();
}

// 连接服务器
function connect() {
    console.log(`连接 ${SERVER_URL}...`);
    
    ws = new WebSocket(SERVER_URL);
    
    ws.onopen = () => {
        connected = true;
        showStatus('connected', '已连接');
        console.log('✓ 连接成功');
    };
    
    ws.onclose = () => {
        connected = false;
        showStatus('disconnected', '已断开');
        console.log('✗ 连接断开');
        
        // 3秒后重连
        if (ws) {
            setTimeout(() => {
                if (!connected && ws.readyState !== WebSocket.CONNECTING) {
                    connect();
                }
            }, 3000);
        }
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket错误:', error);
        showStatus('disconnected', '连接错误');
    };
    
    ws.onmessage = (event) => {
        if (event.data instanceof Blob) {
            // 接收JPEG图像
            const blob = event.data;
            const url = URL.createObjectURL(blob);
            
            const img = new Image();
            img.onload = () => {
                ctx.drawImage(img, 0, 0);
                URL.revokeObjectURL(url);
                updateFps();
            };
            img.src = url;
        } else if (typeof event.data === 'string') {
            // 接收文本消息
            try {
                const msg = JSON.parse(event.data);
                handleMessage(msg);
            } catch (e) {
                console.log('消息:', event.data);
            }
        }
    };
}

// 断开连接
function disconnect() {
    if (ws) {
        ws.close();
        ws = null;
    }
    connected = false;
}

// 处理消息
function handleMessage(msg) {
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
    }
}

// 校准模式
function startCalibration() {
    calibrationMode = !calibrationMode;
    
    if (calibrationMode) {
        calibrationPoints = [];
        alert('校准模式：点击雷达区域的四个角（左上、右上、右下、左下）');
        
        canvas.onclick = (e) => {
            const rect = canvas.getBoundingClientRect();
            const x = (e.clientX - rect.left) * (canvas.width / rect.width);
            const y = (e.clientY - rect.top) * (canvas.height / rect.height);
            
            calibrationPoints.push({ x, y });
            
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
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(config));
    }
    
    alert('校准完成！区域已更新。');
}

// 显示状态
function showStatus(type, text) {
    statusEl.className = 'status ' + type;
    statusEl.textContent = text;
}

// 页面加载完成后初始化
window.onload = init;
