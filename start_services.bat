@echo off
set PYTHON=C:\Users\viper\AppData\Local\Programs\Python\Python311\python.exe
cd C:\Users\viper\gan-otg-db\viper-scripts
start "" /b %PYTHON% viper_llm_server.py > C:\Users\viper\gan-otg-db\viper_llm.log 2>&1
start "" /b %PYTHON% sovereign_loop.py --run > C:\Users\viper\gan-otg-db\sovereign.log 2>&1
cd C:\Users\viper\gan-otg-db
start "" /b %PYTHON% otg_db_bridge.py > C:\Users\viper\gan-otg-db\otg_bridge.log 2>&1
cd C:\Users\viper\gan-otg-db\ArchivalMoe
start "" /b %PYTHON% moe_server.py > C:\Users\viper\gan-otg-db\moe_server.log 2>&1
