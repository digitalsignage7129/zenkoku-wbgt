import json
import urllib.request
from datetime import datetime, timezone, timedelta

# タイムゾーン定義
JST = timezone(timedelta(hours=9))
UTC = timezone.utc

def get_wbgt_from_env():
    """環境省のCSVデータから白馬の最新WBGT値を取得"""
    url = "https://www.wbgt.env.go.jp/prev15d/df/pref_48.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as res:
            lines = res.read().decode('shift_jis', errors='ignore').splitlines()
            for line in lines:
                # 「48141」または「白馬」が含まれる行を特定
                if "48141" in line or "白馬" in line:
                    parts = [p.strip() for p in line.split(',')]
                    # 後ろから順に有効なWBGT数値を探す
                    for val in reversed(parts):
                        if val and val != "--" and val.replace('.', '', 1).isdigit():
                            try:
                                wbgt_num = float(val)
                                # 10倍表記（例: 250 -> 25.0）の補正
                                if wbgt_num > 50:
                                    wbgt_num /= 10.0
                                return f"{wbgt_num:.1f}"
                            except ValueError:
                                pass
    except Exception as e:
        print(f"[Warning] 環境省WBGT取得エラー: {e}")
        
    return "--"


def get_amedas_hakuba():
    """気象庁アメダス（白馬: 48141）から現在のリアルタイム気温・風速を取得"""
    headers = {"User-Agent": "Mozilla/5.0"}
    temp_str = "--"
    wind_str = "--"

    try:
        # 1. 気象庁の最新データ更新時刻（JST）を取得
        time_url = "https://www.jma.go.jp/bosai/amedas/data/latest_time.json"
        req_time = urllib.request.Request(time_url, headers=headers)
        with urllib.request.urlopen(req_time, timeout=10) as res:
            latest_time_str = json.loads(res.read().decode('utf-8'))
            dt_jst = datetime.fromisoformat(latest_time_str)
    except Exception as e:
        print(f"[Warning] アメダス最新時刻取得エラー: {e}")
        dt_jst = datetime.now(JST)

    # 2. 【重要】JSTからUTC（協定世界時）へ変換（気象庁のファイル名はUTC管理のため）
    dt_utc = dt_jst.astimezone(UTC)

    # 3. 直近のデータファイル（10分刻み）を探索
    for i in range(3):
        target_utc = dt_utc - timedelta(minutes=10 * i)
        formatted_time = target_utc.strftime("%Y%m%d%H%M00")
        data_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{formatted_time}.json"
        
        try:
            req_data = urllib.request.Request(data_url, headers=headers)
            with urllib.request.urlopen(req_data, timeout=10) as res:
                amedas_data = json.loads(res.read().decode('utf-8'))
                
                # 白馬観測所（48141）
                hakuba = amedas_data.get("48141", {})
                if hakuba:
                    if "temp" in hakuba and hakuba["temp"] and hakuba["temp"][0] is not None:
                        temp_str = f"{float(hakuba['temp'][0]):.1f}"
                    if "wind" in hakuba and hakuba["wind"] and hakuba["wind"][0] is not None:
                        wind_str = f"{float(hakuba['wind'][0]):.1f}"
                    
                    if temp_str != "--" and wind_str != "--":
                        break
        except Exception:
            continue

    return temp_str, wind_str


def get_jma_weather():
    """気象庁天気予報API（長野県北部）から現在の天気を取得"""
    headers = {"User-Agent": "Mozilla/5.0"}
    weather_str = "くもり"

    try:
        url = "https://www.jma.go.jp/bosai/forecast/data/forecast/200000.json"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as res:
            forecast_data = json.loads(res.read().decode('utf-8'))
            time_series = forecast_data[0]["timeSeries"][0]
            for area in time_series["areas"]:
                if area["area"]["code"] in ["200010", "200000"]:
                    raw_weather = area["weathers"][0]
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
        print(f"[Warning] 天気予報取得エラー: {e}")

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
    wbgt = get_wbgt_from_env()
    level = get_wbgt_level(wbgt)
    temperature, wind_speed = get_amedas_hakuba()
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

    print(f"[{now_str}] hakuba_wbgt.json 更新完了:")
    print(json.dumps(output_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
