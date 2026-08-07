import socket

def check_port(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

print("🔍 Проверка портов:")
for port in [1080, 12334, 2080, 8080, 9050]:
    if check_port(port):
        print(f"✅ ПОРТ {port} - ОТКРЫТ")
    else:
        print(f"❌ ПОРТ {port} - ЗАКРЫТ")