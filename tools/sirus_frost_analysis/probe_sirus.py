import json
from pathlib import Path
import requests

URL='https://sirus.su/api/base/x1/leaderboard/pve'
OUT=Path('artifacts/sirus_frost/probe_results.json')
OUT.parent.mkdir(parents=True, exist_ok=True)
S=requests.Session(); S.headers.update({'User-Agent':'Mozilla/5.0','Accept':'application/json'})

BASE={'ladder':'specializations','type':'dps','aggregation':'avg','page':1,'i':38,'boss':1,'perPage':50}
variants={
 'old_range': {**BASE,'week_from':'2026-07-23','week_to':'2026-08-18'},
 'exact_four_weeks_default': {**BASE,'week_from':'2026-07-16','week_to':'2026-08-19'},
 'exact_four_weeks_70': {**BASE,'week_from':'2026-07-16','week_to':'2026-08-19','parsings':70},
 'exact_four_weeks_40': {**BASE,'week_from':'2026-07-16','week_to':'2026-08-19','parsings':40},
 'exact_two_weeks_70': {**BASE,'week_from':'2026-07-30','week_to':'2026-08-19','parsings':70},
 'exact_two_weeks_40': {**BASE,'week_from':'2026-07-30','week_to':'2026-08-19','parsings':40},
 'current_70': {**BASE,'week_from':'2026-08-13','week_to':'2026-08-19','parsings':70},
 'current_40': {**BASE,'week_from':'2026-08-13','week_to':'2026-08-19','parsings':40},
}

def summarize(data, req_url):
    rows=data.get('data') or []
    frost=next((r for r in rows if r.get('class_id')==6 and r.get('spec')==1),None)
    dates=sorted({str(r.get('datetime')) for r in rows if r.get('datetime')})
    links=data.get('links') or {}
    return {
      'request_url': req_url,
      'returned_first_link': links.get('first'),
      'row_count': len(rows),
      'min_datetime': dates[0] if dates else None,
      'max_datetime': dates[-1] if dates else None,
      'frost_row': frost,
      'rows': rows,
      'meta': data.get('meta'),
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
