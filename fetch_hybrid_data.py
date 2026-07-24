from datetime import datetime, timezone, timedelta
import io
import csv
import json
import requests

JST = timezone(timedelta(hours=9))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

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

def calc_wbgt_approx(temp: float, humidity: float) -> float:
    """環境省データが取得できない場合、気象庁の気温・湿度から簡易WBGTを算出する"""
    if temp is None or humidity is None:
        return None
    # Stullの簡易式などをベースにした近似計算
    wbgt = 0.725 * temp + 0.0368 * humidity + 0.00315 * temp * humidity - 3.2
    return round(wbgt, 1)

def get_wbgt_level(wbgt_val: float) -> str:
    if wbgt_val is None: return "不明"
    if wbgt_val < 21.0: return "ほぼ安全"
    elif wbgt_val < 25.0: return "留意"
    elif wbgt_val < 28.0: return "警戒"
    elif wbgt_val < 31.0: return "厳重警戒"
    else: return "危険"

def fetch_moe_wbgt_all() -> dict:
    """環境省から最新の全地点WBGTを取得（失敗時は空を返して異常終了を防ぐ）"""
    url = "https://www.wbgt.env.go.jp/est1570/d/wbgt_all_latest.csv"
    print("Fetching MoE WBGT CSV...")
    try:
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

            level = get_wbgt_level(wbgt_val)
            formatted_time = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str.zfill(2)[:2]}:00"
            parsed[station_code] = {
                "wbgt": wbgt_val,
                "level": level,
                "updated_at": formatted_time,
                "source": "moe"
            }
        return parsed
    except Exception as e:
        print(f"⚠️ Warning: Could not fetch MoE CSV ({e}). Falling back to JMA calculation.")
        return {}

def fetch_jma_amedas_latest() -> dict:
    """気象庁の最新アメダス実測値を取得"""
    now_jst = datetime.now(JST)
    target_time = now_jst.replace(minute=0, second=0, microsecond=0)
    time_str = target_time.strftime("%Y%m%d%H0000")
    
    url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_str}.json"
    print(f"Fetching JMA AMeDAS data from: {url}")
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 404:
            prev_time = target_time - timedelta(hours=1)
            time_str = prev_time.strftime("%Y%m%d%H0000")
            url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_str}.json"
            print(f"Fallback to previous hour: {url}")
            res = requests.get(url, headers=HEADERS, timeout=10)

        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"❌ Error fetching JMA data: {e}")
        return {}

def main():
    # 1. 気象庁マスターの取得
    master_url = "https://www.jma.go.jp/bosai/amedas/const/amedastable.json"
    try:
        res = requests.get(master_url, headers=HEADERS, timeout=10)
        res.raise_for_status()
        station_master = res.json()
    except Exception as e:
        raise RuntimeError(f"気象庁マスターの取得に失敗しました: {e}")

    # 2. 環境省データ & 気象庁アメダスデータの取得
    moe_data = fetch_moe_wbgt_all()
    jma_amedas = fetch_jma_amedas_latest()

    merged_stations = []

    # 気象庁マスターをベースに全地点を網羅しつつ、環境省データがあればそれを優先、なければ気象庁から算出
    for jma_id, master_info in station_master.items():
        name = master_info.get("kjName", "不明")
        pref = master_info.get("prefName", "不明")

        # 環境省IDの逆引き（またはマッピング）
        moe_id = jma_id
        for m_key, j_val in ID_EXCEPTIONS.items():
            if j_val == jma_id:
                moe_id = m_key
                break

        # 気象庁の実測値を取得
        jma_info = jma_amedas.get(jma_id, {})
        temp = parse_jma_value(jma_info, "temp", is_divide_10=True)
        humidity = parse_jma_value(jma_info, "humidity", is_divide_10=False)
        wind = parse_jma_value(jma_info, "wind", is_divide_10=True)

        # 環境省データが存在すればそれを利用、なければ気象庁の気温・湿度から算出
        moe_info = moe_data.get(moe_id)
        if moe_info and moe_info["wbgt"] is not None:
            wbgt_val = moe_info["wbgt"]
            wbgt_level = moe_info["level"]
            updated_at = moe_info["updated_at"]
        else:
            wbgt_val = calc_wbgt_approx(temp, humidity)
            wbgt_level = get_wbgt_level(wbgt_val)
            now_str = datetime.now(JST).strftime("%Y-%m-%d %H:00")
            updated_at = now_str if wbgt_val is not None else None

        merged_stations.append({
            "station_id": moe_id,
            "jma_amedas_id": jma_id,
            "name": name,
            "prefecture": pref,
            "moe_data": {
                "wbgt": wbgt_val,
                "level": wbgt_level,
                "updated_at": updated_at
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
