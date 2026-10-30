from api_connections.open_mateo import OpenMateo
from classes.jingle import Jingle

if __name__ == "__main__":
    weather = OpenMateo("11215").today()
    print(weather)

    code = weather["weather_code"]
    if not isinstance(code, int):
        raise TypeError(f"Expected an integer weather code, got {code!r}.") 

    jingle = Jingle(code)
    tune = jingle.build()
    print(f"{jingle.scale_name}: {jingle.melody_line}")
    jingle.synth.play(tune)
