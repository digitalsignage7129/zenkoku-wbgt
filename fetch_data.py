import json
import urllib.request
import math

def main():
    headers = {'User-Agent': 'Mozilla/5.0'}

    # 1. 気象庁アメダス観測所マスターデータ（全国約1300箇所）を取得
    req_table = urllib.request.Request("https://www.jma.go.jp/bosai/amedas/const/amedastable.json", headers=headers)
    with urllib.request.urlopen(req_table) as res:
        stn_table = json.loads(res.read().decode())

    # 2. 最新のアメダス観測時刻を取得
    req_time = urllib.request.Request("https://www.jma.go.jp/bosai/amedas/data/latest_time.json", headers=headers)
    with urllib.request.urlopen(req_time) as res:
        latest_time_str = json.loads(res.read().decode())

    # 時刻フォーマット変換 (YYYYMMDDHHMM00)
    time_formatted = latest_time_str.replace("-", "").replace(":", "").replace("T", "").split("+")[0]
    amedas_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_formatted}.json"

    # 3. 全観測所の最新実測値データを一括取得
    req_amedas = urllib.request.Request(amedas_url, headers=headers)
    with urllib.request.urlopen(req_amedas) as res:
        amedas_data = json.loads(res.read().decode())

    output_stations = {}

    # 全国すべての観測所データを整形
    for stn_id, st_info in stn_table.items():
        # 緯度・経度を度数法に変換 [度, 分] -> 小数点
        lat = st_info["lat"][0] + st_info["lat"][1] / 60.0
        lon = st_info["lon"][0] + st_info["lon"][1] / 60.0
        st_name = st_info.get("kjName", "")

        st_data = amedas_data.get(stn_id, {})

        temp = st_data.get("temp", [None])[0]
        humidity = st_data.get("humidity", [None])[0]
        wind = st_data.get("wind", [None])[0]
        precip = st_data.get("precipitation1h", [0])[0]

        # 気温が存在する有効な観測所のみ保存
        if temp is not None:
            hum_val = humidity if humidity is not None else 50
            
            # 環境省公式推定式(小野らの式)でアメダス実測値からWBGTを算出
            wbgt = round(0.735 * temp + 0.0374 * hum_val + 0.00292 * temp * hum_val - 4.064, 1)

            output_stations[stn_id] = {
                "name": st_name,
                "lat": lat,
                "lon": lon,
                "temp": temp,
                "humidity": humidity,
                "wind": wind,
                "precip": precip,
                "wbgt": wbgt
            }

    result = {
        "updated_at": latest_time_str,
        "stations": output_stations
    }

    # 全国データを1つのJSONに出力
    with open("wbgt_data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)

if __name__ == "__main__":
    main()
