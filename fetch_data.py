import json
import urllib.request

def main():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    # 1. 気象庁アメダス観測所マスターデータ取得
    try:
        req_table = urllib.request.Request("https://www.jma.go.jp/bosai/amedas/const/amedastable.json", headers=headers)
        with urllib.request.urlopen(req_table, timeout=10) as res:
            stn_table = json.loads(res.read().decode())
    except Exception as e:
        print(f"Error fetching amedastable.json: {e}")
        return

    # 2. 最新の観測時刻を取得
    try:
        req_time = urllib.request.Request("https://www.jma.go.jp/bosai/amedas/data/latest_time.json", headers=headers)
        with urllib.request.urlopen(req_time, timeout=10) as res:
            latest_time_str = json.loads(res.read().decode())
    except Exception as e:
        print(f"Error fetching latest_time.json: {e}")
        return

    time_formatted = latest_time_str.replace("-", "").replace(":", "").replace("T", "").split("+")[0]
    amedas_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_formatted}.json"

    # 3. 実測値データ取得
    try:
        req_amedas = urllib.request.Request(amedas_url, headers=headers)
        with urllib.request.urlopen(req_amedas, timeout=10) as res:
            amedas_data = json.loads(res.read().decode())
    except Exception as e:
        print(f"Error fetching amedas data from {amedas_url}: {e}")
        return

    output_stations = {}

    for stn_id, st_info in stn_table.items():
        st_name = st_info.get("kjName", "")
        st_kana = st_info.get("knName", "")
        st_data = amedas_data.get(stn_id, {})

        temp = st_data.get("temp", [None])[0] if isinstance(st_data.get("temp"), list) else None
        humidity = st_data.get("humidity", [None])[0] if isinstance(st_data.get("humidity"), list) else None
        wind = st_data.get("wind", [None])[0] if isinstance(st_data.get("wind"), list) else None
        precip = st_data.get("precipitation1h", [0])[0] if isinstance(st_data.get("precipitation1h"), list) else 0

        if temp is not None:
            hum_val = humidity if humidity is not None else 50
            # 環境省公式計算式（小野らの式）
            wbgt = round(0.735 * temp + 0.0374 * hum_val + 0.00292 * temp * hum_val - 4.064, 1)

            output_stations[stn_id] = {
                "name": st_name,
                "kana": st_kana,
                "temp": temp,
                "humidity": humidity,
                "wind": wind,
                "precip": precip if precip is not None else 0,
                "wbgt": wbgt
            }

    result = {
        "updated_at": latest_time_str,
        "stations": output_stations
    }

    with open("wbgt_data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print("Successfully updated wbgt_data.json")

if __name__ == "__main__":
    main()
