import json
import urllib.request
import re
from datetime import datetime, timezone, timedelta

# 日本標準時 (JST)
JST = timezone(timedelta(hours=9))

def get_wbgt_from_env():
    """環境省のCSV/WEBデータから白馬の最新WBGT値を取得"""
    # 長野県（48）の環境省最新実測/予測CSVデータ
    url = "https://www.wbgt.env.go.jp/prev15d/df/pref_48.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as res:
            lines = res.read().decode('shift_jis', errors='ignore').splitlines()
            
            # 白馬（観測所コード 48141）の行を検索
            for line in lines:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) > 2 and parts[0] == "48141":
                    # 最新の有効な数値（末尾側）を取り出す
                    for val in reversed(parts[2:]):
                        if val and val != "--":
                            # 数値変換 (例: 250 -> 25.0)
                            try:
                                wbgt_num = float(val) / 10.0 if float(val) > 50 else float(val)
                                return f"{wbgt_num:.1f}"
                            except ValueError:
                                pass
    except Exception as e:
        print(f"[Warning] 環境省WBGTデータの取得に失敗しました: {e}")
    
    return "25.0"  # フォールバック初期値


def get_amedas_hakuba():
    """気象庁アメダス（白馬観測所: 48141）から気温・風速を取得"""
    headers = {"User-Agent": "Mozilla/5.0"}
    temp_str = "--"
    wind_str = "--"

    try:
        # 1. アメダスの最新更新日時を取得
        time_url = "https://www.jma.go.jp/bosai/amedas/data/latest_time.json"
        req_time = urllib.request.Request(time_url, headers=headers)
        with urllib.request.urlopen(req_time, timeout=10) as res:
            latest_time = json.loads(res.read().decode('utf-8'))
            # 例: "2026-08-05T18:20:00+09:00" -> "20260805182000"
            formatted_time = latest_time.replace("-", "").replace(":", "").replace("T", "").split("+")[0]

        # 2. 最新アメダスデータ全件を取得して白馬(48141)を抽出
        data_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{formatted_time}.json"
        req_data = urllib.request.Request(data_url, headers=headers)
        with urllib.request.urlopen(req_data, timeout=10) as res:
            amedas_data = json.loads(res.read().decode('utf-8'))
            
            hakuba = amedas_data.get("48141", {})
            
            # 気温
            if "temp" in hakuba and hakuba["temp"][0] is not None:
                temp_str = f"{float(hakuba['temp'][0]):.1f}"

            # 風速
            if "wind" in hakuba and hakuba["wind"][0] is not None:
                wind_str = f"{float(hakuba['wind'][0]):.1f}"

    except Exception as e:
        print(f"[Warning] アメダスデータの取得に失敗しました: {e}")

    return temp_str, wind_str


def get_jma_weather():
    """気象庁天気予報API（長野県北部: 200010）から現時点の天気を取得"""
    headers = {"User-Agent": "Mozilla/5.0"}
    weather_str = "くもり"

    try:
        # 長野県の天気予報データ
        url = "https://www.jma.go.jp/bosai/forecast/data/forecast/200000.json"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as res:
            forecast_data = json.loads(res.read().decode('utf-8'))
            
            # 長野県北部（松本・白馬含むエリア）の天気テロップを取得
            time_series = forecast_data[0]["timeSeries"][0]
            for area in time_series["areas"]:
                if area["area"]["code"] in ["200010", "200000"]:
                    raw_weather = area["weathers"][0]
                    # 余分な空白を除去し、短い天気名に整形
                    weather_str = raw_weather.replace(" ", "").split("")[0]
                    break
    except Exception as e:
        print(f"[Warning] 天気予報データの取得に失敗しました: {e}")

    return weather_str


def get_wbgt_level(wbgt_val):
    """WBGT数値から熱中症警戒レベルを判定"""
    try:
        val = float(wbgt_val)
        if val >= 31.0:
            return "危険"
        elif val >= 28.0:
            return "厳重警戒"
        elif val >= 25.0:
            return "警戒"
        elif val >= 21.0:
            return "留意"
        else:
            return "ほぼ安全"
    except ValueError:
        return "警戒"


def main():
    # 1. 環境省からWBGT取得
    wbgt = get_wbgt_from_env()
    level = get_wbgt_level(wbgt)

    # 2. アメダスから気温・風速取得
    temperature, wind_speed = get_amedas_hakuba()

    # 3. 気象庁APIから天気取得
    weather = get_jma_weather()

    # 現在日時（JST）
    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    # 出力JSONデータの生成
    output_data = {
        "location": "長野県白馬村",
        "wbgt": wbgt,
        "level": level,
        "temperature": temperature,
        "wind_speed": wind_speed,
        "weather": weather,
        "updated_at": now_str
    }

    # ファイルへ書き出し
    file_path = "hakuba_wbgt.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"[{now_str}] {file_path} を更新しました:")
    print(json.dumps(output_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
