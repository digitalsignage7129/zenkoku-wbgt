import urllib.request
import json
from datetime import datetime, timezone, timedelta

# 気象庁予報API (大阪府: 270000)
URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/270000.json"
WEEK_DAYS = ["月", "火", "水", "木", "金", "土", "日"]

def get_weather_icon(text):
    if "晴" in text and "雨" in text:
        return "🌦️"
    elif "晴" in text and "曇" in text:
        return "⛅"
    elif "晴" in text:
        return "☀️"
    elif "雨" in text:
        return "🌧️"
    elif "雪" in text:
        return "☃️"
    elif "曇" in text:
        return "☁️"
    return "🌤️"

def fetch_3day_forecast():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # 短期予報(今日・明日・明後日)の取得
    time_series = data[0]["timeSeries"]
    
    # 1. 日付と天気
    dates_raw = time_series[0]["timeDefines"]
    weathers_raw = time_series[0]["areas"][0]["weathers"] # 大阪府の予報
    
    # 2. 降水確率
    pops_raw = time_series[1]["areas"][0]["pops"]
    
    # 3. 気温データ
    temps_raw = time_series[2]["areas"][0]["temps"]

    forecasts = []
    
    for i in range(min(3, len(dates_raw))):
        dt = datetime.fromisoformat(dates_raw[i])
        date_str = f"{dt.month}/{dt.day} ({WEEK_DAYS[dt.weekday()]})"
        
        weather_text = weathers_raw[i].replace(" ", "").replace("のち", "/").replace("時々", "/").replace("一時", "/")
        # 表示文字数が長すぎる場合の短縮処理
        if len(weather_text) > 5:
            weather_text = weather_text[:5]

        icon = get_weather_icon(weathers_raw[i])
        
        # 降水確率（最新枠を採用）
        pop = pops_raw[i] if i < len(pops_raw) else "0"
        
        # 気温 (今日・明日で要素数が変化するため安全に抽出)
        temp_low = None
        temp_high = None
        if i == 0 and len(temps_raw) >= 2:
            temp_high = temps_raw[1]
        elif i == 1 and len(temps_raw) >= 4:
            temp_low = temps_raw[2]
            temp_high = temps_raw[3]

        forecasts.append({
            "date_str": date_str,
            "weather": weather_text,
            "icon": icon,
            "pop": pop,
            "temp_high": temp_high,
            "temp_low": temp_low
        })

    result = {"forecasts": forecasts}

    with open("weather_3days.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("Successfully generated weather_3days.json")

if __name__ == "__main__":
    fetch_3day_forecast()
