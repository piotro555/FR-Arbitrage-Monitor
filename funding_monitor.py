import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SYMBOL = 'RSRUSDT'
BASE_URL = 'https://api.bitget.com/api/v3/market/history-fund-rate'
OUT = Path('report')
OUT.mkdir(exist_ok=True)

params = urlencode({'category': 'USDT-FUTURES', 'symbol': SYMBOL, 'limit': 20})
request = Request(BASE_URL + '?' + params, headers={'User-Agent': 'FR-Arbitrage-Monitor/1.0'})
with urlopen(request, timeout=25) as response:
    payload = json.load(response)
if payload.get('code') != '00000':
    raise RuntimeError(f'Bitget API: {payload}')
records = payload['data']['resultList']
if not records:
    raise RuntimeError('Nessun funding storico trovato')
records.sort(key=lambda item: int(item['fundingRateTimestamp']))

points = []
for record in records:
    stamp = int(record['fundingRateTimestamp'])
    rate = float(record['fundingRate'])
    points.append({'timestamp': stamp, 'date': datetime.fromtimestamp(stamp / 1000, timezone.utc), 'rate': rate})

# An annualized value is meaningful only with a known interval. For the first
# record, use the following interval if available, otherwise leave it blank.
for i, point in enumerate(points):
    if len(points) == 1:
        hours = None
    elif i == 0:
        hours = (points[1]['timestamp'] - point['timestamp']) / 3600000
    else:
        hours = (point['timestamp'] - points[i-1]['timestamp']) / 3600000
    point['hours'] = hours if hours and hours > 0 else None
    point['annual_pct'] = (point['rate'] * 100 * 8760 / hours) if point['hours'] else None

# Time-weighted annualization of realized funding settlements within the
# available lookback window, not a forecast and not compounded.
def annualized_window(hours_back):
    end = points[-1]['timestamp']
    start = end - hours_back * 3600000
    selected = [p for p in points if p['timestamp'] > start and p['hours']]
    if not selected:
        return None, 0
    total_hours = sum(p['hours'] for p in selected)
    return sum(p['rate'] for p in selected) * 100 * 8760 / total_hours, len(selected)

print('BITGET - RSRUSDT | FUNDING DEFINITIVI')
print('Data UTC            FR ciclo %    FR annuo %    Ore')
for p in points:
    annual = f"{p['annual_pct']:+.2f}%" if p['annual_pct'] is not None else 'N/D'
    hours = f"{p['hours']:.2f}" if p['hours'] else 'N/D'
    print(f"{p['date']:%Y-%m-%d %H:%M}  {p['rate']*100:+.6f}%    {annual:>9}   {hours}")

for label, hours in [('24 ore', 24), ('7 giorni', 168), ('30 giorni', 720)]:
    value, count = annualized_window(hours)
    complete = (points[-1]['timestamp'] - points[0]['timestamp']) >= hours * 3600000
    if not complete:
        print(f'Media {label}: N/D (storico insufficiente; {count} regolamenti disponibili nella finestra)')
    else:
        print(f'Media {label}: {value:+.2f}% annuo' if value is not None else f'Media {label}: N/D')

with (OUT / 'funding_rsr_bitget.csv').open('w', newline='', encoding='utf-8-sig') as file:
    writer = csv.writer(file)
    writer.writerow(['data_utc', 'fr_regolamento_pct', 'intervallo_ore', 'fr_annuo_semplice_pct'])
    for p in points:
        writer.writerow([p['date'].strftime('%Y-%m-%d %H:%M'), f"{p['rate']*100:.8f}",
                         f"{p['hours']:.4f}" if p['hours'] else '',
                         f"{p['annual_pct']:.6f}" if p['annual_pct'] is not None else ''])

fig, ax = plt.subplots(figsize=(11, 5))
ax.plot([p['date'] for p in points], [p['annual_pct'] for p in points], marker='o', linewidth=1.7)
ax.axhline(0, linestyle='--', linewidth=1)
ax.set_title('Bitget RSR/USDT - FR definitivo annualizzato (semplice)')
ax.set_xlabel('Data regolamento (UTC)')
ax.set_ylabel('FR annualizzato (%)')
ax.grid(True, alpha=0.3)
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(OUT / 'andamento_fr_annuo.png', dpi=150)
plt.close(fig)
print('Creati report/andamento_fr_annuo.png e report/funding_rsr_bitget.csv')
