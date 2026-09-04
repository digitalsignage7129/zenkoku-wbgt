import json
import re
import ssl
import urllib.request
from datetime import datetime, timedelta, timezone

# 広島県の天気予報JSON
JMA_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/340000.json"
# 南部（広島市が属する天気予報区分。右帯テンプレートと同じ根拠で採用）
AREA_CODE = "340010"
# 広島観測所（広島市そのものの気温予測拠点。右帯テンプレートと同じ根拠で採用）
TEMP_CODE = "67437"
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
    cleaned = re.sub(r"[\s　]+", " ", text).strip()
    return cleaned.split("所により")[0].strip()


def find_area(areas, codes):
    """area.code が codes(優先順)のいずれかに一致する要素を返す。
    見つからなければ先頭要素にフォールバックする。"""
    if not areas:
        return {}
    for code in codes:
        for a in areas:
            if a.get("area", {}).get("code") == code:
                return a
    return areas[0]


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
        "location": "広島県広島市",
        "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        "is_night_mode": is_after_17,
        "day1": {"label": "", "date": "", "weather": "--", "temp_max": "--", "temp_min": "--", "pop": "--"},
        "day2": {"label": "", "date": "", "weather": "--", "temp_max": "--", "temp_min": "--", "pop": "--"},
        "day3": {"label": "", "date": "", "weather": "--", "temp_max": "--", "temp_min": "--", "pop": "--"},
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

        area_data_w0 = find_area(ts_week0.get("areas", []), [AREA_CODE])
        area_data_w1 = find_area(ts_week1.get("areas", []), [TEMP_CODE, AREA_CODE])

        codes = area_data_w0.get("weatherCodes", [])
        pops = area_data_w0.get("pops", [])
        mins = area_data_w1.get("tempsMin", [])
        maxs = area_data_w1.get("tempsMax", [])

        start_offset = 0 if not is_after_17 else 1
        for i, key in enumerate(["day1", "day2", "day3"]):
            w_idx = start_offset + i
            if w_idx < len(codes) and codes[w_idx]:
                result[key]["weather"] = WEATHER_CODE_MAP.get(codes[w_idx], "くもり")
            if w_idx < len(pops) and pops[w_idx]:
                result[key]["pop"] = str(pops[w_idx])
            if w_idx < len(mins) and mins[w_idx]:
                result[key]["temp_min"] = str(mins[w_idx])
            if w_idx < len(maxs) and maxs[w_idx]:
                result[key]["temp_max"] = str(maxs[w_idx])

    # --- 2. 17時前で短期詳細予報（data[0]）が使える場合は上書き ---
    if not is_after_17 and "timeSeries" in short_term:
        ts0 = short_term["timeSeries"][0]
        area_s0 = find_area(ts0.get("areas", []), [AREA_CODE])
        weathers = area_s0.get("weathers", [])
        if len(weathers) > 0:
            result["day1"]["weather"] = clean_weather_text(weathers[0])
        if len(weathers) > 1:
            result["day2"]["weather"] = clean_weather_text(weathers[1])

        # 降水確率の補完（直近の値を取得）
        if len(short_term["timeSeries"]) > 1:
            area_s1 = find_area(short_term["timeSeries"][1].get("areas", []), [AREA_CODE])
            s_pops = area_s1.get("pops", [])
            valid_pops = [p for p in s_pops if p != ""]
            if valid_pops:
                result["day1"]["pop"] = str(valid_pops[0])

        # 気温の取得（TEMP_CODEの地点を明示的に指定。昼以降に最高・最低が
        # 重複するのを防ぐ処理も踏襲）
        if len(short_term["timeSeries"]) > 2:
            area_s2 = find_area(short_term["timeSeries"][2].get("areas", []), [TEMP_CODE, AREA_CODE])
            temps = area_s2.get("temps", [])
            if len(temps) >= 4:
                result["day1"]["temp_min"] = str(temps[0])
                result["day1"]["temp_max"] = str(temps[1])
                result["day2"]["temp_min"] = str(temps[2])
                result["day2"]["temp_max"] = str(temps[3])
            elif len(temps) >= 2:
                result["day1"]["temp_max"] = str(temps[0])
                result["day2"]["temp_min"] = str(temps[1])

    # 昼以降で今日の最高・最低が同じになってしまった場合の補正（最低を"--"にする）
    if result["day1"]["temp_min"] == result["day1"]["temp_max"]:
        result["day1"]["temp_min"] = "--"

    # JSON書き出し
    with open("hiroshima_tenki.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("hiroshima_tenki.json を正常に生成しました:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    get_jma_weather()
