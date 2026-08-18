<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>シンプル3日天気</title>
  <style>
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }
    
    html, body {
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      background-color: #080b10;
      font-family: "Hiragino Kaku Gothic ProN", "Meiryo", sans-serif;
      color: #ffffff;
      user-select: none;
    }

    body {
      padding: 2vh 3vw;
      display: flex;
      flex-direction: column;
      gap: 2vh;
    }

    .weather-card {
      flex: 1;
      background: #111722;
      border: 1px solid #1f2b3e;
      border-radius: 16px;
      padding: 0 4vw;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .weather-card.today {
      background: linear-gradient(135deg, #132238 0%, #0d1726 100%);
      border: 2px solid #00e5ff;
    }

    .date-box {
      width: 30%;
      display: flex;
      flex-direction: column;
      justify-content: center;
    }
    .day-label {
      font-size: clamp(14px, 2.2vh, 20px);
      font-weight: bold;
      color: #00e5ff;
      margin-bottom: 4px;
    }
    .today .day-label {
      color: #ffcc00;
    }
    .date-text {
      font-size: clamp(18px, 3vh, 28px);
      font-weight: 900;
      color: #ffffff;
      white-space: nowrap;
    }

    .icon-box {
      width: 30%;
      text-align: center;
      font-size: clamp(48px, 9vh, 80px);
      line-height: 1;
    }

    .temp-box {
      width: 40%;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      font-size: clamp(22px, 4.5vh, 42px);
      font-weight: 900;
      white-space: nowrap;
    }
    .temp-high { color: #ff5555; }
    .temp-slash { color: #3a4b60; font-weight: 400; }
    .temp-low { color: #3399ff; }
  </style>
</head>
<body>

  <div class="weather-card today">
    <div class="date-box">
      <div class="day-label" id="label-0">今日</div>
      <div class="date-text" id="date-0">--/-- (-)</div>
    </div>
    <div class="icon-box" id="icon-0">☀️</div>
    <div class="temp-box">
      <span class="temp-high" id="high-0">--℃</span>
      <span class="temp-slash">/</span>
      <span class="temp-low" id="low-0">--℃</span>
    </div>
  </div>

  <div class="weather-card">
    <div class="date-box">
      <div class="day-label" id="label-1">明日</div>
      <div class="date-text" id="date-1">--/-- (-)</div>
    </div>
    <div class="icon-box" id="icon-1">⛅</div>
    <div class="temp-box">
      <span class="temp-high" id="high-1">--℃</span>
      <span class="temp-slash">/</span>
      <span class="temp-low" id="low-1">--℃</span>
    </div>
  </div>

  <div class="weather-card">
    <div class="date-box">
      <div class="day-label" id="label-2">明後日</div>
      <div class="date-text" id="date-2">--/-- (-)</div>
    </div>
    <div class="icon-box" id="icon-2">🌧️</div>
    <div class="temp-box">
      <span class="temp-high" id="high-2">--℃</span>
      <span class="temp-slash">/</span>
      <span class="temp-low" id="low-2">--℃</span>
    </div>
  </div>

  <script>
    const CITIES = {
      '4020300': { forecastCode: '400000' },
      '4021700': { forecastCode: '400000' }
    };

    const params = new URLSearchParams(window.location.search);
    const cityCode = params.get('city') || '4020300';
    const cityInfo = CITIES[cityCode] || CITIES['4020300'];

    function getWeatherIcon(text) {
      if (!text) return '☀️';
      if (text.includes('雷')) return '🌩️';
      if (text.includes('雪')) return '❄️';
      if (text.includes('雨')) return text.includes('晴') ? '🌦️' : '🌧️';
      if (text.includes('くもり') || text.includes('曇')) return text.includes('晴') ? '⛅' : '☁️';
      return '☀️';
    }

    function getDateKey(isoStr) {
      const d = new Date(isoStr);
      return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    }

    async function fetchForecast() {
      try {
        const url = `https://www.jma.go.jp/bosai/forecast/data/forecast/${cityInfo.forecastCode}.json?t=` + Date.now();
        const res = await fetch(url);
        const data = await res.json();

        const shortData = data[0];
        const weeklyData = data[1] || null;

        const dailyMap = {};

        // 1. 天気テキスト取得
        const tsWeather = shortData.timeSeries[0];
        const areaWeather = tsWeather.areas[0];
        tsWeather.timeDefines.forEach((tStr, idx) => {
          const key = getDateKey(tStr);
          if (!dailyMap[key]) dailyMap[key] = { dateObj: new Date(tStr), weather: '', temps: [], high: null, low: null };
          if (areaWeather.weathers && areaWeather.weathers[idx]) {
            dailyMap[key].weather = areaWeather.weathers[idx].trim();
          }
        });

        // 2. 短期気温取得
        if (shortData.timeSeries[2]) {
          const tsTemp = shortData.timeSeries[2];
          const areaTemp = tsTemp.areas[0];
          tsTemp.timeDefines.forEach((tStr, idx) => {
            const key = getDateKey(tStr);
            const val = parseInt(areaTemp.temps[idx]);
            if (!isNaN(val)) {
              if (!dailyMap[key]) dailyMap[key] = { dateObj: new Date(tStr), weather: '', temps: [], high: null, low: null };
              dailyMap[key].temps.push(val);
            }
          });
        }

        // 3. 週間気温データ（補完用）
        if (weeklyData && weeklyData.timeSeries && weeklyData.timeSeries[1]) {
          const tsWTemp = weeklyData.timeSeries[1];
          const areaWTemp = tsWTemp.areas[0];
          tsWTemp.timeDefines.forEach((tStr, idx) => {
            const key = getDateKey(tStr);
            if (!dailyMap[key]) dailyMap[key] = { dateObj: new Date(tStr), weather: '', temps: [], high: null, low: null };
            if (areaWTemp.tempsMax && areaWTemp.tempsMax[idx] !== "") dailyMap[key].high = areaWTemp.tempsMax[idx];
            if (areaWTemp.tempsMin && areaWTemp.tempsMin[idx] !== "") dailyMap[key].low = areaWTemp.tempsMin[idx];
          });
        }

        const now = new Date();
        const todayKey = getDateKey(now);
        const sortedKeys = Object.keys(dailyMap).filter(k => k >= todayKey).sort();

        const labels = ['今日', '明日', '明後日'];

        for (let i = 0; i < 3; i++) {
          const key = sortedKeys[i];
          if (!key) continue;

          const item = dailyMap[key];
          const d = item.dateObj;
          const dateStr = `${d.getMonth()+1}/${d.getDate()} (${['日','月','火','水','木','金','土'][d.getDay()]})`;

          document.getElementById(`label-${i}`).textContent = labels[i] || `${i}日後`;
          document.getElementById(`date-${i}`).textContent = dateStr;
          document.getElementById(`icon-${i}`).textContent = getWeatherIcon(item.weather);

          let highVal = item.high;
          let lowVal = item.low;

          // 気温配列からの算出・保存・復元ロジック
          if (item.temps.length > 0) {
            const maxTemp = Math.max(...item.temps);
            const minTemp = Math.min(...item.temps);
            
            if (!highVal) highVal = maxTemp;

            if (maxTemp !== minTemp) {
              // 最高・最低が2つ取れている（朝方のデータがある）場合
              if (!lowVal) lowVal = minTemp;
              // 今日の最低気温をストレージに保存
              if (key === todayKey) {
                localStorage.setItem(`saved_low_${todayKey}`, minTemp);
              }
            } else {
              // 昼以降で気温が1つ（34℃等）しか取れない場合
              if (key === todayKey) {
                const savedLow = localStorage.getItem(`saved_low_${todayKey}`);
                if (savedLow) {
                  lowVal = savedLow; // 保存していた朝の最低気温を復元
                } else if (!lowVal) {
                  lowVal = '--'; // 保持データがなければ無理に34℃を入れず '--' にする
                }
              } else if (!lowVal) {
                lowVal = minTemp;
              }
            }
          }

          document.getElementById(`high-${i}`).textContent = (highVal !== null && highVal !== undefined) ? `${highVal}℃` : '--℃';
          document.getElementById(`low-${i}`).textContent = (lowVal !== null && lowVal !== undefined) ? `${lowVal}℃` : '--℃';
        }

      } catch (e) {
        console.error('天気取得エラー:', e);
      }
    }

    fetchForecast();
    setInterval(fetchForecast, 600000);
  </script>
</body>
</html>
