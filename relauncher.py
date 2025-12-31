import os
import sys
import time
import subprocess

def relaunch(pid, executable, *args):
    # Wait for the original process to exit
    try:
        pid = int(pid)
        # Wait up to 5 seconds
        for _ in range(10):
            try:
                # Check if process exists
                os.kill(pid, 0) 
                time.sleep(0.5)
            except OSError:
                # Process is gone
                break
    except (ValueError, TypeError):
        pass
    except KeyboardInterrupt:
        # Ignore keyboard interrupt during wait
        pass

    # Launch the new process
    # We use subprocess.Popen to detach
    try:
        if executable.endswith("python.exe") or executable.endswith("pythonw.exe"):
             # Running as script
             cmd = [executable] + list(args)
        else:
             # Running as frozen exe
             cmd = [executable]
        
        # Creation flags for Windows to detach
        creationflags = 0x00000008 | 0x00000200 if os.name == 'nt' else 0 # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        
        subprocess.Popen(cmd, creationflags=creationflags, close_fds=True)
        
    except Exception as e:
        # If we can't log to stdout (since parent is dead), try writing to a file
        with open("relaunch_error.log", "w") as f:
            f.write(f"Failed to relaunch: {e}\nCmd: {cmd}")

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        # argv[1] is PID, argv[2] is executable, argv[3:] are args
        relaunch(sys.argv[1], sys.argv[2], *sys.argv[3:])
