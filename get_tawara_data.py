import json
import re
import ssl
import urllib.request
from datetime import datetime, timedelta, timezone

# ブラウザリクエストの完全擬態ヘッダー
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,json;q=0.8,*/*;q=0.8",
    "Referer": "https://www.jma.go.jp/",
}

# SSLエラー回避設定
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 【精査済み】田原本町周辺の全項目対応観測点：奈良（64011）
AMEDAS_CODE = "64011"
MOE_POINT = "64011"
REGION_CODE = "06"  # 近畿
PREF_CODE = "64"    # 奈良県

jst = timezone(timedelta(hours=9))
now_jst = datetime.now(jst)

temp_val, hum_val, wind_val, weather_val = None, None, None, "不明"

# 1. 気象庁アメダスから最新確定データを取得
try:
    # 気象庁の「最新確定時刻インデックス」を叩く
    latest_time_url = "https://www.jma.go.jp/bosai/amedas/data/latest_time.json"
    req_time = urllib.request.Request(latest_time_url, headers=headers)
    
    with urllib.request.urlopen(req_time, context=ssl_context, timeout=10) as resp:
        raw_time = json.loads(resp.read().decode("utf-8"))
        # Format: "2026-08-17T16:50:00+09:00" -> "20260817165000"
        time_str = raw_time.replace("-", "").replace("T", "").replace(":", "").replace("+09:00", "")

    # 確定時刻のJSONを取得
    jma_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_str}.json"
    req_map = urllib.request.Request(jma_url, headers=headers)
    
    with urllib.request.urlopen(req_map, context=ssl_context, timeout=10) as resp:
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
            print(f"JMA Success: Fetched data from {time_str}")

except Exception as e:
    print(f"JMA Fetch Error: {e}")

# 2. 環境省サイトから奈良（64011）の公式WBGT値を直接取得
wbgt_val = None
moe_url = f"https://www.wbgt.env.go.jp/sp/graph_ref_td.php?region={REGION_CODE}&prefecture={PREF_CODE}&point={MOE_POINT}"

try:
    req_moe = urllib.request.Request(moe_url, headers=headers)
    with urllib.request.urlopen(req_moe, context=ssl_context, timeout=10) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
        matches = re.findall(r"(\d{2}\.\d)", html)
        valid_wbgt = [m for m in matches if 10.0 <= float(m) <= 40.0]
        if valid_wbgt:
            wbgt_val = valid_wbgt[-1]
            print(f"MOE Success: WBGT = {wbgt_val}")
except Exception as e:
    print(f"MOE Fetch Error: {e}")

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
