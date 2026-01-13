import os
import sys
import json
import requests
import zipfile
import shutil
import hashlib
from pathlib import Path

# Configuration
REPO_OWNER = "bzminer"
REPO_NAME = "bzminer"
INSTALL_DIR_REL = "../miners/bzminer"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

def get_project_root():
    return Path(__file__).parent.parent

def install_bzminer():
    print("--- Starting BzMiner Installation ---")
    
    project_root = get_project_root()
    install_dir = project_root / "miners" / "bzminer"
    
    # 1. Clean existing install if needed
    if install_dir.exists():
        print(f"Directory {install_dir} exists. Cleaning up...")
        try:
            shutil.rmtree(install_dir)
        except Exception as e:
            print(f"Error cleaning directory: {e}")
            return False
            
    install_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Get latest release info
    print(f"Fetching latest release from {GITHUB_API_URL}...")
    try:
        resp = requests.get(GITHUB_API_URL)
        resp.raise_for_status()
        release_data = resp.json()
    except Exception as e:
        print(f"Failed to fetch release info: {e}")
        return False
        
    tag_name = release_data.get("tag_name", "unknown")
    print(f"Latest version: {tag_name}")
    
    # 3. Find Windows asset
    assets = release_data.get("assets", [])
    download_url = None
    asset_name = None
    
    for asset in assets:
        name = asset["name"].lower()
        if "windows" in name and name.endswith(".zip"):
            download_url = asset["browser_download_url"]
            asset_name = asset["name"]
            break
            
    if not download_url:
        print("Error: No Windows zip asset found in latest release.")
        return False
        
    print(f"Found asset: {asset_name}")
    print(f"Download URL: {download_url}")
    
    # 4. Download
    zip_path = install_dir / asset_name
    print("Downloading...")
    try:
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(zip_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
    except Exception as e:
        print(f"Download failed: {e}")
        return False

    print("Download complete.")
    
    # 5. Verify (File size check at minimum, ideally hash if available)
    # Since we can't easily get the hash from the API response body (usually in a separate file),
    # we'll just check if the file is a valid zip and non-empty.
    # In a real rigorous scenario, we'd fetch the CHECKSUMS file from the release as well.
    if zip_path.stat().st_size < 1000000: # < 1MB is suspicious
        print("Error: Downloaded file seems too small.")
        return False

    # 6. Extract
    print("Extracting...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # BzMiner zip usually contains a root folder like "bzminer_v..._windows". 
            # We want to flatten it or handle it.
            zip_ref.extractall(install_dir)
            
        # Move contents up if there's a single wrapper directory
        subdirs = [x for x in install_dir.iterdir() if x.is_dir()]
        if len(subdirs) == 1:
            wrapper_dir = subdirs[0]
            print(f"Flattening directory structure from {wrapper_dir.name}...")
            for item in wrapper_dir.iterdir():
                shutil.move(str(item), str(install_dir))
            wrapper_dir.rmdir()
            
    except zipfile.BadZipFile:
        print("Error: Invalid zip file.")
        return False
    except Exception as e:
        print(f"Extraction failed: {e}")
        return False
        
    # 7. Cleanup Zip
    try:
        os.remove(zip_path)
    except:
        pass

    # 8. Check for executable
    exe_path = install_dir / "bzminer.exe"
    if exe_path.exists():
        print(f"SUCCESS: BzMiner installed at {exe_path}")
        print("IMPORTANT: Please verify the downloaded file hash against the official release if you have security concerns.")
        return True
    else:
        print(f"Error: bzminer.exe not found in {install_dir} after extraction.")
        return False

if __name__ == "__main__":
    success = install_bzminer()
    if not success:
        sys.exit(1)
