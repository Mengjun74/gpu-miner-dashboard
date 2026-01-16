# GPU Miner Dashboard

A self-hosted, web-based dashboard to manage NVIDIA GPU mining. Currently configured for **ETC (Ethereum Classic)** using **lolMiner**.

## Features
- **ETC Mining**: Configured for ETCHASH algorithm.
- **lolMiner Integration**: Automatically downloads and runs lolMiner.
- **Web Dashboard**: Real-time hashrate, shares, and logs via WebSocket.
- **Auto-Install**: Automatically downloads and verifies lolMiner release.

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

# Install lolMiner
python installers/install_lolminer.py
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
Edit `backend/config.toml` to change wallet or pool:

```toml
[miner]
args = [
  "--algo", "ETCHASH",
  "--pool", "etc.2miners.com:1010",
  "--user", "0x8b55C6A92eD1ac90eF8CAf3dc188255E13B42B88.worker" 
]
```

## Troubleshooting

### lolMiner Download Failed
- Check your internet connection.
- If GitHub is blocked, manually download the latest lolMiner Windows Zip from [GitHub Releases](https://github.com/Lolliedieb/lolMiner-releases/releases) and extract it to `miners/lolminer/`. Ensure `lolMiner.exe` is at `miners/lolminer/lolMiner.exe`.

### Windows Defender
- Mining software is often flagged as PUA (Potentially Unwanted Application).
- You may need to add an exclusion for the `gpu-miner-dashboard/miners` folder in Windows Security.

### WebSocket Connection Failed
- Ensure the backend is running on port 8000.
- Check if your firewall is blocking local connections.

## Security & Disclaimer
- This software is for **educational and personal use only**.
- Always verify the hash/checksum of downloaded mining software.
- The default wallet address is set to the one provided in the request. Ensure it is correct before mining for long periods.
