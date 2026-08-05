import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone

headers = {"User-Agent": "Mozilla/5.0"}

# 長野県（200000）の予報データ取得
url = "https://www.jma.go.jp/bosai/forecast/data/forecast/200000.json"
req = urllib.request.Request(url, headers=headers)

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # --- 1. 天気と降水確率の抽出（長野県北部: 200020） ---
    time_series = data[0]["timeSeries"]
    
    # 北部エリアのインデックス特定
    area_idx = 0
    for i, a in enumerate(time_series[0]["areas"]):
        if a["area"]["code"] == "200020":  # 長野県北部
            area_idx = i
            break

    weathers = time_series[0]["areas"][area_idx].get("weathers", ["--", "--", "--"])
    pops = time_series[1]["areas"][area_idx].get("pops", ["--"])

    # 天気文字列の整形（全角スペース除去など）
    w_today = weathers[0].replace(" ", " ") if len(weathers) > 0 else "--"
    w_tomorrow = weathers[1].replace(" ", " ") if len(weathers) > 1 else "--"
    w_day_after = weathers[2].replace(" ", " ") if len(weathers) > 2 else "--"

    # 代表降水確率の取得
    pop_today = pops[0] if len(pops) > 0 else "--"
    pop_tomorrow = pops[min(4, len(pops)-1)] if len(pops) > 1 else "--"
    pop_day_after = pops[-1] if len(pops) > 2 else "--"

    # --- 2. 気温データの抽出 ---
    # 白馬（48141）または長野の予想気温
    temp_today_max, temp_today_min = "--", "--"
    temp_tomorrow_max, temp_tomorrow_min = "--", "--"
    temp_day_after_max, temp_day_after_min = "--", "--"

    if len(data) > 1 and "timeSeries" in data[1]:
        temp_series = data[1]["timeSeries"]
        if len(temp_series) > 1:
            temps_area = temp_series[1]["areas"][0] # 長野エリア代表気温
            temps = temps_area.get("temps", [])
            if len(temps) >= 2:
                temp_tomorrow_min = temps[0]
                temp_tomorrow_max = temps[1]

    # --- 3. JSONデータ整形 ---
    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime("%Y-%m-%d %H:%M")

    result = {
        "location": "長野県白馬村",
        "updated_at": now_str,
        "today": {
            "weather": w_today,
            "temp_max": temp_today_max,
            "temp_min": temp_today_min,
            "pop": pop_today
        },
        "tomorrow": {
            "weather": w_tomorrow,
            "temp_max": temp_tomorrow_max,
            "temp_min": temp_tomorrow_min,
            "pop": pop_tomorrow
        },
        "day_after": {
            "weather": w_day_after,
            "temp_max": temp_day_after_max,
            "temp_min": temp_day_after_min,
            "pop": pop_day_after
        }
    }

    with open("hakuba_tenki.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("hakuba_tenki.json を正常に生成しました。")

except Exception as e:
    print(f"Error generating forecast JSON: {e}")
