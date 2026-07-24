from datetime import datetime, timezone, timedelta
import io
import csv
import json
import requests

JST = timezone(timedelta(hours=9))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ------------------------------------------------------------------
# 環境省ID と 気象庁アメダスID が異なる場合の例外マッピング
# ------------------------------------------------------------------
ID_EXCEPTIONS = {
    "45112": "45212",  # 千葉
}

def parse_jma_value(data_dict: dict, key: str, is_divide_10: bool = False):
    """気象庁JSONの特殊構造から安全に値を取り出す"""
    if not isinstance(data_dict, dict) or key not in data_dict:
        return None
    val_list = data_dict[key]
    if isinstance(val_list, list) and len(val_list) > 0:
        raw_val = val_list[0]
        if raw_val is None:
            return None
        try:
            val = float(raw_val)
            if is_divide_10:
                val = round(val / 10.0, 1)
            return val
        except (ValueError, TypeError):
            return None
    return None

def fetch_moe_wbgt_all() -> dict:
    """環境省の公式CSVから最新の全地点WBGTを取得する"""
    url = "https://www.wbgt.env.go.jp/est1570/dl/wbgt_dl.csv"
    print(f"Fetching MoE WBGT CSV from: {url}")
    
    res = requests.get(url, headers=HEADERS, timeout=10)
    res.raise_for_status()

    try:
        content = res.content.decode("shift_jis")
    except UnicodeDecodeError:
        content = res.content.decode("utf-8-sig")

    parsed = {}
    reader = csv.reader(io.StringIO(content))
    for row in reader:
        if not row or len(row) < 4 or row[0].startswith("#"):
            continue

        station_code = row[0].strip()
        date_str = row[1].strip()
        time_str = row[2].strip()
        raw_val = row[3].strip()

        try:
            wbgt_val = float(raw_val)
            if wbgt_val > 50:
                wbgt_val = round(wbgt_val / 10.0, 1)
        except ValueError:
            continue

        if wbgt_val < 21.0: level = "ほぼ安全"
        elif wbgt_val < 25.0: level = "留意"
        elif wbgt_val < 28.0: level = "警戒"
        elif wbgt_val < 31.0: level = "厳重警戒"
        else: level = "危険"

        formatted_time = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str.zfill(2)[:2]}:00"
        parsed[station_code] = {
            "wbgt": wbgt_val,
            "level": level,
            "updated_at": formatted_time
        }
    return parsed

def fetch_jma_amedas_latest() -> dict:
    """気象庁の最新アメダス実測値を取得する"""
    now_jst = datetime.now(JST)
    target_time = now_jst.replace(minute=0, second=0, microsecond=0)
    time_str = target_time.strftime("%Y%m%d%H0000")
    
    url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_str}.json"
    print(f"Fetching JMA AMeDAS data from: {url}")
    
    res = requests.get(url, headers=HEADERS, timeout=10)
    if res.status_code == 404:
        prev_time = target_time - timedelta(hours=1)
        time_str = prev_time.strftime("%Y%m%d%H0000")
        url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_str}.json"
        print(f"Fallback to previous hour: {url}")
        res = requests.get(url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    return res.json()

def main():
    # 1. 気象庁マスター取得
    master_url = "https://www.jma.go.jp/bosai/amedas/const/amedastable.json"
    res = requests.get(master_url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    station_master = res.json()

    # 2. 環境省 WBGTデータ取得
    moe_data = fetch_moe_wbgt_all()

    # 3. 気象庁 アメダス実測値取得
    jma_amedas = fetch_jma_amedas_latest()

    # 4. マージ処理（環境省WBGT ＋ 気象庁気象データ）
    merged_stations = []
    for moe_id, moe_info in moe_data.items():
        # 環境省IDから気象庁IDへの変換（例外対応）
        jma_id = ID_EXCEPTIONS.get(moe_id, moe_id)

        master_info = station_master.get(jma_id, {})
        if not master_info:
            continue

        name = master_info.get("kjName", "不明")
        pref = master_info.get("prefName", "不明")

        jma_info = jma_amedas.get(jma_id, {})
        temp = parse_jma_value(jma_info, "temp", is_divide_10=True)
        humidity = parse_jma_value(jma_info, "humidity", is_divide_10=False)
        wind = parse_jma_value(jma_info, "wind", is_divide_10=True)

        merged_stations.append({
            "station_id": moe_id,
            "jma_amedas_id": jma_id,
            "name": name,
            "prefecture": pref,
            "moe_data": {
                "wbgt": moe_info["wbgt"],
                "level": moe_info["level"],
                "updated_at": moe_info["updated_at"]
            },
            "jma_data": {
                "temperature": temp,
                "humidity": humidity,
                "wind_speed": wind
            }
        })

    output_data = {
        "metadata": {
            "generated_at": datetime.now(JST).isoformat(),
            "total_stations": len(merged_stations)
        },
        "stations": merged_stations
    }

    with open("wbgt_data.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Successfully updated wbgt_data.json with {len(merged_stations)} stations!")

if __name__ == "__main__":
    main()
