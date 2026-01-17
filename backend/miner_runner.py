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
        # Basic validation only. Removed strict algorithm/pool checks to allow flexibility (e.g. ETC/lolMiner).
        args = self.config['miner'].get('args', [])
        if not args:
            print("Warning: No miner arguments specified.")
        return True

    def get_exe_path(self):
        user_path = self.config['miner'].get('exe')
        if user_path:
            return Path(user_path)
        
        # Default path fallback search
        project_root = Path(__file__).parent.parent
        
        # Check lolMiner
        lol_path = project_root / "miners" / "lolminer" / "lolMiner.exe"
        if lol_path.exists():
            return lol_path

        return project_root / "miners" / "generic_miner.exe"

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
            "algo": "Unknown", 
            "pool": "Unknown",
            "uptime": 0,
            "start_time": time.time()
        }
        self.log_tail.clear()
        self.stop_event.clear()

        try:
            # shell=False for security, direct execution
            print(f"Starting miner with command: {' '.join(cmd)}")
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Merge stderr to stdout
                text=True,
                cwd=str(exe_path.parent) # Run in miner dir
            )
            self.running = True
            
            # Populate basic stats from args for display
            args = self.config['miner']['args']
            if "--algo" in args:
                try:
                    self.stats['algo'] = args[args.index("--algo")+1]
                except: pass
            if "--pool" in args:
                try:
                    self.stats['pool'] = args[args.index("--pool")+1]
                except: pass

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
        # Ensure logs dir exists
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Create log file
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_file_path = logs_dir / f"miner_{timestamp}.log"
        print(f"Logging miner output to: {log_file_path.absolute()}")

        try:
            with open(log_file_path, "w", encoding="utf-8") as f:
                while self.running and self.process:
                    line = self.process.stdout.readline()
                    if not line and self.process.poll() is not None:
                        break
                    
                    if line:
                        # Write to log file
                        f.write(line)
                        f.flush()

                        clean_line = line.strip()
                        if clean_line:
                            self.log_tail.append(clean_line)
                            self._parse_line(clean_line)
        except Exception as e:
            print(f"Error writing to log file: {e}")
        
        self.running = False

    def _parse_line(self, line):
        # Strip ANSI color codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_line = ansi_escape.sub('', line).strip()
        
        # Universal / lolMiner Parsing
        
        # 1. Accepted Shares
        # lolMiner: "GPU 0: Share accepted (80 ms)"
        # Generic: "Accepted share"
        if "Share accepted" in clean_line or "Accepted share" in clean_line:
            self.stats['accepted'] += 1
            
        # Table parsing for Accepted/Rejected count (lolMiner "7/0/0")
        # GPU 0 ... 51.31 ... 7/0/0
        if "/" in clean_line:
             # Look for pattern like " 7/0/0 "
             # This is a bit loose but helpful for correct totals from the table
             m = re.search(r'\s(\d+)/(\d+)/(\d+)\s', clean_line)
             if m and "GPU" not in clean_line: # Avoid GPU rows if we want Total, or sum them?
                 # Actually, "Total ... 7/0/0" row is best
                 if "Total" in clean_line:
                     self.stats['accepted'] = int(m.group(1))
                     self.stats['rejected'] = int(m.group(2))

        # 2. Hashrate
        # lolMiner: "Average speed (15s): 50.94 Mh/s"
        m_speed = re.search(r'Average speed.*:\s*(\d+(\.\d+)?)\s*(Mh/s|Gh/s)', clean_line, re.IGNORECASE)
        if m_speed:
             self.stats['hashrate'] = f"{m_speed.group(1)} {m_speed.group(3)}"
             return

        # Check for explicit Total line in table
        # Total ... 51.31 ...
        if "Total" in clean_line:
            # Look for the first float number after "Total"
            # Total ... 51.31
            # But be careful not to match other things. The table structure is:
            # Total ... Hashrate ...
            parts = clean_line.split()
            # lolMiner Total row: Total <space> 51.31 <space> ...
            if len(parts) > 2 and parts[0] == "Total":
                try:
                    # changes based on table col index, but first float usually is hashrate
                    val = float(parts[1])
                    if val > 0: # Sanity check
                        self.stats['hashrate'] = f"{val} Mh/s" # lolMiner is usually Mh/s for ETC
                except:
                    pass

        # Fallback/Supplemental
        match = re.search(r'Total:?\s*(\d+(\.\d+)?)\s*(MH/s|GH/s)', clean_line, re.IGNORECASE)
        if match:
             self.stats['hashrate'] = f"{match.group(1)} {match.group(3)}"

    def get_status(self):
        if self.running:
            self.stats['uptime'] = int(time.time() - self.stats['start_time'])
        
        return {
            "running": self.running,
            "pid": self.process.pid if self.process else None,
            "stats": self.stats,
            # "logs": list(self.log_tail) # Sending all logs via websocket might be heavy, but fine for small tail
            "logs": list(self.log_tail)
        }

