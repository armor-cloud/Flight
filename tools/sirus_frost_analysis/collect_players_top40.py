import csv
import json
import math
import statistics
import time
from pathlib import Path
import requests

BASE='https://sirus.su/api/base/x1/leaderboard/pve'
OUT=Path('artifacts/sirus_frost/player_top40')
RAW=OUT/'raw'
RAW.mkdir(parents=True,exist_ok=True)

PERIODS={
 'four_weeks':('2026-07-16','2026-08-19'),
 'two_weeks':('2026-07-30','2026-08-19'),
}
BOSSES=[
 (38,0,'TK','Alar'),(38,1,'TK','Void Reaver'),(38,2,'TK','Solarian'),(38,3,'TK','Kaelthas'),
 (39,0,'SSC','Hydross'),(39,1,'SSC','Lurker'),(39,2,'SSC','Leotheras'),(39,3,'SSC','Karathress'),
 (39,4,'SSC','Morogrim'),(39,5,'SSC','Lady Vashj'),
]
SPEC_NAMES={
 (1,0):'Arms Warrior',(1,1):'Fury Warrior',(2,2):'Retribution Paladin',
 (3,0):'Beast Mastery Hunter',(3,1):'Marksmanship Hunter',(3,2):'Survival Hunter',
 (4,0):'Assassination Rogue',(4,1):'Combat Rogue',(4,2):'Subtlety Rogue',
 (5,2):'Shadow Priest',(6,0):'Blood DK',(6,1):'Frost DK',(6,2):'Unholy DK',
 (7,0):'Elemental Shaman',(7,1):'Enhancement Shaman',(8,0):'Arcane Mage',(8,1):'Fire Mage',(8,2):'Frost Mage',
 (9,0):'Affliction Warlock',(9,1):'Demonology Warlock',(9,2):'Destruction Warlock',
 (11,0):'Balance Druid',(11,1):'Feral Druid'
}
MELEE={(1,0),(1,1),(2,2),(4,0),(4,1),(4,2),(6,0),(6,1),(6,2),(7,1),(11,1)}
FROST=(6,1); UH=(6,2)

S=requests.Session(); S.headers.update({'User-Agent':'Mozilla/5.0','Accept':'application/json'})

def get(params):
  last=None
  for a in range(3):
    try:
      r=S.get(BASE,params=params,timeout=45); r.raise_for_status(); return r.json(),r.url
    except Exception as e:
      last=e; time.sleep(3*(a+1))
  raise RuntimeError(last)

def fetch_spec(period,wf,wt,order,boss_id,key):
  cls,spec=key; p=1; rows=[]; urls=[]
  while True:
    params={'ladder':'players','type':'dps','aggregation':'max','week_from':wf,'week_to':wt,'page':p,
            'i':order,'boss':boss_id,'specs':f'{cls}:{spec}'}
    js,url=get(params); chunk=js.get('data') or []; rows.extend(chunk); urls.append(url)
    rawdir=RAW/period/f'{order}_{boss_id}'/f'{cls}_{spec}'; rawdir.mkdir(parents=True,exist_ok=True)
    (rawdir/f'p{p}.json').write_text(json.dumps(js,ensure_ascii=False,indent=2),encoding='utf-8')
    last=int((js.get('meta') or {}).get('last_page') or 1)
    if p>=last: break
    p+=1; time.sleep(.1)
  # keep only exact intended HM boss rows as a hard audit guard
  expected_map=550 if order==38 else 548
  exact=[r for r in rows if r.get('map_id')==expected_map and r.get('difficulty')==3 and r.get('encounter_id')==boss_id and r.get('dps') is not None]
  return exact,urls

def top_fraction(rows,fraction):
  vals=sorted([float(r['dps']) for r in rows],reverse=True)
  if not vals: return [],None
  n=max(1,math.ceil(len(vals)*fraction))
  selected=vals[:n]
  return selected,statistics.median(selected)

def pct(a,b): return None if a is None or not b else round((a/b-1)*100,2)

spec_rows=[]; boss_rows=[]; proof=[]
for period,(wf,wt) in PERIODS.items():
  for order,boss_id,raid,boss in BOSSES:
    meds40={}; meds70={}; counts={}
    for key,name in SPEC_NAMES.items():
      rows,urls=fetch_spec(period,wf,wt,order,boss_id,key)
      sel40,m40=top_fraction(rows,.40); sel70,m70=top_fraction(rows,.70)
      counts[key]=len(rows)
      if m40 is not None: meds40[key]=m40
      if m70 is not None: meds70[key]=m70
      spec_rows.append({'period':period,'week_from':wf,'week_to':wt,'raid':raid,'boss':boss,
                        'class_id':key[0],'spec_id':key[1],'spec':name,'raw_logs':len(rows),
                        'top40_logs':len(sel40),'top40_median':m40,'top70_logs':len(sel70),'top70_median':m70,
                        'source_url':urls[0] if urls else None})
      if key==FROST:
        for r in rows:
          proof.append({'period':period,'raid':raid,'boss':boss,'name':r.get('name'),'dps':r.get('dps'),'ilvl':r.get('ilvl'),
                        'bossfight_id':r.get('bossfight_id'),'datetime':r.get('datetime'),'duration':r.get('duration'),
                        'map_id':r.get('map_id'),'difficulty':r.get('difficulty'),'encounter_id':r.get('encounter_id'),
                        'source_url':urls[0] if urls else None})
    f=meds40.get(FROST); u=meds40.get(UH)
    allvals=list(meds40.values()); meleevals=[v for k,v in meds40.items() if k in MELEE]
    overall=statistics.median(allvals) if allvals else None; melee=statistics.median(meleevals) if meleevals else None
    ranking=sorted(meds40.items(),key=lambda kv:kv[1],reverse=True)
    rank=next((i+1 for i,(k,v) in enumerate(ranking) if k==FROST),None)
    boss_rows.append({'period':period,'week_from':wf,'week_to':wt,'raid':raid,'boss':boss,
                      'frost_top40_median':f,'frost_raw_logs':counts.get(FROST,0),'frost_top40_logs':max(1,math.ceil(counts.get(FROST,0)*.4)) if counts.get(FROST,0) else 0,
                      'frost_rank':rank,'specs_present':len(ranking),'all_spec_median':overall,'frost_vs_all_pct':pct(f,overall),
                      'melee_spec_median':melee,'frost_vs_melee_pct':pct(f,melee),'unholy_top40_median':u,'frost_vs_unholy_pct':pct(f,u)})

for path,rows in [(OUT/'spec_summary.csv',spec_rows),(OUT/'boss_summary.csv',boss_rows),(OUT/'frost_proof.csv',proof)]:
  with path.open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

(OUT/'run_info.json').write_text(json.dumps({
 'method':'For each boss/spec: fetch exact Sirus player fight rows, hard-filter map+difficulty+encounter, sort DPS descending, keep ceil(40%) best logs, median.',
 'secondary':'Also compute top70 median for low-volume sensitivity check.',
 'ilvl_filter':None,'aggregation_request':'max','difficulty':3,'periods':PERIODS
},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(boss_rows,ensure_ascii=False,indent=2))
