"""
GridSense MCP server — Step 4: all four tools.

Tools:
  get_fuel_mix            - generation by fuel source
  get_electricity_demand  - hourly demand
  get_wholesale_prices    - retail price proxy (see note in docstring)
  get_co2_emissions       - CO2 by state, electric power sector, annual

Run standalone to sanity-check it starts:  python3 server.py
Then it's launched by Claude Desktop via claude_desktop_config.json.
"""

import os
import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["EIA_API_KEY"]
BASE = "https://api.eia.gov/v2"

mcp = FastMCP("gridsense")


async def _eia_get(route: str, params: list[tuple[str, str]]) -> list[dict]:
    """Shared helper: call an EIA /data route, return rows (or [] if none)."""
    full_params = params + [("api_key", API_KEY)]
    url = f"{BASE}/{route}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=full_params)
        resp.raise_for_status()
        body = resp.json()
    rows = body.get("response", {}).get("data", [])
    if isinstance(rows, dict):  # metadata came back instead of rows
        return []
    return rows


@mcp.tool()
async def get_fuel_mix(region: str, start: str, end: str) -> str:
    """Get hourly electricity generation broken down by fuel type for a US grid region.

    Use this to see how much power came from each energy source (natural gas,
    wind, solar, coal, nuclear, etc.) over a time window.

    Args:
        region: Balancing authority code, e.g. "ERCO" (Texas/ERCOT),
                "CISO" (California), "PJM" (mid-Atlantic), "MISO" (Midwest).
        start: Start datetime, hourly format "YYYY-MM-DDTHH", e.g. "2024-06-01T00".
        end: End datetime, same format, e.g. "2024-06-02T00".
    """
    rows = await _eia_get("electricity/rto/fuel-type-data/data", [
        ("frequency", "hourly"),
        ("data[]", "value"),
        ("facets[respondent][]", region),
        ("start", start),
        ("end", end),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "desc"),
        ("length", "500"),
    ])
    if not rows:
        return f"No fuel-mix data returned for {region} between {start} and {end}."

    totals: dict[str, float] = {}
    for r in rows:
        fuel = r.get("type-name") or r.get("fueltype", "Unknown")
        try:
            totals[fuel] = totals.get(fuel, 0.0) + float(r["value"])
        except (TypeError, ValueError, KeyError):
            continue

    lines = [f"Fuel mix for {region}, {start} to {end} (total MWh by source):"]
    for fuel, mwh in sorted(totals.items(), key=lambda x: -x[1]):
        lines.append(f"  {fuel}: {mwh:,.0f} MWh")
    return "\n".join(lines)


@mcp.tool()
async def get_electricity_demand(region: str, start: str, end: str) -> str:
    """Get hourly electricity demand for a US grid region.

    Use this to see how much power was consumed over a time window, including
    peak demand and average demand.

    Args:
        region: Balancing authority code, e.g. "ERCO", "CISO", "PJM", "MISO".
        start: Start datetime, hourly format "YYYY-MM-DDTHH".
        end: End datetime, same format.
    """
    rows = await _eia_get("electricity/rto/region-data/data", [
        ("frequency", "hourly"),
        ("data[]", "value"),
        ("facets[respondent][]", region),
        ("facets[type][]", "D"),  # D = demand
        ("start", start),
        ("end", end),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "desc"),
        ("length", "500"),
    ])
    if not rows:
        return f"No demand data returned for {region} between {start} and {end}."

    values = []
    for r in rows:
        try:
            values.append(float(r["value"]))
        except (TypeError, ValueError, KeyError):
            continue
    if not values:
        return f"Demand rows returned for {region} but none had usable values."

    peak = max(values)
    avg = sum(values) / len(values)
    low = min(values)
    return (
        f"Demand for {region}, {start} to {end} ({len(values)} hourly readings):\n"
        f"  Peak: {peak:,.0f} MWh\n"
        f"  Average: {avg:,.0f} MWh\n"
        f"  Minimum: {low:,.0f} MWh"
    )


@mcp.tool()
async def get_wholesale_prices(state: str, start: str, end: str) -> str:
    """Get monthly average electricity retail price for a US state.

    NOTE: EIA's free open-data API does not expose true wholesale/locational
    marginal prices at hourly granularity. This tool returns monthly retail
    price (cents/kWh) as a proxy for price trends. For true wholesale price
    data, a grid operator's own API (ERCOT, CAISO) would be needed.

    Args:
        state: Two-letter state code, e.g. "TX", "CA".
        start: Start month, format "YYYY-MM", e.g. "2024-01".
        end: End month, format "YYYY-MM", e.g. "2024-06".
    """
    rows = await _eia_get("electricity/retail-sales/data", [
        ("frequency", "monthly"),
        ("data[]", "price"),
        ("facets[stateid][]", state),
        ("facets[sectorid][]", "ALL"),
        ("start", start),
        ("end", end),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "desc"),
        ("length", "100"),
    ])
    if not rows:
        return f"No price data returned for {state} between {start} and {end}."

    lines = [f"Monthly avg retail electricity price for {state}, {start} to {end} (cents/kWh):"]
    for r in rows:
        period = r.get("period", "?")
        try:
            price = float(r["price"])
            lines.append(f"  {period}: {price:.2f}")
        except (TypeError, ValueError, KeyError):
            continue
    return "\n".join(lines)


@mcp.tool()
async def get_co2_emissions(state: str, start_year: str, end_year: str) -> str:
    """Get annual CO2 emissions from the electric power sector for a US state.

    Args:
        state: Two-letter state code, e.g. "TX", "CA".
        start_year: Start year, format "YYYY", e.g. "2020".
        end_year: End year, format "YYYY", e.g. "2022".
    """
    rows = await _eia_get("co2-emissions/co2-emissions-aggregates/data", [
        ("frequency", "annual"),
        ("data[]", "value"),
        ("facets[stateId][]", state),
        ("facets[sectorId][]", "EC"),  # EC = electric power sector
        ("start", start_year),
        ("end", end_year),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "desc"),
        ("length", "50"),
    ])
    if not rows:
        return f"No CO2 emissions data returned for {state} between {start_year} and {end_year}."

    lines = [f"Annual CO2 emissions, electric power sector, {state} ({start_year}-{end_year}):"]
    for r in rows:
        period = r.get("period", "?")
        try:
            value = float(r["value"])
            units = r.get("value-units", "")
            lines.append(f"  {period}: {value:,.1f} {units}")
        except (TypeError, ValueError, KeyError):
            continue
    return "\n".join(lines)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()