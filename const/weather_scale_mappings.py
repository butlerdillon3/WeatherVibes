WEATHER_NAMES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    97: "Heavy thunderstorm",
    99: "Thunderstorm with heavy hail",
}

WEATHER_SCALES = {
    0: "major",
    1: "major",
    2: "lydian",
    3: "mixolydian",
    45: "minor",
    48: "locrian",
    51: "dorian",
    53: "minor",
    55: "phrygian",
    56: "phrygian",
    57: "locrian",
    61: "dorian",
    63: "minor",
    65: "phrygian",
    66: "phrygian",
    67: "locrian",
    71: "major",
    73: "lydian",
    75: "minor",
    77: "pentatonic_minor",
    80: "major",
    81: "mixolydian",
    82: "harmonic_minor",
    85: "pentatonic_major",
    86: "pentatonic_minor",
    95: "minor",
    96: "diminished",
    97: "phrygian",
    99: "whole_tone",
}

# (name, minimum gust in mph, bpm added to the jingle's base tempo).
# Gusts below a strong breeze are left off, so they do not change the tempo.
WIND_BPM = (
    ("strong_breeze", 25, 10),
    ("near_gale", 32, 20),
    ("gale", 39, 30),
    ("strong_gale", 47, 40),
    ("storm", 55, 50),
    ("violent_storm", 64, 60),
    ("hurricane", 73, 70),
)


def bpm_for_gust(gust_mph: float | None, base_bpm: float = 120) -> float:
    """Add the high-wind tempo step for this gust to the base tempo."""
    if gust_mph is None:
        return base_bpm
    added = 0
    for _name, minimum, extra in WIND_BPM:
        if gust_mph < minimum:
            break
        added = extra
    return base_bpm + added