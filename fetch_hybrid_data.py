from datetime import datetime, timezone, timedelta
import io
import csv
import json
import requests

# 日本時間 (JST = UTC+9) の定義
JST = timezone(timedelta(hours=9))

# ------------------------------------------------------------------
# 1. 気象庁の全観測所マスター情報（名前・都道府県）を取得
# ------------------------------------------------------------------
def fetch_jma_station_master() -> dict:
    """全国のアメダス観測所コードと名称・都道府県の対応表を取得"""
    url = "https://www.jma.go.jp/bosai/amedas/const/amedas_table.json"
    print("Fetching JMA Station Master...")
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"Error fetching station master: {e}")
        return {}


# ------------------------------------------------------------------
# 2. 環境省 CSV から全地点のWBGTを取得
# ------------------------------------------------------------------
def fetch_moe_wbgt_all() -> dict:
    """環境省から最新の全地点WBGTを取得"""
    url = "https://www.wbgt.env.go.jp/est1570/d/wbgt_all_latest.csv"
    print("Fetching MoE WBGT CSV...")
    try:
        res = requests.get(url, timeout=10)
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
                if wbgt_val > 50:  # 10倍表示の補正 (例: 252 -> 25.2)
                    wbgt_val = round(wbgt_val / 10.0, 1)
            except ValueError:
                continue

            # レベル判定
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
    except Exception as e:
        print(f"Error fetching MoE CSV: {e}")
        return {}


# ------------------------------------------------------------------
# 3. 気象庁 アメダス実測値を取得（JST時間を厳密指定）
# ------------------------------------------------------------------
def fetch_jma_amedas_latest() -> dict:
    """日本時間(JST)基準で気象庁の最新アメダスJSONを取得"""
    now_jst = datetime.now(JST)
    
    # 毎時00分のタイムスタンプを生成 (例: 20260724160000)
    target_time = now_jst.replace(minute=0, second=0, microsecond=0)
    time_str = target_time.strftime("%Y%m%d%H0000")
    
    url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_str}.json"
    print(f"Fetching JMA AMeDAS data from: {url}")
    
    try:
        res = requests.get(url, timeout=10)
        # 毎時00分直後でまだデータがない場合は1時間前をフォールバック試行
        if res.status_code == 404:
            prev_time = target_time - timedelta(hours=1)
            time_str = prev_time.strftime("%Y%m%d%H0000")
            url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_str}.json"
            print(f"Fallback to previous hour: {url}")
            res = requests.get(url, timeout=10)

        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"Error fetching JMA data: {e}")
        return {}


# ------------------------------------------------------------------
# 4. 全地点マージ処理
# ------------------------------------------------------------------
def main():
    station_master = fetch_jma_station_master()
    moe_data = fetch_moe_wbgt_all()
    jma_data = fetch_jma_amedas_latest()

    merged_stations = []

    # 全観測所マスターをループ（全国約840地点）
    for st_id, master_info in station_master.items():
        name = master_info.get("kjName", "")
        pref = master_info.get("prefName", "")

        # 環境省データ
        moe_info = moe_data.get(st_id, {"wbgt": None, "level": "不明", "updated_at": None})

        # 気象庁データ
        jma_info = jma_data.get(st_id, {})
        temp = jma_info.get("temp", [None])[0] if "temp" in jma_info else None
        humidity = jma_info.get("humidity", [None])[0] if "humidity" in jma_info else None
        wind = jma_info.get("wind", [None])[0] if "wind" in jma_info else None

        merged_stations.append({
            "station_id": st_id,
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

    print(f"Successfully updated wbgt_data.json with {len(merged_stations)} stations!")

if __name__ == "__main__":
    main()
