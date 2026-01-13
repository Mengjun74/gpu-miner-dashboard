# GPU Miner Dashboard

A self-hosted, web-based dashboard to manage NVIDIA GPU mining for Kaspa (KAS) via unMineable (paying out in DOGE).

## Features
- **Strictly KASPA**: Configured solely for kHeavyHash algorithm.
- **Auto-Exchange**: Mines to unMineable pool to auto-convert KAS -> DOGE.
- **Web Dashboard**: Real-time hashrate, shares, and logs via WebSocket.
- **Auto-Install**: Automatically downloads and verifies BzMiner release.

## Prerequisites
- Windows 10/11
- NVIDIA GPU (RTX 30xx/40xx/50xx recommended)
- Python 3.11+
- Node.js 18+

## Installation

### 1. Setup Backend
Open a PowerShell terminal in the project root:

```powershell
# Create virtual environment (optional but recommended)
python -m venv venv
.\venv\Scripts\Activate

# Install dependencies
pip install -r backend/requirements.txt

# Install BzMiner (Can also be done via UI later, but good to verify first)
python installers/install_bzminer.py
```

### 2. Setup Frontend
Open a new terminal:

```powershell
cd frontend
npm install
```

## Running the System

### 1. Start Backend Server
```powershell
# In project root
python backend/main.py
```
Server runs at `http://127.0.0.1:8000`.

### 2. Start Frontend UI
```powershell
# In frontend directory
npm run dev
```
Dashboard available at `http://localhost:5173`.

## Configuration
Edit `backend/config.toml` to change wallet or worker name (though defaults are set to your request):

```toml
[miner]
args = [
  "-a", "kaspa",
  "-p", "stratum+tcp://kaspa.unmineable.com:3333",
  "-w", "DOGE:YOUR_ADDRESS.WORKER_NAME", 
  "-r", "4"
]
```
**Note**: The system enforces `kaspa` and `kaspa.unmineable.com`. Changing these to other coins/pools will cause the miner to fail startup validation.

## Troubleshooting

### BzMiner Download Failed
- Check your internet connection.
- If GitHub is blocked, manually download the latest BzMiner Windows Zip from [GitHub Releases](https://github.com/bzminer/bzminer/releases) and extract it to `miners/bzminer/`. Ensure `bzminer.exe` is at `miners/bzminer/bzminer.exe`.

### Windows Defender
- Mining software is often flagged as PUA (Potentially Unwanted Application).
- You may need to add an exclusion for the `gpu-miner-dashboard/miners` folder in Windows Security.
- **Verify Source**: Only use the included installer which fetches from the official BzMiner GitHub repo.

### WebSocket Connection Failed
- Ensure the backend is running on port 8000.
- Check if your firewall is blocking local connections.

## Security & Disclaimer
- This software is for **educational and personal use only**.
- Always verify the hash/checksum of downloaded mining software.
- The default wallet address is set to the one provided in the request. Ensure it is correct before mining for long periods.
