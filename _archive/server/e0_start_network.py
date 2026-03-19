"""Wrapper to start orchestrator with correct environment.
Run with: python e0_start_network.py [--port PORT]
"""
import subprocess, sys, os

PYTHON = r"C:\Users\Thoma\AppData\Local\Programs\Python\Python311\python.exe"

def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    cmd = [PYTHON, "-u", 
           os.path.join(project_dir, "e0_init_v3_orchestrator.py")] + args
    
    print(f"Starting: {' '.join(cmd)}")
    sys.stdout.flush()
    
    result = subprocess.run(cmd, cwd=project_dir)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
