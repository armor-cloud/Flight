import json
from pathlib import Path
import requests

URL='https://sirus.su/api/base/x1/leaderboard/pve'
OUT=Path('artifacts/sirus_frost/probe_results.json')
OUT.parent.mkdir(parents=True, exist_ok=True)
S=requests.Session(); S.headers.update({'User-Agent':'Mozilla/5.0','Accept':'application/json'})

variants={
 'old_range_i': {'ladder':'specializations','type':'dps','aggregation':'avg','week_from':'2026-07-23','week_to':'2026-08-18','per_page':500,'page':1,'i':38,'boss':1},
 'four_weeks_70': {'ladder':'specializations','type':'dps','aggregation':'avg','week':'last_four_weeks','order':38,'boss':1,'parsings':70,'perPage':50,'page':1},
 'four_weeks_40': {'ladder':'specializations','type':'dps','aggregation':'avg','week':'last_four_weeks','order':38,'boss':1,'parsings':40,'perPage':50,'page':1},
 'two_weeks_40': {'ladder':'specializations','type':'dps','aggregation':'avg','week':'last_two_weeks','order':38,'boss':1,'parsings':40,'perPage':50,'page':1},
 'two_weeks_70': {'ladder':'specializations','type':'dps','aggregation':'avg','week':'last_two_weeks','order':38,'boss':1,'parsings':70,'perPage':50,'page':1},
 'range_with_week': {'ladder':'specializations','type':'dps','aggregation':'avg','week':'range','week_from':'2026-07-23','week_to':'2026-08-18','order':38,'boss':1,'parsings':70,'perPage':50,'page':1},
}

def summarize(data, req_url):
    rows=data.get('data') or []
    frost=next((r for r in rows if r.get('class_id')==6 and r.get('spec')==1),None)
    dates=sorted({str(r.get('datetime')) for r in rows if r.get('datetime')})
    links=data.get('links') or {}
    return {
      'request_url': req_url,
      'returned_first_link': links.get('first'),
      'returned_last_link': links.get('last'),
      'row_count': len(rows),
      'min_datetime': dates[0] if dates else None,
      'max_datetime': dates[-1] if dates else None,
      'frost_row': frost,
      'weeks': data.get('weeks'),
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
