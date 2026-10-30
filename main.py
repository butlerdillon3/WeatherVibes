from api_connections.open_mateo import OpenMateo
from classes.jingle import Jingle

if __name__ == "__main__":
    weather = OpenMateo("11215").today()
    print(weather)

    code = weather["weather_code"]
    if not isinstance(code, int):
        raise TypeError(f"Expected an integer weather code, got {code!r}.") 

    gust = weather["wind_gust"]
    jingle = Jingle(code, wind_gust=gust if isinstance(gust, (int, float)) else None)
    tune = jingle.build()
    saved = jingle.save()
    print(f"{jingle.scale_name} at {jingle.synth.bpm:g} bpm")
    print(f"lead:   {jingle.lead_line}")
    print(f"rhythm: {jingle.rhythm_line}")
    print(f"bass:   {jingle.bass_line}")
    print(saved)
    jingle.synth.play(tune)
