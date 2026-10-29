"""Reproducible ending-selection audit using saved witness seeds and modes."""
import csv,json,collections
from pathlib import Path
from mgl_v18_witness_search import run
from mgl_play_v13 import PlaySession13
from mgl_v11_simulator import SocialPlanner
R=Path(__file__).resolve().parent
rows=[]
for item in csv.DictReader((R/'mgl_v18_witness_trials.csv').open(encoding='utf-8-sig')):
 target=item['ending'];seed=int(item['seed']);mode=item['mode']
 s=PlaySession13(seed=seed,focus=target);e=s.engine;ending=s.focus_ending
 planner=SocialPlanner(e,ending,seed=seed,mode='special' if ending['type']=='special' else 'focused')
 import json as j
 for month in range(120):
  if e.age>=16:
   req=ending['mandatory']['stats'];keys=sorted((k for k,v in req.items() if v>75),key=lambda k:-req[k])
   for k in keys[:2]:
    if k not in e.state.specializations and len(e.state.specializations)<2:s.specialize(k)
  for slot in range(4):
   opts=[x for x in s.action_options() if x['usable']]
   if not opts:break
   available={(x['kind'],j.dumps(x['args'],sort_keys=True)):x for x in opts}
   def valid(a):return available.get((a['kind'],j.dumps(a['args'],sort_keys=True))) if a else None
   preferred=valid(planner.choice()) if mode=='social_planner' else valid(planner.focus_choice())
   if mode=='session_recommend':
    a=s.recommend();preferred=valid(a) if a and a['kind']!='specialize' else None
   if preferred is None:
    m=ending['mandatory'];gaps={k:v-e.state.stats[k] for k,v in m['stats'].items()}
    def rank(x):
     k=x['kind'];z=x['args'];v=0
     if k=='rest':v=100 if e.state.stress>65 else (35 if e.state.stress>45 else -20)
     elif k=='work':v=90 if e.state.cash<180 else (45 if e.state.cash<450 else -10)
     elif k=='ear':v=65 if e.state.ear<m.get('ear_min',0) else 0
     elif k=='study':v=40+max(0,gaps.get(z['stat'],0))*2
     elif k=='course':v=30 if any(q['facility']==z['facility'] for q in m.get('education',[])) else 0
     elif k in ('project','event'):v=40 if z['id'] in (m.get('projects',[])+m.get('events',[])) else 0
     return (v,-x['ap'])
    preferred=max(opts,key=rank)
   if preferred:s.act(preferred['kind'],preferred['args'])
  s.next_month()
 resolution=e.resolve_endings();chosen=resolution['selected'];rows.append({'ending':target,'seed':seed,'mode':mode,'eligible':int(not e.ending_missing(ending)),'selected':chosen['id'] if chosen else '', 'selected_matches_target':int(bool(chosen) and chosen['id']==target),'eligible_count':len(resolution['eligible']),'earth_transfer':e.state.earth_transfer_count})
 print(target,mode,rows[-1]['selected'],flush=True)
with (R/'mgl_v18_selection_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
summary={'runs':len(rows),'eligible':sum(r['eligible'] for r in rows),'selected_matches':sum(r['selected_matches_target'] for r in rows),'unique_selected_targets':len({r['ending'] for r in rows if r['selected_matches_target']}),'transfer_violations':sum(r['earth_transfer']!=1 for r in rows)}
(R/'mgl_v18_selection_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(summary)
