import csv
import json
import statistics
import time
from pathlib import Path
import requests

BASE='https://sirus.su/api/base/x1/leaderboard/pve'
DETAIL='https://sirus.su/api/base/x1/details/bossfight/{fight_id}'
OUT=Path('artifacts/sirus_frost/final')
RAW=OUT/'raw'
for p in [OUT, RAW/'specializations', RAW/'players_frost', RAW/'bossfights']:
    p.mkdir(parents=True, exist_ok=True)

PERIODS={
    'four_weeks_40': {'week_from':'2026-07-16','week_to':'2026-08-19','parsings':40},
    'two_weeks_40': {'week_from':'2026-07-30','week_to':'2026-08-19','parsings':40},
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
 (9,0):'Affliction Warlock',(9,1):'Demonology Warlock',(9,2):'Destruction Warlock',(11,0):'Balance Druid',(11,1):'Feral Druid'
}
DPS=set(SPEC_NAMES)
MELEE={(1,0),(1,1),(2,2),(4,0),(4,1),(4,2),(6,0),(6,1),(6,2),(7,1),(11,1)}
FROST=(6,1); UH=(6,2)

S=requests.Session(); S.headers.update({'User-Agent':'Mozilla/5.0','Accept':'application/json','Accept-Language':'ru-RU,ru;q=0.9,en;q=0.8'})

def get(url,params=None):
    last=None
    for a in range(3):
        try:
            r=S.get(url,params=params,timeout=45); r.raise_for_status(); return r.json(),r.url
        except Exception as e:
            last=e; time.sleep(3*(a+1))
    raise RuntimeError(last)

def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def pct(a,b): return None if a is None or not b else round((a/b-1)*100,2)

summary=[]; spec_long=[]; frost_proof=[]; manifests=[]; fetched_details=set()

for period,pv in PERIODS.items():
  for order,boss_id,raid,boss in BOSSES:
    # Authoritative specialization table. NOTE: specialization endpoint needs `order`, not `i`.
    sp={
      'ladder':'specializations','type':'dps','aggregation':'avg','page':1,'perPage':50,
      'order':order,'boss':boss_id,'parsings':pv['parsings'],'week_from':pv['week_from'],'week_to':pv['week_to']
    }
    js,url=get(BASE,sp); rows=js.get('data') or []
    dump(RAW/'specializations'/f'{period}_{raid}_{boss.replace(" ","_")}.json',js)
    manifests.append({'period':period,'dataset':'specializations','raid':raid,'boss':boss,'url':url,'rows':len(rows)})

    med={}
    for r in rows:
      key=(r.get('class_id'),r.get('spec'))
      if key not in DPS or r.get('dps') is None: continue
      med[key]=float(r['dps'])
      spec_long.append({
        'period':period,'raid':raid,'boss':boss,'class_id':key[0],'spec_id':key[1],
        'spec':SPEC_NAMES[key],'dps':r['dps'],'map_id':r.get('map_id'),'difficulty':r.get('difficulty'),
        'encounter_id':r.get('encounter_id'),'bossfight_id':r.get('bossfight_id'),'datetime':r.get('datetime'),'duration':r.get('duration'),
        'source_url':url
      })

    f=med.get(FROST); u=med.get(UH)
    vals=[v for k,v in med.items() if k in DPS]; melees=[v for k,v in med.items() if k in MELEE]
    overall=statistics.median(vals) if vals else None; melee=statistics.median(melees) if melees else None
    ranking=sorted(med.items(),key=lambda kv:kv[1],reverse=True)
    rank=next((i+1 for i,(k,v) in enumerate(ranking) if k==FROST),None)

    # Frost player ladder for proof/sample. This is the contract used by LazyCatBot: i + specs + week_from/week_to.
    p=1; player_rows=[]; page_urls=[]
    while True:
      pp={
        'ladder':'players','type':'dps','aggregation':'max','week_from':pv['week_from'],'week_to':pv['week_to'],
        'page':p,'i':order,'boss':boss_id,'specs':'6:1'
      }
      pj,purl=get(BASE,pp); chunk=pj.get('data') or []; player_rows.extend(chunk); page_urls.append(purl)
      last=int((pj.get('meta') or {}).get('last_page') or 1)
      dump(RAW/'players_frost'/f'{period}_{raid}_{boss.replace(" ","_")}_p{p}.json',pj)
      if p>=last: break
      p+=1; time.sleep(.25)
    manifests.append({'period':period,'dataset':'players_frost','raid':raid,'boss':boss,'url':' | '.join(page_urls),'rows':len(player_rows)})

    ids=[]
    for pr in player_rows:
      fid=pr.get('bossfight_id')
      if fid: ids.append(int(fid))
      frost_proof.append({
        'period':period,'raid':raid,'boss':boss,'name':pr.get('name'),'dps':pr.get('dps'),'ilvl':pr.get('ilvl'),
        'bossfight_id':fid,'datetime':pr.get('datetime'),'duration':pr.get('duration'),'rank':pr.get('rank'),
        'map_id':pr.get('map_id'),'difficulty':pr.get('difficulty'),'encounter_id':pr.get('encounter_id'),
        'source_url':page_urls[0] if page_urls else None
      })

    # Save a bounded set of concrete fight details for manual verification.
    detail_ok=0
    for fid in list(dict.fromkeys(ids))[:12]:
      if fid in fetched_details: continue
      try:
        dj,durl=get(DETAIL.format(fight_id=fid)); dump(RAW/'bossfights'/f'{fid}.json',dj); fetched_details.add(fid); detail_ok+=1
      except Exception:
        pass

    summary.append({
      'period':period,'week_from':pv['week_from'],'week_to':pv['week_to'],'parsings':pv['parsings'],
      'raid':raid,'boss':boss,'frost_dps':f,'frost_rank':rank,'dps_specs_present':len(ranking),
      'overall_spec_median':overall,'frost_vs_overall_pct':pct(f,overall),
      'melee_spec_median':melee,'frost_vs_melee_pct':pct(f,melee),
      'unholy_dps':u,'frost_vs_unholy_pct':pct(f,u),
      'frost_player_rows':len(player_rows),'frost_unique_bossfight_ids':len(set(ids)),
      'specializations_url':url,'frost_players_url':page_urls[0] if page_urls else None,
      'map_ids':','.join(map(str,sorted({r.get('map_id') for r in rows if r.get('map_id') is not None}))),
      'difficulties':','.join(map(str,sorted({r.get('difficulty') for r in rows if r.get('difficulty') is not None}))),
      'encounters':','.join(map(str,sorted({r.get('encounter_id') for r in rows if r.get('encounter_id') is not None}))),
    })

for path,rows in [(OUT/'summary.csv',summary),(OUT/'specializations_long.csv',spec_long),(OUT/'frost_proof.csv',frost_proof),(OUT/'request_manifest.csv',manifests)]:
  if rows:
    with path.open('w',newline='',encoding='utf-8-sig') as f:
      w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

dump(OUT/'run_info.json',{
 'periods':PERIODS,'bosses':[{'order':o,'boss_id':b,'raid':r,'boss':n} for o,b,r,n in BOSSES],
 'ilvl_filter':None,'specializations_raid_param':'order','players_raid_param':'i',
 'specializations_aggregation':'avg','players_proof_aggregation':'max',
 'notes':['Specialization DPS is taken directly from official Sirus specialization endpoint with parsings=40.',
          'Frost proof rows are separate player-ladder records and are not substituted for official specialization DPS.',
          'No ilvl filter is applied.']
})
print(json.dumps(summary,ensure_ascii=False,indent=2))
