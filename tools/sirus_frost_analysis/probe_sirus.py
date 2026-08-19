import json
from pathlib import Path
import requests

URL='https://sirus.su/api/base/x1/leaderboard/pve'
OUT=Path('artifacts/sirus_frost/probe_results.json')
OUT.parent.mkdir(parents=True, exist_ok=True)
S=requests.Session(); S.headers.update({'User-Agent':'Mozilla/5.0','Accept':'application/json'})

# Use the API's own canonical raid parameter (order), not the frontend alias i.
BASE={'ladder':'specializations','type':'dps','aggregation':'avg','page':1,'order':38,'boss':1,'perPage':50,'parsings':40}
variants={
 'control_current': BASE,
 'week_from_to': {**BASE,'week_from':'2026-07-16','week_to':'2026-08-19'},
 'from_to': {**BASE,'from':'2026-07-16','to':'2026-08-19'},
 'date_from_to': {**BASE,'date_from':'2026-07-16','date_to':'2026-08-19'},
 'start_end': {**BASE,'start':'2026-07-16','end':'2026-08-19'},
 'start_date_end_date': {**BASE,'start_date':'2026-07-16','end_date':'2026-08-19'},
 'weekFrom_weekTo': {**BASE,'weekFrom':'2026-07-16','weekTo':'2026-08-19'},
 'period_from_to': {**BASE,'period_from':'2026-07-16','period_to':'2026-08-19'},
 # Also test a concrete weekly interval returned by Sirus itself.
 'concrete_week_0723': {**BASE,'week_from':'2026-07-23','week_to':'2026-07-30'},
 'concrete_week_from_to': {**BASE,'from':'2026-07-23','to':'2026-07-30'},
}

def summarize(data, req_url):
    rows=data.get('data') or []
    frost=next((r for r in rows if r.get('class_id')==6 and r.get('spec')==1),None)
    dates=sorted({str(r.get('datetime')) for r in rows if r.get('datetime')})
    return {
      'request_url': req_url,
      'returned_first_link': (data.get('links') or {}).get('first'),
      'row_count': len(rows),
      'min_datetime': dates[0] if dates else None,
      'max_datetime': dates[-1] if dates else None,
      'frost_dps': frost.get('dps') if frost else None,
      'frost_datetime': frost.get('datetime') if frost else None,
      'frost_bossfight_id': frost.get('bossfight_id') if frost else None,
      'meta_total': (data.get('meta') or {}).get('total'),
    }

results={}
for name,params in variants.items():
    try:
      r=S.get(URL,params=params,timeout=45); r.raise_for_status(); data=r.json()
      results[name]=summarize(data,r.url)
    except Exception as e:
      results[name]={'error':repr(e)}

OUT.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2))
