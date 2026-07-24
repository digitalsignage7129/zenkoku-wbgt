from datetime import datetime, timedelta, timezone
import json
import requests

JST = timezone(timedelta(hours=9))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def parse_jma_value(data_dict, key, is_divide_10=False):
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
  # 1. 観測所マスター（名前・都道府県）の取得
  master_url = "https://www.jma.go.jp/bosai/amedas/const/amedastable.json"
  master_res = requests.get(master_url, headers=HEADERS, timeout=10)
  master_res.raise_for_status()
  station_master = master_res.json()

  # 2. 最新アメダス実測値の取得
  now_jst = datetime.now(JST)
  target_time = now_jst.replace(minute=0, second=0, microsecond=0)
  time_str = target_time.strftime("%Y%m%d%H0000")
  data_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_str}.json"

  data_res = requests.get(data_url, headers=HEADERS, timeout=10)
  if data_res.status_code == 404:
    prev_time = target_time - timedelta(hours=1)
    time_str = prev_time.strftime("%Y%m%d%H0000")
    data_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_str}.json"
    data_res = requests.get(data_url, headers=HEADERS, timeout=10)
  data_res.raise_for_status()
  amedas_data = data_res.json()

  stations = []
  for st_id, master in station_master.items():
    name = master.get("kjName", "")
    pref = master.get("prefName", "")

    jma_info = amedas_data.get(st_id, {})
    temp = parse_jma_value(jma_info, "temp", is_divide_10=True)
    humidity = parse_jma_value(jma_info, "humidity", is_divide_10=False)
    wind = parse_jma_value(jma_info, "wind", is_divide_10=True)

    stations.append({
        "jma_id": st_id,
        "name": name,
        "prefecture": pref,
        "temperature": temp,
        "humidity": humidity,
        "wind_speed": wind,
    })

  with open("jma_weather.json", "w", encoding="utf-8") as f:
    json.dump(stations, f, ensure_ascii=False, indent=2)

  print(f"✅ Saved {len(stations)} JMA records to jma_weather.json")


if __name__ == "__main__":
  main()
