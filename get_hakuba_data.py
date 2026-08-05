import json
import urllib.request
from datetime import datetime, timezone, timedelta

# 日本標準時 (JST)
JST = timezone(timedelta(hours=9))

def get_wbgt_from_env():
    """環境省のCSVデータから白馬（48141）の最新WBGT値を取得"""
    url = "https://www.wbgt.env.go.jp/prev15d/df/pref_48.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as res:
            lines = res.read().decode('shift_jis', errors='ignore').splitlines()
            for line in lines:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) > 2 and parts[0] == "48141":  # 白馬観測所
                    for val in reversed(parts[2:]):
                        if val and val != "--":
                            try:
                                wbgt_num = float(val) / 10.0 if float(val) > 50 else float(val)
                                return f"{wbgt_num:.1f}"
                            except ValueError:
                                pass
    except Exception as e:
        print(f"[Warning] 環境省WBGT取得失敗: {e}")
        
    return "25.0"


def get_amedas_hakuba():
    """気象庁アメダス（白馬観測所: 48141）から気温・風速を確実に取得"""
    headers = {"User-Agent": "Mozilla/5.0"}
    temp_str = "--"
    wind_str = "--"

    try:
        # 1. アメダスの最新更新時刻を取得
        time_url = "https://www.jma.go.jp/bosai/amedas/data/latest_time.json"
        req_time = urllib.request.Request(time_url, headers=headers)
        with urllib.request.urlopen(req_time, timeout=10) as res:
            latest_time_str = json.loads(res.read().decode('utf-8'))
            base_dt = datetime.fromisoformat(latest_time_str)
    except Exception as e:
        print(f"[Warning] アメダス最新時刻取得失敗: {e}")
        base_dt = datetime.now(timezone.utc)

    # 2. ファイル未生成エラーを避けるため、最新時刻から10分ずつ最大4回遡ってデータを探索
    for i in range(4):
        target_dt = base_dt - timedelta(minutes=10 * i)
        formatted_time = target_dt.strftime("%Y%m%d%H%M00")
        data_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{formatted_time}.json"
        
        try:
            req_data = urllib.request.Request(data_url, headers=headers)
            with urllib.request.urlopen(req_data, timeout=10) as res:
                amedas_data = json.loads(res.read().decode('utf-8'))
                
                hakuba = amedas_data.get("48141", {})
                if hakuba:
                    if "temp" in hakuba and hakuba["temp"][0] is not None:
                        temp_str = f"{float(hakuba['temp'][0]):.1f}"
                    if "wind" in hakuba and hakuba["wind"][0] is not None:
                        wind_str = f"{float(hakuba['wind'][0]):.1f}"
                    
                    # 取得できたらループを抜ける
                    if temp_str != "--" and wind_str != "--":
                        break
        except Exception:
            continue

    return temp_str, wind_str


def get_jma_weather():
    """気象庁公式API（長野県: 200000）から天気を取得"""
    headers = {"User-Agent": "Mozilla/5.0"}
    weather_str = "くもり"

    try:
        url = "https://www.jma.go.jp/bosai/forecast/data/forecast/200000.json"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as res:
            forecast_data = json.loads(res.read().decode('utf-8'))
            time_series = forecast_data[0]["timeSeries"][0]
            for area in time_series["areas"]:
                # 長野県北部エリア
                if area["area"]["code"] in ["200010", "200000"]:
                    raw_weather = area["weathers"][0]
                    # テロップから先頭の天気単語を取り出し
                    cleaned = raw_weather.replace(" ", " ").split()[0]
                    if "晴" in cleaned:
                        weather_str = "晴れ"
                    elif "雨" in cleaned:
                        weather_str = "雨"
                    elif "雪" in cleaned:
                        weather_str = "雪"
                    else:
                        weather_str = "くもり"
                    break
    except Exception as e:
        print(f"[Warning] 気象庁天気取得失敗: {e}")

    return weather_str


def get_wbgt_level(wbgt_val):
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

    # 2. 気象庁アメダス（48141白馬）から気温・風速を取得
    temperature, wind_speed = get_amedas_hakuba()

    # 3. 気象庁APIから天気を取得
    weather = get_jma_weather()

    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    output_data = {
        "location": "長野県白馬村",
        "wbgt": wbgt,
        "level": level,
        "temperature": temperature,
        "wind_speed": wind_speed,
        "weather": weather,
        "updated_at": now_str
    }

    with open("hakuba_wbgt.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"[{now_str}] hakuba_wbgt.json を更新しました:")
    print(json.dumps(output_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
