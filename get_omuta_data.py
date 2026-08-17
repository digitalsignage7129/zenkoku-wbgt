import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone

headers = {"User-Agent": "Mozilla/5.0"}

# 大牟田市に最も近い総合観測所（久留米: 82056）を参照
WBGT_POINT = "82056"
AMEDAS_CODE = "82056"

wbgt_val = None
temp_val = "--"
hum_val = "--"
wind_val = "--"
weather_val = "--"

# 1. 環境省サイトから公式WBGT値を取得
try:
    moe_url = f"https://www.wbgt.env.go.jp/sp/graph_ref_td.php?region=10&prefecture=82&point={WBGT_POINT}"
    req = urllib.request.Request(moe_url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
        matches = re.findall(
            r">(1[5-9]\.[0-9]|2[0-9]\.[0-9]|3[0-9]\.[0-9])<", html
        )
        if matches:
            wbgt_val = matches[0]
except Exception as e:
    print(f"MOE fetch warning: {e}")

# 2. 気象庁アメダスから実測データを取得
try:
    req_time = urllib.request.Request(
        "https://www.jma.go.jp/bosai/amedas/data/latest_time.txt",
        headers=headers,
    )
    with urllib.request.urlopen(req_time, timeout=10) as resp:
        latest_time = resp.read().decode("utf-8").strip()
        formatted_time = re.sub(r"[-:+T]", "", latest_time)[:14]

    jma_url = (
        f"https://www.jma.go.jp/bosai/amedas/data/map/{formatted_time}.json"
    )
    req_map = urllib.request.Request(jma_url, headers=headers)
    with urllib.request.urlopen(req_map, timeout=10) as resp:
        map_data = json.loads(resp.read().decode("utf-8"))
        obs_data = map_data.get(AMEDAS_CODE, {})

        # 気温
        if "temp" in obs_data and obs_data["temp"] and obs_data["temp"][0] is not None:
            temp_val = f"{float(obs_data['temp'][0]):.1f}"

        # 湿度
        if "humidity" in obs_data and obs_data["humidity"] and obs_data["humidity"][0] is not None:
            hum_val = str(int(obs_data["humidity"][0]))

        # 風速
        if "wind" in obs_data and obs_data["wind"] and obs_data["wind"][0] is not None:
            wind_val = f"{float(obs_data['wind'][0]):.1f}"

        # 天気判定（10分降水量 / 10分日照時間）
        if obs_data:
            precip = obs_data.get("precipitation10m", [0])[0] or 0
            sun = obs_data.get("sun10m", [0])[0] or 0

            if precip >= 0.5:
                weather_val = "雨"
            elif sun >= 0.1:
                weather_val = "晴れ"
            else:
                weather_val = "くもり"

except Exception as e:
    print(f"JMA fetch warning: {e}")

# 警戒度の判定
level = "--"
if wbgt_val:
    w = float(wbgt_val)
    if w >= 31.0:
        level = "危険"
    elif w >= 28.0:
        level = "厳重警戒"
    elif w >= 25.0:
        level = "警戒"
    elif w >= 21.0:
        level = "留意"
    else:
        level = "ほぼ安全"

# JSON出力
jst = timezone(timedelta(hours=9))
now_str = datetime.now(jst).strftime("%Y-%m-%d %H:%M")

result = {
    "location": "福岡県大牟田市",
    "wbgt": str(wbgt_val) if wbgt_val else "--",
    "level": level,
    "temperature": temp_val,
    "humidity": hum_val,
    "wind_speed": wind_val,
    "weather": weather_val,
    "updated_at": now_str,
}

with open("omuta_wbgt.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print("Generated JSON:", json.dumps(result, ensure_ascii=False))
