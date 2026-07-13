import subprocess
import os

python_exe = r"C:\Users\viper\AppData\Local\Programs\Python\Python311\python.exe"

services = [
    [r"C:\Users\viper\gan-otg-db\viper-scripts\viper_llm_server.py"],
    [r"C:\Users\viper\gan-otg-db\otg_db_bridge.py"],
    [r"C:\Users\viper\gan-otg-db\viper-scripts\sovereign_loop.py", "--run"],
    [r"C:\Users\viper\gan-otg-db\ArchivalMoe\moe_server.py"]
]

for s in services:
    cwd = os.path.dirname(s[0])
    subprocess.Popen([python_exe] + s, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.DETACHED_PROCESS)
