# Weather MCP server

An anonymous MCP service providing generated current weather, forecasts,
activity suggestions, and city recommendations. It has no external data
dependency; the catalog is static and readings are generated at startup.

| Tool | Purpose |
|---|---|
| `list_cities` | List supported cities and environments |
| `get_current_weather` | Return current conditions for a city |
| `get_forecast` | Return a one-to-seven-day forecast |
| `propose_activity` | Suggest activities for conditions |
| `propose_city` | Rank cities by weather, date, and environment |

## Run locally

```bash
python3 -m src.weather_mcp_server.server
```

MCP is served at <http://127.0.0.1:8093/mcp> and readiness at
<http://127.0.0.1:8093/health>. Set `WEATHER_SEED` for reproducible readings.

## Deploy and register

```bash
python3 -m scripts.deploy_weather_mcp_server
python3 -m scripts.register_weather_toolbox
```

The Container App has public ingress and no authentication. Use it only with
generated or otherwise non-sensitive data.