import json
import re
import ssl
import urllib.request
from datetime import datetime, timedelta, timezone

# 奈良県の天気予報JSON
JMA_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/290000.json"
# 奈良県北部（田原本町・奈良市エリア）
AREA_CODE = "290010"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# SSL検証エラー対策
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

WEATHER_CODE_MAP = {
    "100": "晴れ",
    "101": "晴れ時々くもり",
    "102": "晴れ一時雨",
    "103": "晴れ時々雨",
    "110": "晴れ時々くもり",
    "200": "くもり",
    "201": "くもり時々晴れ",
    "202": "くもり一時雨",
    "203": "くもり時々雨",
    "300": "雨",
    "301": "雨時々晴れ",
    "302": "雨時々くもり",
    "400": "雪",
    "401": "雪時々晴れ",
    "402": "雪時々くもり",
}

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]


def clean_weather_text(text):
    if not text:
        return "--"
    cleaned = re.sub(r"[\s\u3000]+", " ", text).strip()
    return cleaned.split("所により")[0].strip()


def get_jma_weather():
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    is_after_17 = now.hour >= 17  # 17時以降判定

    req = urllib.request.Request(JMA_URL, headers=HEADERS)
    with urllib.request.urlopen(req, context=ssl_context, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    short_term = data[0] if len(data) > 0 else {}
    weekly = data[1] if len(data) > 1 else {}

    result = {
        "location": "奈良県田原本町",
        "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        "is_night_mode": is_after_17,
        "day1": {
            "label": "",
            "date": "",
            "weather": "--",
            "temp_max": "--",
            "temp_min": "--",
            "pop": "--",
        },
        "day2": {
            "label": "",
            "date": "",
            "weather": "--",
            "temp_max": "--",
            "temp_min": "--",
            "pop": "--",
        },
        "day3": {
            "label": "",
            "date": "",
            "weather": "--",
            "temp_max": "--",
            "temp_min": "--",
            "pop": "--",
        },
    }

    # 日付ラベルと基準日の計算
    base_date = now if not is_after_17 else now + timedelta(days=1)
    labels = (
        ["今日", "明日", "明後日"]
        if not is_after_17
        else ["明日", "明後日", "明々後日"]
    )

    for idx, key in enumerate(["day1", "day2", "day3"]):
        target_date = base_date + timedelta(days=idx)
        w_str = WEEKDAYS[target_date.weekday()]
        result[key]["label"] = labels[idx]
        result[key]["date"] = f"{target_date.month}/{target_date.day}({w_str})"

    # --- 1. 週間予報（data[1]）から抽出 ---
    if "timeSeries" in weekly:
        ts_week0 = weekly["timeSeries"][0]
        ts_week1 = weekly["timeSeries"][1] if len(weekly["timeSeries"]) > 1 else {}

        # 奈良県北部のエリアインデックス特定
        area_idx = 0
        for i, a in enumerate(ts_week0.get("areas", [])):
            if a.get("area", {}).get("code") == AREA_CODE:
                area_idx = i
                break

        area_data_w0 = ts_week0["areas"][area_idx]
        area_data_w1 = (
            ts_week1.get("areas", [])[0] if ts_week1.get("areas") else {}
        )

        codes = area_data_w0.get("weatherCodes", [])
        pops = area_data_w0.get("pops", [])
        mins = area_data_w1.get("tempsMin", [])
        maxs = area_data_w1.get("tempsMax", [])

        # 17時以降の場合は週間予報のインデックスをシフト
        start_offset = 0 if not is_after_17 else 1

        for i, key in enumerate(["day1", "day2", "day3"]):
            w_idx = start_offset + i
            if w_idx < len(codes) and codes[w_idx]:
                result[key]["weather"] = WEATHER_CODE_MAP.get(
                    codes[w_idx], "くもり"
                )
            if w_idx < len(pops) and pops[w_idx]:
                result[key]["pop"] = str(pops[w_idx])
            if w_idx < len(mins) and mins[w_idx]:
                result[key]["temp_min"] = str(mins[w_idx])
            if w_idx < len(maxs) and maxs[w_idx]:
                result[key]["temp_max"] = str(maxs[w_idx])

    # --- 2. 17時前で短期詳細予報（data[0]）が使える場合はテキストと気温を上書き ---
    if not is_after_17 and "timeSeries" in short_term:
        ts0 = short_term["timeSeries"][0]
        area_idx_s = 0
        for i, a in enumerate(ts0.get("areas", [])):
            if a.get("area", {}).get("code") == AREA_CODE:
                area_idx_s = i
                break

        weathers = ts0["areas"][area_idx_s].get("weathers", [])
        if len(weathers) > 0:
            result["day1"]["weather"] = clean_weather_text(weathers[0])
        if len(weathers) > 1:
            result["day2"]["weather"] = clean_weather_text(weathers[1])

        # 気温（短期）
        if len(short_term["timeSeries"]) > 2:
            temps = short_term["timeSeries"][2]["areas"][0].get("temps", [])
            if len(temps) >= 4:
                result["day1"]["temp_min"] = temps[0]
                result["day1"]["temp_max"] = temps[1]
                result["day2"]["temp_min"] = temps[2]
                result["day2"]["temp_max"] = temps[3]

    # JSON書き出し
    with open("tawaramoto_tenki.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("tawaramoto_tenki.json を正常に生成しました:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    get_jma_weather()
