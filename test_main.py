from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_homepage():
    """Проверка главной страницы."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Прогноз погоды" in response.text


def test_autocomplete_valid_query():
    """Проверка автозаполнения."""
    response = client.get("/autocomplete", params={"query": "Moscow"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("Moscow" in city or "Москва" in city for city in data)


def test_weather_invalid_city():
    """Проверка несуществующего города."""
    response = client.post(
        "/weather",
        data={"city": "InvalidCityNameThatDoesNotExist"},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"] == "Город не найден"


def test_weather_valid_city():
    """Проверка существующего города."""
    response = client.post(
        "/weather",
        data={"city": "Moscow"},
        headers={"Accept": "application/json"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "weather" in data
    weather = data["weather"]
    assert "temperature" in weather
    assert "windspeed" in weather
    assert "city" in weather
    assert weather["city"].lower() in ("moscow", "москва")


def test_stats_returns_counts():
    """Проверка истории просмотров."""
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert "search_counts" in data
    assert isinstance(data["search_counts"], list)
