import os
import httpx
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("🔍 ТЕСТ 2: Подключение к Supabase через HTTP (без SSL)")

try:
    # Меняем https на http
    http_url = SUPABASE_URL.replace("https://", "http://")
    print(f"Пробуем подключиться к: {http_url}")

    client = httpx.Client(verify=False, timeout=10.0)
    supabase = create_client(http_url, SUPABASE_KEY)
    supabase._http_client = client

    result = supabase.table("pedagogs").select("*").execute()
    print(f"✅ УСПЕШНО! Найдено педагогов: {len(result.data)}")
    for p in result.data:
        print(f"  - {p['name']}")

except Exception as e:
    print(f"❌ ОШИБКА: {e}")