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
            if "kheavyhash.unmineable.com" in arg:
                pool_valid = True
                break
        if not pool_valid:
            raise ValueError("INVALID CONFIG: Pool must be kheavyhash.unmineable.com")

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
            "pool": "kheavyhash.unmineable.com",
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
        # BzMiner Table Parsing
        # | #    | a/r/i | cfg | tbs | eff | pool hr | miner hr | status |
        # | 1:0  | 10/0/0 | ...
        
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 8:
                # Share parsing
                try:
                    shares_str = parts[2]
                    if "/" in shares_str:
                        a, r, i = shares_str.split("/")
                        # Handle "1/-/-" where - means 0 or N/A
                        
                        if a.isdigit():
                            self.stats['accepted'] = int(a)
                        
                        # Handle rejected independently
                        if r.isdigit():
                             self.stats['rejected'] = int(r)
                        elif r == '-':
                             self.stats['rejected'] = 0
                except:
                    pass

                # Hashrate parsing - Check both Pool HR (6) and Miner HR (7)
                # BzMiner v23.0.4 logs: "837.37mh" or "1.07gh" (No /s)
                found_hr = False
                for idx in [7, 6]:
                    try:
                        val = parts[idx].lower()
                        # Check for mh, gh, th, ph (with or without /s)
                        if any(u in val for u in ["kh", "mh", "gh", "th", "ph"]):
                            # Normalize unit
                            clean_val = val
                            if not clean_val.endswith("s"):
                                clean_val += "/s" # append /s if missing (mh -> mh/s)
                            
                            # Format properly: "837.37mh/s" -> "837.37 MH/s"
                            display_val = clean_val.upper()\
                                .replace("KH/S", " KH/s")\
                                .replace("MH/S", " MH/s")\
                                .replace("GH/S", " GH/s")\
                                .replace("TH/S", " TH/s")\
                                .replace("PH/S", " PH/s")
                                
                            self.stats['hashrate'] = display_val
                            found_hr = True
                            break
                    except:
                        pass
                
        # Fallback/Supplemental: Simple regex for standard log lines if they exist
        # "Total: 100.0 MH/s" or "Total 100.0 MH/s"
        match = re.search(r'Total:?\s*(\d+(\.\d+)?)\s*(MH/s|GH/s)', line, re.IGNORECASE)
        if match:
             self.stats['hashrate'] = f"{match.group(1)} {match.group(3)}"

        # "Accepted share" lines
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

