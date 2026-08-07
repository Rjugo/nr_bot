import os
import httpx
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("🔍 ТЕСТ 1: Прямое подключение к Supabase (БЕЗ прокси)")

try:
    # Пробуем без прокси, с отключенным SSL
    client = httpx.Client(verify=False, timeout=10.0)
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    supabase._http_client = client

    result = supabase.table("pedagogs").select("*").execute()
    print(f"✅ УСПЕШНО! Найдено педагогов: {len(result.data)}")
    for p in result.data:
        print(f"  - {p['name']}")

except Exception as e:
    print(f"❌ ОШИБКА: {e}")