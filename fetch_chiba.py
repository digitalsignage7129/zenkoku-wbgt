from datetime import datetime, timezone, timedelta
import io
import csv
import json
import re
import requests

JST = timezone(timedelta(hours=9))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.wbgt.env.go.jp/"
}

MOE_TARGET_ID = "45112"  # 環境省：千葉
JMA_TARGET_ID = "45212"  # 気象庁：千葉

def get_chiba_wbgt():
    """環境省のCSVから千葉のWBGTを取得する"""
    now_jst = datetime.now(JST)
    ym = now_jst.strftime("%Y%m")
    
    candidate_urls = [
        f"https://www.wbgt.env.go.jp/est15WG/dl/wbgt_all_{ym}.csv",
        "https://www.wbgt.env.go.jp/est1570/dl/wbgt_dl.csv",
        "https://www.wbgt.env.go.jp/data/wbgt_dl.csv"
    ]
    
    content = None
    for url in candidate_urls:
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code == 200 and len(res.content) > 100:
                content = res.content.decode("shift_jis")
                break
        except Exception:
            continue
            
    if not content:
        return None, "不明", "データ取得エラー"

    reader = csv.reader(io.StringIO(content))
    for row in reader:
        if not row or row[0].startswith("#"):
            continue
        if row[0].strip() == MOE_TARGET_ID:
            try:
                raw_val = float(row[3] if len(row) >= 4 else row[1])
                wbgt = round(raw_val / 10.0, 1) if raw_val > 50 else round(raw_val, 1)
                
                if wbgt < 21.0: level = "ほぼ安全"
                elif wbgt < 25.0: level = "留意"
                elif wbgt_val < 28.0: level = "警戒" if 'wbgt_val' else "警戒"
                elif wbgt < 28.0: level = "警戒"
                elif wbgt < 31.0: level = "厳重警戒"
                else: level = "危険"
                
                return wbgt, level, now_jst.strftime("%Y-%m-%d %H:00")
            except ValueError:
                pass
    return None, "不明", "データなし"

def get_chiba_jma():
    """気象庁から千葉の気温・湿度・風速を取得する"""
    try:
        time_res = requests.get("https://www.jma.go.jp/bosai/amedas/data/latest_time.txt", headers=HEADERS, timeout=10)
        raw_time = time_res.text.strip()
        formatted_time = re.sub(r'[-:+T]', '', raw_time)[:14]
    except Exception:
        formatted_time = datetime.now(JST).replace(minute=0, second=0, microsecond=0).strftime("%Y%m%d%H0000")

    jma_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{formatted_time}.json"
    res = requests.get(jma_url, headers=HEADERS, timeout=10)
    data = res.json().get(JMA_TARGET_ID, {})

    def parse_val(key, div=False):
        val_list = data.get(key)
        if val_list and val_list[0] is not None:
            v = float(val_list[0])
            return round(v / 10.0, 1) if div else v
        return None

    return {
        "temperature": parse_val("temp", True),
        "humidity": parse_val("humidity", False),
        "wind_speed": parse_val("wind", True)
    }

def main():
    wbgt, level, updated = get_chiba_wbgt()
    jma_data = get_chiba_jma()

    output = {
        "location": "新港清掃工場（周辺：千葉）",
        "wbgt": wbgt,
        "level": level,
        "updated_at": updated,
        "temperature": jma_data["temperature"],
        "humidity": jma_data["humidity"],
        "wind_speed": jma_data["wind_speed"]
    }

    with open("chiba_wbgt.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("✅ chiba_wbgt.json updated successfully.")

if __name__ == "__main__":
    main()
