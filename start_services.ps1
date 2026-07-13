$python = "C:\Users\viper\AppData\Local\Programs\Python\Python311\python.exe"
Start-Process $python -ArgumentList "C:\Users\viper\gan-otg-db\viper-scripts\viper_llm_server.py" -WindowStyle Hidden
Start-Process $python -ArgumentList "C:\Users\viper\gan-otg-db\otg_db_bridge.py" -WindowStyle Hidden
Start-Process $python -ArgumentList "C:\Users\viper\gan-otg-db\viper-scripts\sovereign_loop.py" -WindowStyle Hidden
Start-Process $python -ArgumentList "C:\Users\viper\gan-otg-db\ArchivalMoe\moe_server.py" -WindowStyle Hidden
