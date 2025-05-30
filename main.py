from fastapi import FastAPI, Request, Form, Cookie, Response, Header
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from geopy.geocoders import Nominatim
from uuid import uuid4
from datetime import datetime
from geopy.exc import GeocoderTimedOut
import sqlite3
import httpx

app = FastAPI()
templates = Jinja2Templates(directory="templates")

geolocator = Nominatim(user_agent="weather_app")

# Подключение к БД
conn = sqlite3.connect("search_history.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    city TEXT,
    timestamp TEXT
)
""")
conn.commit()


# Сохранение поиска
def save_search(user_id: str, city: str):
    cursor.execute("INSERT INTO search_history (user_id, city, timestamp) VALUES (?, ?, ?)",
                   (user_id, city, datetime.utcnow().isoformat()))
    conn.commit()


# Сохранение последнего поиска
def get_user_last_city(user_id: str):
    cursor.execute("SELECT city FROM search_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user_id,))
    res = cursor.fetchone()
    return res[0] if res else None


# Вся история поиска городов
def get_city_search_counts():
    cursor.execute("SELECT city, COUNT(*) as count FROM search_history GROUP BY city ORDER BY count DESC")
    return cursor.fetchall()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user_id: str | None = Cookie(default=None)):
    if not user_id:
        user_id = str(uuid4())

    last_city = get_user_last_city(user_id)
    response = templates.TemplateResponse(request, "index.html", {"request": request, "last_city": last_city, "weather": None, "error": None})
    response.set_cookie(key="user_id", value=user_id, max_age=3600*24*365*2)
    return response


@app.post("/weather")
async def get_weather(
    city: str = Form(...),
    user_id: str | None = Cookie(default=None),
    accept: str = Header(default="text/html")
):
    if not user_id:
        user_id = str(uuid4())

    location = geolocator.geocode(city)
    if not location:
        if "application/json" in accept:
            return JSONResponse({"error": "Город не найден"}, status_code=400)
        return RedirectResponse(url="/", status_code=303)

    lat, lon = location.latitude, location.longitude
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    async with httpx.AsyncClient() as client:
        weather_resp = await client.get(url)
    data = weather_resp.json()

    if "current_weather" not in data:
        if "application/json" in accept:
            return JSONResponse({"error": "Данные о погоде недоступны"}, status_code=400)
        return RedirectResponse(url="/", status_code=303)

    save_search(user_id, city.title())

    if "application/json" in accept:
        weather = data["current_weather"]
        return JSONResponse({
            "weather": {
                "temperature": weather["temperature"],
                "windspeed": weather["windspeed"],
                "winddirection": weather["winddirection"],
                "time": weather["time"],
                "city": city.title()
            }
        })

    return RedirectResponse(url="/", status_code=303)


@app.get("/autocomplete")
async def autocomplete(query: str):
    try:
        location = geolocator.geocode(query, exactly_one=False, limit=5, timeout=5)
    except GeocoderTimedOut:
        return JSONResponse([], status_code=504)

    results = []
    if location:
        for loc in location:
            results.append(loc.address.split(",")[0])
    return JSONResponse(results)


@app.get("/stats")
async def stats():
    counts = get_city_search_counts()
    return JSONResponse({"search_counts": [{"city": c[0], "count": c[1]} for c in counts]})
