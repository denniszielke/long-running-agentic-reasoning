"""Register the deployed weather MCP server as a Foundry toolbox."""

from __future__ import annotations

from scripts._helpers import env, load_env, project_client, save_env


def main() -> None:
    load_env()
    name = env("WEATHER_TOOLBOX_NAME", "weather-tools")
    mcp_url = env("WEATHER_MCP_URL", required=True)
    project_endpoint = env("AZURE_AI_PROJECT_ENDPOINT", required=True).rstrip("/")

    from azure.ai.projects.models import MCPToolboxTool
    from azure.core.exceptions import ResourceNotFoundError

    with project_client() as client:
        try:
            client.toolboxes.delete(name=name)
            print(f"  ↳ removed existing toolbox '{name}'")
        except ResourceNotFoundError:
            pass
        created = client.toolboxes.create_version(
            name=name,
            description="Generated current weather, forecasts, and city recommendations.",
            tools=[MCPToolboxTool(server_label="weather", server_url=mcp_url, require_approval="never")],
        )

    endpoint = f"{project_endpoint}/toolboxes/{name}/versions/{created.version}/mcp?api-version=v1"
    save_env({"WEATHER_TOOLBOX_NAME": name, "FOUNDRY_TOOLBOX_ENDPOINT": endpoint})
    print(f"Registered toolbox '{name}' version {created.version}")


if __name__ == "__main__":
    main()