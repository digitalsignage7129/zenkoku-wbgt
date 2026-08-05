import json
import urllib.request
from datetime import datetime, timedelta, timezone

# 白馬村のピンポイント座標（緯度・経度）
LAT = 36.6983
LON = 137.8619

# Open-Meteo API（今日・明日・明後日の天気コード、最高/最低気温、降水確率を取得）
url = (
    f"https://api.open-meteo.com/v1/forecast?"
    f"latitude={LAT}&longitude={LON}"
    f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
    f"&timezone=Asia%2FTokyo"
)

def get_weather_text(code):
    """Open-MeteoのWMO天気コードをサイネージ用の簡潔な和名に変換"""
    if code == 0:
        return "晴れ"
    elif code in [1, 2]:
        return "晴れ時々くもり"
    elif code == 3:
        return "くもり"
    elif code in [45, 48]:
        return "霧"
    elif code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]:
        return "雨"
    elif code in [71, 73, 75, 77, 85, 86]:
        return "雪"
    elif code in [95, 96, 99]:
        return "雷雨"
    else:
        return "くもり"

req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    daily = data.get("daily", {})
    codes = daily.get("weather_code", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    pops = daily.get("precipitation_probability_max", [])

    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime("%Y-%m-%d %H:%M")

    result = {
        "location": "長野県白馬村",
        "updated_at": now_str,
        "today": {
            "weather": get_weather_text(codes[0]),
            "temp_max": str(round(max_temps[0])),
            "temp_min": str(round(min_temps[0])),
            "pop": str(pops[0]) if pops[0] is not None else "0"
        },
        "tomorrow": {
            "weather": get_weather_text(codes[1]),
            "temp_max": str(round(max_temps[1])),
            "temp_min": str(round(min_temps[1])),
            "pop": str(pops[1]) if pops[1] is not None else "0"
        },
        "day_after": {
            "weather": get_weather_text(codes[2]),
            "temp_max": str(round(max_temps[2])),
            "temp_min": str(round(min_temps[2])),
            "pop": str(pops[2]) if pops[2] is not None else "0"
        }
    }

    with open("hakuba_tenki.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("hakuba_tenki.json を正常に生成しました:")
    print(json.dumps(result, ensure_ascii=False, indent=2))

except Exception as e:
    print(f"Open-Meteo fetch error: {e}")
