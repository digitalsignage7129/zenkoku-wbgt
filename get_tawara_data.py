import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# 田原本町周辺の公式WBGT・気象観測点（奈良：64011）
AMEDAS_CODE = "64011"
MOE_POINT = "64011"
REGION_CODE = "06"  # 近畿
PREF_CODE = "64"    # 奈良県

jst = timezone(timedelta(hours=9))
now_jst = datetime.now(jst)

# 1. 気象庁アメダスから実測値を取得
temp_val, hum_val, wind_val, weather_val = None, None, None, "不明"

for minutes_back in [10, 20, 30]:
    target_time = now_jst - timedelta(minutes=minutes_back)
    minute = (target_time.minute // 10) * 10
    time_str = target_time.strftime(f"%Y%m%d%H{minute:02d}00")

    jma_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_str}.json"
    try:
        req = urllib.request.Request(jma_url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if AMEDAS_CODE in data:
                obs = data[AMEDAS_CODE]

                if "temp" in obs and obs["temp"] and obs["temp"][0] is not None:
                    temp_val = f"{float(obs['temp'][0]):.1f}"
                if "humidity" in obs and obs["humidity"] and obs["humidity"][0] is not None:
                    hum_val = str(int(obs["humidity"][0]))
                if "wind" in obs and obs["wind"] and obs["wind"][0] is not None:
                    wind_val = f"{float(obs['wind'][0]):.1f}"

                precip = obs.get("precipitation10m", [0])[0] or 0
                sun = obs.get("sun10m", [0])[0] or 0

                if precip >= 0.5:
                    weather_val = "雨"
                elif sun >= 0.1:
                    weather_val = "晴れ"
                else:
                    weather_val = "くもり"
                break
    except Exception:
        continue

# 2. 環境省サイトからWBGT値を直接取得
wbgt_val = None
moe_url = f"https://www.wbgt.env.go.jp/sp/graph_ref_td.php?region={REGION_CODE}&prefecture={PREF_CODE}&point={MOE_POINT}"

try:
    req = urllib.request.Request(moe_url, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
        matches = re.findall(r"(\d{2}\.\d)", html)
        valid_wbgt = [m for m in matches if 10.0 <= float(m) <= 40.0]
        if valid_wbgt:
            wbgt_val = valid_wbgt[-1]
except Exception as e:
    print(f"MOE fetch error: {e}")

# 3. 警戒度判定
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

# 4. JSON出力
result = {
    "location": "奈良県田原本町",
    "wbgt": str(wbgt_val) if wbgt_val else "--",
    "level": level,
    "temperature": str(temp_val) if temp_val else "--",
    "humidity": str(hum_val) if hum_val else "--",
    "wind_speed": str(wind_val) if wind_val else "--",
    "weather": weather_val,
    "updated_at": now_jst.strftime("%Y-%m-%d %H:%M"),
}

with open("tawaramoto_wbgt.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print("Generated JSON:\n", json.dumps(result, ensure_ascii=False, indent=2))
