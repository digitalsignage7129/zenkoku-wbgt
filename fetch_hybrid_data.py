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
# ⚠️ 環境省ID と 気象庁アメダスID が異なる場合の例外辞書
# (必要に応じて、今後ズレが見つかった地点をここに追加していきます)
# ------------------------------------------------------------------
ID_EXCEPTIONS = {
    "45112": "45212",  # 千葉
    # 例: "XXXXX": "YYYYY",
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


def main():
    # 1. 気象庁マスターの取得
    master_url = "https://www.jma.go.jp/bosai/amedas/const/amedastable.json"
    res = requests.get(master_url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    station_master = res.json()

    # 2. 環境省 WBGT CSVの取得
    moe_url = "https://www.wbgt.env.go.jp/est1570/d/wbgt_all_latest.csv"
    res = requests.get(moe_url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    try:
        content = res.content.decode("shift_jis")
    except UnicodeDecodeError:
        content = res.content.decode("utf-8-sig")

    moe_data = {}
    reader = csv.reader(io.StringIO(content))
    for row in reader:
        if not row or len(row) < 4 or row[0].startswith("#"):
            continue
        st_code = row[0].strip()
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
        moe_data[st_code] = {"wbgt": wbgt_val, "level": level, "updated_at": formatted_time}

    # 3. 気象庁 最新アメダスデータの取得
    now_jst = datetime.now(JST)
    target_time = now_jst.replace(minute=0, second=0, microsecond=0)
    time_str = target_time.strftime("%Y%m%d%H0000")
    jma_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_str}.json"
    
    res = requests.get(jma_url, headers=HEADERS, timeout=10)
    if res.status_code == 404:
        prev_time = target_time - timedelta(hours=1)
        time_str = prev_time.strftime("%Y%m%d%H0000")
        jma_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_str}.json"
        res = requests.get(jma_url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    jma_amedas = res.json()

    # 4. マージ処理
    merged_stations = []
    for moe_id, moe_info in moe_data.items():
        # 例外辞書に登録があれば変換、なければそのままのIDを使う
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
            "moe_data": moe_info,
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
