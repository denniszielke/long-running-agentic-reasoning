"""Build and deploy the weather MCP server as an Azure Container App."""

from __future__ import annotations

from scripts._helpers import ROOT, acr_build, deploy_container_app, env, load_env, save_env, tag_from_cli

APP_NAME = "weather-mcp-server"
PORT = 8093


def main(tag: str | None = None) -> None:
    load_env()
    image = acr_build(APP_NAME, ROOT / "src" / "weather_mcp_server" / "Dockerfile", tag=tag)
    container_env = {
        "WEATHER_MCP_HOST": "0.0.0.0",
        "WEATHER_MCP_PORT": str(PORT),
        "IMAGE_TAG": image.rsplit(":", 1)[-1],
    }
    if connection_string := env("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        container_env["APPLICATIONINSIGHTS_CONNECTION_STRING"] = connection_string
    if seed := env("WEATHER_SEED"):
        container_env["WEATHER_SEED"] = seed

    url = deploy_container_app(
        APP_NAME,
        image,
        target_port=PORT,
        env_vars=container_env,
        cpu=env("WEATHER_MCP_CPU", "1"),
        memory=env("WEATHER_MCP_MEMORY", "2.0Gi"),
        readiness_path="/health",
        min_replicas=int(env("WEATHER_MCP_MIN_REPLICAS", "1")),
    )
    mcp_url = f"{url.rstrip('/')}/mcp"
    save_env({"WEATHER_MCP_URL": mcp_url, "WEATHER_MCP_IMAGE": image})
    print(f"\nWeather MCP server ready: {mcp_url}")


if __name__ == "__main__":
    main(tag_from_cli())