import subprocess
import time
import threading
import psutil
import os
import signal
import re
from pathlib import Path
from collections import deque

class MinerRunner:
    def __init__(self, config):
        self.config = config
        self.process = None
        self.running = False
        self.log_tail = deque(maxlen=200)
        self.stats = {
            "hashrate": "0 MH/s",
            "accepted": 0,
            "rejected": 0,
            "algo": "Unknown",
            "pool": "Unknown",
            "uptime": 0,
            "start_time": 0
        }
        self.stop_event = threading.Event()
        self.log_thread = None

    def _validate_config(self):
        # Security: Enforce Kaspa and unMineable
        args = self.config['miner']['args']
        exe = self.config['miner'].get('exe', '')
        
        # Check Algo
        if "-a" in args:
            idx = args.index("-a")
            if idx + 1 < len(args):
                algo = args[idx+1].lower()
                if algo != "kaspa" and algo != "kheavyhash":
                     raise ValueError("INVALID CONFIG: Algorithm must be kaspa")
        else:
             raise ValueError("INVALID CONFIG: Algorithm not specified")

        # Check Pool
        pool_valid = False
        for arg in args:
            if "kaspa.unmineable.com" in arg:
                pool_valid = True
                break
        if not pool_valid:
            raise ValueError("INVALID CONFIG: Pool must be kaspa.unmineable.com")

        # Check Wallet Format
        wallet_arg = ""
        if "-w" in args:
             wallet_arg = args[args.index("-w")+1]
        
        # Simple check for DOGE: prefix
        if not wallet_arg.startswith("DOGE:"):
             raise ValueError("INVALID CONFIG: Wallet must start with DOGE:")

        return True

    def get_exe_path(self):
        user_path = self.config['miner'].get('exe')
        if user_path:
            return Path(user_path)
        
        # Default path
        project_root = Path(__file__).parent.parent
        default_path = project_root / "miners" / "bzminer" / "bzminer.exe"
        return default_path

    def start(self):
        if self.running:
            return False, "Already running"

        try:
            self._validate_config()
        except ValueError as e:
            return False, str(e)

        exe_path = self.get_exe_path()
        if not exe_path.exists():
            return False, f"Miner executable not found at {exe_path}. Please run installer."

        cmd = [str(exe_path)] + self.config['miner']['args']
        
        # Reset stats
        self.stats = {
            "hashrate": "0 MH/s",
            "accepted": 0,
            "rejected": 0,
            "algo": "kaspa (kHeavyHash)", 
            "pool": "kaspa.unmineable.com",
            "uptime": 0,
            "start_time": time.time()
        }
        self.log_tail.clear()
        self.stop_event.clear()

        try:
            # shell=False for security, direct execution
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Merge stderr to stdout
                text=True,
                cwd=str(exe_path.parent) # Run in miner dir
            )
            self.running = True
            
            # Start log reader thread
            self.log_thread = threading.Thread(target=self._monitor_output)
            self.log_thread.daemon = True
            self.log_thread.start()
            
            return True, f"Started with PID {self.process.pid}"
        except Exception as e:
            self.running = False
            return False, str(e)

    def stop(self):
        if not self.running or not self.process:
            return False, "Not running"

        self.stop_event.set()
        
        # Try terminate first
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
            
        self.running = False
        self.process = None
        return True, "Stopped"

    def _monitor_output(self):
        # BzMiner output parsing
        # Example lines (hypothetical based on standard miners):
        # [2024-01-01 12:00:00] [INFO] GPU0: 1000.0 MH/s, A: 10, R: 0
        
        # Regex patterns to grab data
        # Adjust these based on actual BzMiner output
        hr_pattern = re.compile(r"(\d+(\.\d+)?) (MH|GH|TH)/s")
        shares_pattern = re.compile(r"A:\s*(\d+).*R:\s*(\d+)")
        
        while self.running and self.process:
            line = self.process.stdout.readline()
            if not line and self.process.poll() is not None:
                break
            
            if line:
                clean_line = line.strip()
                if clean_line:
                    self.log_tail.append(clean_line)
                    self._parse_line(clean_line)
        
        self.running = False

    def _parse_line(self, line):
        # Simple heuristic parsing
        
        # 1. Accepted/Rejected Share Update
        # Look for "Accepted share" or summary lines
        # Many miners output stats lines periodically
        
        # Example check for shares
        # Assuming log might have "Accepted" word or "A: <num>"
        if "Accepted" in line or "A:" in line:
            # Try to extract numbers if available in a standard format
            # This is best-effort without running it live first
            pass

        # 2. Hashrate
        # Look for "MH/s" or "GH/s"
        match = re.search(r'Total:?\s*(\d+(\.\d+)?)\s*(MH/s|GH/s)', line, re.IGNORECASE)
        if match:
             self.stats['hashrate'] = f"{match.group(1)} {match.group(3)}"

        # Also generic scraper for "A: x R: y" often found in miner logs
        share_match = re.search(r'A:(\d+).*R:(\d+)', line)
        if share_match:
            try:
                self.stats['accepted'] = int(share_match.group(1))
                self.stats['rejected'] = int(share_match.group(2))
            except:
                pass
                
        # Parse official "Accepted share" lines to increment if cumulative not found
        if "Accepted share" in line:
            self.stats['accepted'] += 1

    def get_status(self):
        if self.running:
            self.stats['uptime'] = int(time.time() - self.stats['start_time'])
        
        return {
            "running": self.running,
            "pid": self.process.pid if self.process else None,
            "stats": self.stats,
            "logs": list(self.log_tail)
        }
