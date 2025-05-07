#!/usr/bin/env python3
import os
import sys
import shutil
from pathlib import Path

def install():
    """Install the zoompoller command globally"""
    # Make zoompoller.py executable
    script_path = Path(__file__).parent / "zoompoller.py"
    script_path.chmod(0o755)
    
    # Determine the bin directory based on OS
    if sys.platform == "win32":
        # For Windows, we'll create a batch file in Scripts directory
        # Get the Scripts directory from sys.prefix instead of sys.executable
        scripts_dir = Path(sys.prefix) / "Scripts"
        
        # Create Scripts directory if it doesn't exist
        if not scripts_dir.exists():
            scripts_dir.mkdir(parents=True)
            
        batch_path = scripts_dir / "zoompoller.bat"
        python_path = sys.executable
        
        # Create batch file
        with open(batch_path, "w") as f:
            f.write(f'@echo off\n"{python_path}" "{script_path}" %*')
        
        print(f"✓ Created {batch_path}")
        print("\nZoom Poll Automator installed successfully!")
        print("You can now use 'zoompoller' from anywhere.")
        
    else:
        # For Unix-like systems, create symlink in /usr/local/bin
        bin_dir = Path("/usr/local/bin")
        if not bin_dir.exists():
            bin_dir.mkdir(parents=True)
        
        link_path = bin_dir / "zoompoller"
        if link_path.exists():
            link_path.unlink()
        
        os.symlink(script_path, link_path)
        print(f"✓ Created symlink in {link_path}")
        print("\nZoom Poll Automator installed successfully!")
        print("You can now use 'zoompoller' from anywhere.")

if __name__ == "__main__":
    install()