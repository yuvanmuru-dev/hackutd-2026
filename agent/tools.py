"""Public-data tools the agent can call. No API keys needed for any of these.

Every tool returns a dict with a "source" URL so the final report can cite it.
Verify each endpoint once on prep day (APIs change). If one breaks mid-hackathon,
the agent should report "could not verify" instead of guessing.
"""
from __future__ import annotations

import requests

TIMEOUT = 20
UA = {"User-Agent": "hackutd-groundtruth-demo/0.1 (student hackathon project)"}


def geocode_address(address: str) -> dict:
    """US Census geocoder: address -> lat/lon + state/county/tract FIPS."""
    url = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
    }
    r = requests.get(url, params=params, timeout=TIMEOUT, headers=UA)
    r.raise_for_status()
    matches = r.json().get("result", {}).get("addressMatches", [])
    if not matches:
        return {"found": False, "source": r.url}
    m = matches[0]
    tract = (m.get("geographies", {}).get("Census Tracts") or [{}])[0]
    return {
        "found": True,
        "matched_address": m.get("matchedAddress"),
        "lat": m["coordinates"]["y"],
        "lon": m["coordinates"]["x"],
        "state_fips": tract.get("STATE"),
        "county_fips": tract.get("COUNTY"),
        "tract": tract.get("TRACT"),
        "source": r.url,
    }


def flood_zone(lat: float, lon: float) -> dict:
    """FEMA National Flood Hazard Layer: which flood zone is this point in?"""
    url = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF",
        "returnGeometry": "false",
        "f": "json",
    }
    r = requests.get(url, params=params, timeout=TIMEOUT, headers=UA)
    r.raise_for_status()
    feats = r.json().get("features", [])
    if not feats:
        return {"mapped": False, "note": "No NFHL polygon at this point (unmapped or outside coverage).", "source": r.url}
    a = feats[0]["attributes"]
    return {
        "mapped": True,
        "flood_zone": a.get("FLD_ZONE"),
        "zone_subtype": a.get("ZONE_SUBTY"),
        "special_flood_hazard_area": a.get("SFHA_TF") == "T",
        "source": r.url,
    }


def neighborhood_stats(state_fips: str, county_fips: str, tract: str) -> dict:
    """Census ACS 5-year: median home value, household income, gross rent for the tract."""
    url = "https://api.census.gov/data/2023/acs/acs5"
    params = {
        "get": "NAME,B25077_001E,B19013_001E,B25064_001E",
        "for": f"tract:{tract}",
        "in": f"state:{state_fips} county:{county_fips}",
    }
    r = requests.get(url, params=params, timeout=TIMEOUT, headers=UA)
    r.raise_for_status()
    header, row = r.json()[0], r.json()[1]
    d = dict(zip(header, row))

    def num(v):
        try:
            n = int(v)
            return n if n >= 0 else None  # Census uses negative sentinels for "no data"
        except (TypeError, ValueError):
            return None

    return {
        "area": d.get("NAME"),
        "median_home_value_usd": num(d.get("B25077_001E")),
        "median_household_income_usd": num(d.get("B19013_001E")),
        "median_gross_rent_usd": num(d.get("B25064_001E")),
        "source": r.url,
    }


def nearby_amenities(lat: float, lon: float, radius_m: int = 1000) -> dict:
    """OpenStreetMap Overpass: count schools, grocery, transit, parks, hospitals nearby."""
    url = "https://overpass-api.de/api/interpreter"
    kinds = {
        "school": 'nwr["amenity"="school"]',
        "grocery": 'nwr["shop"~"supermarket|grocery"]',
        "transit_stop": 'nwr["public_transport"="platform"]',
        "park": 'nwr["leisure"="park"]',
        "hospital": 'nwr["amenity"="hospital"]',
    }
    out = {}
    for name, sel in kinds.items():
        q = f"[out:json][timeout:20];{sel}(around:{radius_m},{lat},{lon});out count;"
        r = requests.post(url, data={"data": q}, timeout=TIMEOUT, headers=UA)
        r.raise_for_status()
        els = r.json().get("elements", [])
        out[name] = int(els[0]["tags"]["total"]) if els else 0
    return {"radius_m": radius_m, "counts": out, "source": "https://www.openstreetmap.org (via Overpass API)"}


# ---- OpenAI-style tool schemas (what Nemotron sees) ----
TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "geocode_address",
        "description": "Resolve a US street address to coordinates and Census tract. Call this first.",
        "parameters": {"type": "object", "properties": {"address": {"type": "string"}}, "required": ["address"]}}},
    {"type": "function", "function": {
        "name": "flood_zone",
        "description": "FEMA flood zone for a coordinate. Use to verify flood-related listing claims.",
        "parameters": {"type": "object", "properties": {"lat": {"type": "number"}, "lon": {"type": "number"}}, "required": ["lat", "lon"]}}},
    {"type": "function", "function": {
        "name": "neighborhood_stats",
        "description": "Census ACS tract stats: median home value, income, rent. Use to sanity-check price claims.",
        "parameters": {"type": "object", "properties": {
            "state_fips": {"type": "string"}, "county_fips": {"type": "string"}, "tract": {"type": "string"}},
            "required": ["state_fips", "county_fips", "tract"]}}},
    {"type": "function", "function": {
        "name": "nearby_amenities",
        "description": "Counts of schools, grocery, transit stops, parks, hospitals within a radius. Use to verify 'walkable', 'near schools', etc.",
        "parameters": {"type": "object", "properties": {
            "lat": {"type": "number"}, "lon": {"type": "number"}, "radius_m": {"type": "integer", "default": 1000}},
            "required": ["lat", "lon"]}}},
]

TOOLS = {
    "geocode_address": geocode_address,
    "flood_zone": flood_zone,
    "neighborhood_stats": neighborhood_stats,
    "nearby_amenities": nearby_amenities,
}
