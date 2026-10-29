"""Reproducible 120-month targeted witness search, without modifying ending rules."""
import csv,json,random,collections,argparse
from pathlib import Path
from mgl_play_v13 import PlaySession13
from mgl_simulator import Planner
from mgl_v11_simulator import SocialPlanner
R=Path(__file__).resolve().parent

def run(target,seed,mode):
 s=PlaySession13(seed=seed,focus=target);e=s.engine;ending=s.focus_ending
 planner=SocialPlanner(e,ending,seed=seed,mode='special' if ending['type']=='special' else 'focused')
 rng=random.Random(seed);counts=collections.Counter();failed=0
 for month in range(120):
  if e.age>=16:
   req=ending['mandatory']['stats']; keys=sorted((k for k,v in req.items() if v>75),key=lambda k:-req[k]);
   for k in keys[:2]:
    if k not in e.state.specializations and len(e.state.specializations)<2:s.specialize(k)
  for slot in range(4):
   opts=[x for x in s.action_options() if x['usable']]
   if not opts:break
   available={(x['kind'],json.dumps(x['args'],sort_keys=True)):x for x in opts}
   def valid(a):return available.get((a['kind'],json.dumps(a['args'],sort_keys=True))) if a else None
   preferred=valid(planner.choice()) if mode=='social_planner' else valid(planner.focus_choice())
   if mode=='session_recommend':
    a=s.recommend();preferred=valid(a) if a and a['kind']!='specialize' else None
   if preferred is None:
    # Rescue invalid plan actions with an affordable, useful activity.
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
   if preferred:
    try:
     result=s.act(preferred['kind'],preferred['args']);counts[preferred['kind']]+=1
     if not result['ok']:failed+=1
    except ValueError:failed+=1
  s.next_month()
 missing=e.ending_missing(ending)
 return {'ending':target,'seed':seed,'mode':mode,'eligible':int(not missing),'missing_count':len(missing),'missing':json.dumps(missing,ensure_ascii=False),'actions':sum(counts.values()),'score_failures':failed,'rests':counts['rest'],'courses':counts['course'],'projects':counts['project'],'events':counts['event'],'earth_transfer':e.state.earth_transfer_count,'months':120}

def main():
 p=argparse.ArgumentParser();p.add_argument('--attempts',type=int,default=2);p.add_argument('--targets',default='');args=p.parse_args()
 ids=json.loads((R/'mgl_v18_diagnostics.json').read_text())['unresolved_ids'];ids=args.targets.split(',') if args.targets else ids
 rows=[]
 for target in ids:
  for i in range(args.attempts):
   mode=['social_planner','session_recommend','focus_planner'][i%3]
   rows.append(run(target,20261029+int(target[1:])*1000+i,mode))
  print(target, sum(r['eligible'] for r in rows if r['ending']==target),flush=True)
 with (R/'mgl_v18_witness_trials.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 summary={'runs':len(rows),'successful_runs':sum(r['eligible'] for r in rows),'successful_endings':sorted({r['ending'] for r in rows if r['eligible']}),'remaining_endings':sorted(set(ids)-{r['ending'] for r in rows if r['eligible']}),'rejected_or_score_failed':sum(r['score_failures'] for r in rows),'transfer_violations':sum(r['earth_transfer']!=1 for r in rows)}
 (R/'mgl_v18_witness_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
