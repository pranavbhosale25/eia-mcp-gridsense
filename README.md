# eia-api-gridsense

An MCP server exposing US electricity grid data from the [EIA API](https://www.eia.gov/opendata/):

- `get_fuel_mix` — hourly generation by fuel source for a grid region
- `get_electricity_demand` — hourly demand for a grid region
- `get_wholesale_prices` — monthly retail price proxy for a state
- `get_co2_emissions` — annual CO2 emissions by state, electric power sector

## Setup

Requires an EIA API key: https://www.eia.gov/opendata/register.php

Set it as an environment variable (or in a local `.env` file, never committed):

```
EIA_API_KEY=your-key-here
```

## Usage with Claude Desktop

```json
{
  "mcpServers": {
    "eia-api-gridsense": {
      "command": "uvx",
      "args": ["eia-api-gridsense"],
      "env": {
        "EIA_API_KEY": "your-key-here"
      }
    }
  }
}
```

<!-- mcp-name: io.github.pranavbhosale25/eia-api-gridsense -->
