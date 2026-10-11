import socket
import json
import sys
import time

def check_service(port, service_name):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return {"port": port, "service": service_name, "up": result == 0}
    except Exception as e:
        return {"port": port, "service": service_name, "up": False, "error": str(e)}

def main():
    services = {
        "moe": 8765,
        "wave": 8788,
        "hexflow": 7766,
        "hive_brain": 8791,
        "ollama": 11434
    }
    
    for service, port in services.items():
        result = check_service(port, service)
        print(json.dumps(result))

if __name__ == "__main__":
    main()
