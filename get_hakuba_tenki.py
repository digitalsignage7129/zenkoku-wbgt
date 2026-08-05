import json
import urllib.request
from datetime import datetime, timedelta, timezone

# 気象庁 API（長野県: 200000）
JMA_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/200000.json"
# 白馬村が含まれるエリアコード（長野県北部: 200010）
AREA_CODE = "200010"

HEADERS = {"User-Agent": "Mozilla/5.0"}


def get_jma_weather():
    req = urllib.request.Request(JMA_URL, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # データ構造の取得（短期予報と週間予報）
    short_term = data[0]
    weekly = data[1]

    # 北部エリア（200010）のインデックスを特定
    area_index = 0
    for idx, area in enumerate(
        short_term["timeSeries"][0]["areas"]
    ):
        if area["area"]["code"] == AREA_CODE:
            area_index = idx
            break

    # 1. 天気テキストの抽出 (今日・明日)
    weathers = short_term["timeSeries"][0]["areas"][area_index]["weathers"]
    today_weather = weathers[0] if len(weathers) > 0 else "--"
    tomorrow_weather = weathers[1] if len(weathers) > 1 else "--"

    # 2. 明後日の天気 (週間予報から抽出)
    weekly_weathers = weekly["timeSeries"][0]["areas"][0]["weathers"]
    # 週間予報の2番目（index 2）が明後日
    day_after_weather = (
        weekly_weathers[2] if len(weekly_weathers) > 2 else "--"
    )

    # 3. 降水確率の抽出
    pops = short_term["timeSeries"][1]["areas"][area_index].get("pops", [])
    today_pop = max([int(p) for p in pops[:2] if p.isdigit()], default="--")
    tomorrow_pop = max(
        [int(p) for p in pops[2:] if p.isdigit()], default="--"
    )

    # 明後日の降水確率
    weekly_pops = weekly["timeSeries"][0]["areas"][0].get("pops", [])
    day_after_pop = (
        weekly_pops[2]
        if len(weekly_pops) > 2 and weekly_pops[2]
        else "--"
    )

    # 4. 気温の抽出 (今日・明日の最高/最低気温)
    temps = short_term["timeSeries"][2]["areas"][area_index].get("temps", [])
    # 気象庁データの気温配列から最高・最低を取得
    today_temp_min = temps[0] if len(temps) > 0 else "--"
    today_temp_max = temps[1] if len(temps) > 1 else "--"
    tomorrow_temp_min = temps[2] if len(temps) > 2 else "--"
    tomorrow_temp_max = temps[3] if len(temps) > 3 else "--"

    # 明後日の気温
    weekly_temps_min = weekly["timeSeries"][1]["areas"][0].get(
        "tempsMin", []
    )
    weekly_temps_max = weekly["timeSeries"][1]["areas"][0].get(
        "tempsMax", []
    )
    day_after_min = (
        weekly_temps_min[2]
        if len(weekly_temps_min) > 2 and weekly_temps_min[2]
        else "--"
    )
    day_after_max = (
        weekly_temps_max[2]
        if len(weekly_temps_max) > 2 and weekly_temps_max[2]
        else "--"
    )

    # JST時刻設定
    jst = timezone(timedelta(hours=9))
    updated_at = datetime.now(jst).strftime("%Y-%m-%d %H:%M")

    # サイネージ表示用JSON構造の整形
    result = {
        "location": "長野県白馬村",
        "updated_at": updated_at,
        "today": {
            "weather": today_weather.replace(" ", " "),
            "temp_max": str(today_temp_max),
            "temp_min": str(today_temp_min),
            "pop": str(today_pop),
        },
        "tomorrow": {
            "weather": tomorrow_weather.replace(" ", " "),
            "temp_max": str(tomorrow_temp_max),
            "temp_min": str(tomorrow_temp_min),
            "pop": str(tomorrow_pop),
        },
        "day_after": {
            "weather": str(day_after_weather).replace(" ", " "),
            "temp_max": str(day_after_max),
            "temp_min": str(day_after_min),
            "pop": str(day_after_pop),
        },
    }

    # JSON出力
    with open("hakuba_tenki.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("気象庁APIから hakuba_tenki.json を生成しました:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    get_jma_weather()
