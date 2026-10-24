"""Travel-planner tools for the WanderWise agent.

These are deliberately self-contained (deterministic mock data) so the demo is
reproducible and needs no third-party travel APIs or keys. The point of the
project is the *routing decision*, not live flight prices. Each tool is a plain
Strands ``@tool``; swap the bodies for real APIs without touching the router.
"""

from __future__ import annotations

from strands import tool


@tool
def search_flights(origin: str, destination: str, date: str = "flexible") -> str:
    """Find flight options between two cities.

    Args:
        origin: Departure city or airport.
        destination: Arrival city or airport.
        date: Travel date (free text; defaults to flexible).
    """
    return (
        f"Flights {origin} -> {destination} on {date}:\n"
        f"  - VN310  07:05-13:40  nonstop   $218\n"
        f"  - JL752  09:30-16:10  nonstop   $264\n"
        f"  - CX influence 1-stop (HKG)     $189 (cheapest)"
    )


@tool
def find_hotels(city: str, check_in: str = "", nights: int = 3) -> str:
    """Find hotel options in a city.

    Args:
        city: City to stay in.
        check_in: Check-in date (free text).
        nights: Number of nights.
    """
    return (
        f"Hotels in {city} ({nights} nights from {check_in or 'TBD'}):\n"
        f"  - Sakura Inn        3*  $82/night   central, great reviews\n"
        f"  - Grand Bay Hotel   4*  $141/night  near station\n"
        f"  - Capsule Nova      2*  $39/night   budget, tiny rooms"
    )


@tool
def suggest_activities(city: str, interest: str = "general") -> str:
    """Suggest things to do in a city.

    Args:
        city: City to explore.
        interest: Optional interest (food, history, nature, nightlife...).
    """
    return (
        f"Top {interest} activities in {city}:\n"
        f"  - Old Town walking food tour (3h)\n"
        f"  - Sunrise temple visit + tea ceremony\n"
        f"  - Night market + river cruise"
    )


@tool
def check_weather(city: str, when: str = "this week") -> str:
    """Check the weather forecast for a city.

    Args:
        city: City to check.
        when: Time window (free text).
    """
    return (
        f"Weather for {city} ({when}):\n"
        f"  - Highs 24-27C, lows 18-20C\n"
        f"  - Partly cloudy, 30% chance of rain Thu\n"
        f"  - Pack a light jacket for evenings"
    )


@tool
def estimate_budget(city: str, days: int = 3, style: str = "mid-range") -> str:
    """Estimate a trip budget.

    Args:
        city: Destination city.
        days: Trip length in days.
        style: budget | mid-range | luxury.
    """
    per_day = {"budget": 55, "mid-range": 130, "luxury": 340}.get(style, 130)
    total = per_day * days
    return (
        f"Estimated {style} budget for {days} days in {city}:\n"
        f"  - Lodging + food + local transport: ~${per_day}/day\n"
        f"  - Trip total (excl. flights): ~${total}"
    )


ALL_TOOLS = [
    search_flights,
    find_hotels,
    suggest_activities,
    check_weather,
    estimate_budget,
]

# One-line descriptions used by the DeciderToolRouter as choice options.
TOOL_DESCRIPTIONS = {
    "search_flights": "the user wants to find, compare, or book flights",
    "find_hotels": "the user wants lodging, hotels, or accommodation",
    "suggest_activities": "the user wants things to do, attractions, or itineraries",
    "check_weather": "the user wants the weather or climate forecast",
    "estimate_budget": "the user wants trip costs or a budget estimate",
}
