import requests

API_URL = "https://student.namspi.uz/rest/v1/data/employee-list"
TOKEN = "t9MPsdyX_oGFeUbpTxdL9Yy10V_8_Je6"

HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}

def fetch_employees_from_api(page=1):
    """ 📥 API'dan hodimlarni yuklash """
    try:
        response = requests.get(f"{API_URL}?type=all&page={page}", headers=HEADERS, timeout=15)
        response.raise_for_status()
        response_data = response.json()

        if not response_data.get("success"):
            print("API", "❌ API muvaffaqiyatsiz javob berdi!")
            return None, 0

        data = response_data.get("data", {})
        return data.get("items", []), data.get("pagination", {}).get("totalCount", 0)

    except requests.exceptions.RequestException as e:
        print("API", f"❌ API so‘rovda xatolik: {e}")
        return None, 0


