import uvicorn
import toml
import psutil
import sys
import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from miner_runner import MinerRunner

# Load Config
CONFIG_PATH = Path(__file__).parent / 'config.toml'
if not CONFIG_PATH.exists():
    print("FATAL: config.toml not found.")
    sys.exit(1)

with open(CONFIG_PATH, 'r') as f:
    config = toml.load(f)

app = FastAPI(title="GPU Miner Dashboard")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for local dev convenience, or specify localhost:5173
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Miner Instance
runner = MinerRunner(config)

# Websocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Background Task for WS Broadcast
async def broadcast_status():
    while True:
        status = runner.get_status()
        await manager.broadcast(status)
        await asyncio.sleep(1) # 1Hz update

@app.on_event("startup")
async def startup_event():
    # Check for miner exe
    exe_path = runner.get_exe_path()
    if not exe_path.exists():
        print(f"WARNING: Miner executable invalid at {exe_path}")
        print("Please run: python installers/install_bzminer.py")
    
    asyncio.create_task(broadcast_status())

@app.get("/")
def read_root():
    return {"status": "ok", "service": "gpu-miner-dashboard"}

@app.get("/api/status")
def get_status():
    return runner.get_status()

@app.post("/api/start")
def start_miner():
    success, msg = runner.start()
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "started", "message": msg}

@app.post("/api/stop")
def stop_miner():
    success, msg = runner.stop()
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "stopped", "message": msg}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep alive, receive commands if necessary (mostly push though)
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    host = config['server'].get('host', '127.0.0.1')
    port = config['server'].get('port', 8000)
    uvicorn.run(app, host=host, port=port)
