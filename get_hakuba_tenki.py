import json
import urllib.request
from datetime import datetime, timedelta, timezone

# 長野県白馬村の緯度・経度
LAT = 36.6983
LON = 137.8619

# 気象庁（JMA）モデルのデータを取得するWeb API
URL = (
    f"https://api.open-meteo.com/v1/forecast?"
    f"latitude={LAT}&longitude={LON}"
    f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
    f"&timezone=Asia%2FTokyo"
    f"&models=jma_seamless"
)

HEADERS = {"User-Agent": "Mozilla/5.0"}

# 天気コードから日本語表記への変換表
WEATHER_MAP = {
    0: "晴れ",
    1: "晴れ時々くもり",
    2: "晴れ時々くもり",
    3: "くもり",
    45: "霧",
    48: "霧",
    51: "小雨",
    53: "雨",
    55: "大雨",
    56: "雨",
    57: "雨",
    61: "雨",
    63: "雨",
    65: "大雨",
    66: "雨",
    67: "雨",
    71: "みぞれ・小雪",
    73: "雪",
    75: "大雪",
    77: "雪",
    80: "にわか雨",
    81: "にわか雨",
    82: "激しい雨",
    85: "にわか雪",
    86: "にわか雪",
    95: "雷雨",
    96: "雷雨",
    99: "雷雨",
}


def safe_get(arr, idx, default="--"):
    """配列から安全に値を取り出す"""
    try:
        val = arr[idx]
        if val is None:
            return default
        return val
    except Exception:
        return default


def format_temp(val):
    if val == "--":
        return "--"
    try:
        return str(round(float(val)))
    except Exception:
        return "--"


def format_pop(val):
    if val == "--":
        return "--"
    try:
        # 降水確率は10%刻みに整形
        return str(int(round(float(val) / 10.0) * 10))
    except Exception:
        return "--"


def get_weather():
    result = {
        "location": "長野県白馬村",
        "updated_at": "",
        "today": {"weather": "--", "temp_max": "--", "temp_min": "--", "pop": "--"},
        "tomorrow": {
            "weather": "--",
            "temp_max": "--",
            "temp_min": "--",
            "pop": "--",
        },
        "day_after": {
            "weather": "--",
            "temp_max": "--",
            "temp_min": "--",
            "pop": "--",
        },
    }

    try:
        req = urllib.request.Request(URL, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        daily = data.get("daily", {})
        codes = daily.get("weather_code", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        pops = daily.get("precipitation_probability_max", [])

        keys = ["today", "tomorrow", "day_after"]
        for i, key in enumerate(keys):
            code = safe_get(codes, i)
            result[key]["weather"] = (
                WEATHER_MAP.get(code, "くもり") if code != "--" else "--"
            )
            result[key]["temp_max"] = format_temp(safe_get(max_temps, i))
            result[key]["temp_min"] = format_temp(safe_get(min_temps, i))
            result[key]["pop"] = format_pop(safe_get(pops, i))

    except Exception as e:
        print(f"データ取得エラー (安全なデフォルト値で書き出します): {e}")

    # JST時刻設定
    jst = timezone(timedelta(hours=9))
    result["updated_at"] = datetime.now(jst).strftime("%Y-%m-%d %H:%M")

    # JSON書き出し
    with open("hakuba_tenki.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("hakuba_tenki.json を更新しました:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    get_weather()
