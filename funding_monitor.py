
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode

EXCHANGE = "Bitget"
SYMBOL = "RSRUSDT"

URL = "https://api.bitget.com/api/v3/market/history-fund-rate"

params = urlencode({
    "category": "USDT-FUTURES",
    "symbol": SYMBOL,
    "limit": 20
})

print("FR ARBITRAGE MONITOR")
print("Exchange:", EXCHANGE)
print("Token:", SYMBOL)
print("Solo funding storici definitivi")
print("-" * 65)

try:
    request = Request(
        URL + "?" + params,
        headers={"User-Agent": "FR-Arbitrage-Monitor/1.0"}
    )

    with urlopen(request, timeout=20) as response:
        result = json.load(response)

    if result.get("code") != "00000":
        raise RuntimeError(
            "Errore API Bitget: " + str(result)
        )

    records = result["data"]["resultList"]

    if not records:
        raise RuntimeError("Nessun regolamento disponibile")

    records = sorted(
        records,
        key=lambda x: int(x["fundingRateTimestamp"])
    )

    previous_ts = None

    print("DATA UTC             FR %          CICLO ORE")
    print("-" * 65)

    for item in records:
        ts = int(item["fundingRateTimestamp"])
        rate = float(item["fundingRate"]) * 100

        date = datetime.fromtimestamp(
            ts / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M")

        if previous_ts is None:
            interval = "-"
        else:
            hours = (ts - previous_ts) / 3600000
            interval = f"{hours:.2f}"

        print(f"{date}    {rate:+.6f}%       {interval}")

        previous_ts = ts

    print("-" * 65)
    print("Regolamenti recuperati:", len(records))
    print("TEST API COMPLETATO")

except Exception as error:
    print("ERRORE:", error)
    raise
