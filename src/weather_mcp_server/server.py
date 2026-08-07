"""Anonymous generated-weather tools served over streamable HTTP MCP."""

from __future__ import annotations

import json
import logging
import os

os.environ.setdefault("FASTMCP_CHECK_FOR_UPDATES", "off")

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.weather_mcp_server.weather_data import WeatherStore

_HOST = os.getenv("WEATHER_MCP_HOST", "127.0.0.1")
_PORT = int(os.getenv("WEATHER_MCP_PORT", "8093"))
logger = logging.getLogger("weather_mcp_server")

if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(logger_name="weather_mcp_server")
    except Exception:  # noqa: BLE001
        logger.warning("Application Insights instrumentation could not be configured", exc_info=True)

_store = WeatherStore()
mcp = FastMCP(
    name="weather",
    instructions=(
        "Use these tools for generated current weather, forecasts, activities, "
        "and city recommendations. Temperatures are in degrees Celsius."
    ),
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.tool()
def list_cities() -> str:
    """List supported cities, climates, and environments."""
    return json.dumps({"cities": _store.cities()}, indent=2)


@mcp.tool()
def get_current_weather(city: str) -> str:
    """Get current generated weather for a city."""
    reading = _store.current(city)
    if reading is None:
        return json.dumps({"error": f"Unknown city '{city}'.", "known_cities": _store.city_names()}, indent=2)
    return json.dumps(reading, indent=2)


@mcp.tool()
def get_forecast(city: str, days: int = 3) -> str:
    """Get a generated one-to-seven-day forecast for a city."""
    forecast = _store.forecast(city, days)
    if forecast is None:
        return json.dumps({"error": f"Unknown city '{city}'.", "known_cities": _store.city_names()}, indent=2)
    return json.dumps(forecast, indent=2)


@mcp.tool()
def propose_activity(city: str, conditions: str) -> str:
    """Propose activities for a city and expected conditions."""
    return json.dumps(_store.propose_activity(city, conditions), indent=2)


@mcp.tool()
def propose_city(
    conditions: str | None = None,
    date: str | None = None,
    environment: str | None = None,
) -> str:
    """Rank cities by desired weather, date, environment, or a combination."""
    return json.dumps(
        _store.propose_city(conditions=conditions, on_date=date, environment=environment),
        indent=2,
    )


def main() -> None:
    logging.basicConfig(level=os.environ.get("MCP_LOG_LEVEL", "INFO"))
    logger.info("Starting weather MCP server - image_tag=%s", os.getenv("IMAGE_TAG", "unknown"))
    try:
        mcp.run(transport="http", host=_HOST, port=_PORT, host_origin_protection=False)
    except TypeError:
        mcp.run(transport="http", host=_HOST, port=_PORT)


if __name__ == "__main__":
    main()