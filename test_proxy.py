import httpx

proxy_url = "socks5://127.0.0.1:12334"

print("🔍 Проверка прокси для HTTPS...")

try:
    # Пробуем через прокси подключиться к HTTPS сайту (не Supabase)
    with httpx.Client(proxy=proxy_url, timeout=10.0) as client:
        response = client.get("https://httpbin.org/get")
        print(f"✅ Прокси работает для HTTPS! Статус: {response.status_code}")
        print(f"IP: {response.json().get('origin')}")
except Exception as e:
    print(f"❌ Прокси НЕ работает для HTTPS: {e}")

print("\n" + "="*50 + "\n")

print("🔍 Проверка прокси для Supabase...")
try:
    # Пробуем через прокси подключиться к Supabase
    with httpx.Client(proxy=proxy_url, verify=False, timeout=10.0) as client:
        response = client.get("https://alafwqeezmzmanowrjpvm.supabase.co/rest/v1/")
        print(f"✅ Supabase доступен! Статус: {response.status_code}")
except Exception as e:
    print(f"❌ Supabase НЕ доступен через прокси: {e}")