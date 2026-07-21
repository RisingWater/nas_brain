"""天气查询工具 — 通过 wttr.in 获取今天/明天天气"""
import requests
from . import BaseTool, registry

_DESC_CN: dict[str, str] = {
    "Sunny": "晴", "Clear": "晴", "Partly cloudy": "多云", "Partly Cloudy": "多云",
    "Cloudy": "阴", "Overcast": "阴", "Mist": "薄雾", "Fog": "雾",
    "Freezing fog": "冻雾", "Patchy rain nearby": "局部阵雨",
    "Patchy rain possible": "局部阵雨", "Patchy light rain": "小到中雨",
    "Light rain": "小雨", "Moderate rain": "中雨",
    "Moderate rain at times": "间歇中雨", "Heavy rain": "大雨",
    "Heavy rain at times": "间歇大雨", "Torrential rain shower": "暴雨",
    "Light drizzle": "毛毛雨", "Patchy light drizzle": "局部毛毛雨",
    "Light rain shower": "小阵雨", "Rain shower": "阵雨",
    "Patchy light rain in area with thunder": "雷阵雨",
    "Moderate or heavy rain shower": "中到大阵雨",
    "Thundery outbreaks in nearby": "周边雷暴",
    "Patchy sleet nearby": "局部雨夹雪", "Light sleet": "小雨夹雪",
    "Moderate or heavy sleet": "中到大雨夹雪", "Patchy snow nearby": "局部雪",
    "Light snow": "小雪", "Moderate snow": "中雪", "Heavy snow": "大雪",
    "Blizzard": "暴风雪", "Blowing snow": "吹雪",
    "Smoky haze": "霾", "Haze": "霾", "Freezing drizzle": "冻毛毛雨",
    "Ice pellets": "冰粒",
}


def _translate(desc: str) -> str:
    return _DESC_CN.get(desc.strip(), desc)


def _time_str(t: int) -> str:
    return f"{t // 100:02d}:{t % 100:02d}"


def _summarize_day(day: dict) -> str:
    date_str = day["date"]
    month, day_num = int(date_str[5:7]), int(date_str[8:10])
    min_temp = day.get("mintempC", "?")
    max_temp = day.get("maxtempC", "?")
    avg_temp = day.get("avgtempC", "?")
    lines = [f"{month}月{day_num}日 温度 {min_temp}°C ~ {max_temp}°C（平均 {avg_temp}°C）"]
    hourly = day.get("hourly", [])
    precip_slots = [
        (int(h["time"]), _translate(h.get("weatherDesc", [{"value": "未知"}])[0]["value"]),
         float(h.get("precipMM", 0)))
        for h in hourly if h
    ]
    merged: list = []
    for t, desc, precip in precip_slots:
        if merged and merged[-1][2] == desc:
            merged[-1] = (merged[-1][0], t + 300, desc, max(merged[-1][3], precip))
        else:
            merged.append((t, t + 300, desc, precip))
    rain_parts = [
        f"{_time_str(start)}-{_time_str(end)} {desc}"
        for start, end, desc, precip in merged
        if precip > 0 or any(kw in desc for kw in ("雨", "雪", "雷", "雹", "冰"))
    ]
    if rain_parts:
        lines.append("降水时段: " + "；".join(rain_parts))
    else:
        lines.append("全天无降水")
    return "\n  ".join(lines)


class WeatherTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_weather",
            display_name="查询天气",
            description="查询指定城市今天或明天的天气。返回温度范围、天气状况、降水时段。",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称，如 Beijing、上海、Tokyo，留空则自动判断位置"},
                    "date": {"type": "string", "enum": ["today", "tomorrow"],
                             "description": "查询日期：today=今天（默认），tomorrow=明天"},
                },
                "required": [],
            },
        )

    def execute(self, args: dict) -> dict:
        city = args.get("city", "")
        date = args.get("date", "today")
        try:
            resp = requests.get(
                f"https://wttr.in/{city}",
                params={"format": "j1"}, timeout=10,
                headers={"Accept-Language": "zh-CN"},
            )
            resp.encoding = "utf-8"
            data = resp.json()
            area_list = data.get("nearest_area", [])
            resolved = area_list[0]["areaName"][0]["value"] if area_list else (city or "当前地区")
            weather_list = data.get("weather", [])
            if not weather_list:
                return {"text": f"未找到 {resolved} 的天气信息"}
            idx = 0 if date == "today" else 1
            if idx >= len(weather_list):
                return {"text": f"暂无 {resolved} 未来天气数据"}
            summary = _summarize_day(weather_list[idx])
            label = "今天" if date == "today" else "明天"
            result = f"{resolved} {label}天气:\n  {summary}"
            if date == "today":
                curr = data.get("current_condition", [])
                if curr:
                    c = curr[0]
                    desc_en = c.get("weatherDesc", [{"value": "未知"}])[0]["value"]
                    result += (f"\n  当前: {_translate(desc_en)}, 气温 {c['temp_C']}°C, "
                               f"体感 {c['FeelsLikeC']}°C, 湿度 {c['humidity']}%, "
                               f"风速 {c['winddir16Point']} {c['windspeedKmph']}km/h")
            return {"text": result}
        except Exception as e:
            return {"text": f"查询天气失败: {e}"}


registry.register(WeatherTool())
