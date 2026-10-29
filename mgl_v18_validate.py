import csv,random,collections,json,sys
from pathlib import Path
from mgl_play_v13 import PlaySession13
from mgl_play_session import load_data,ROOT
POLICIES=["guided","free_random","balanced","social","frugal","mixed","career"]
endings=load_data(ROOT)[1]['endings']
rows=[];fails=[];coverage=collections.Counter();actions=collections.Counter()
for focus_index,ending in enumerate(endings):
 for policy_index,policy in enumerate(POLICIES):
  seed=20261029+focus_index*100+policy_index
  rng=random.Random(seed)
  s=PlaySession13(seed=seed,focus=ending['id']);counts=collections.Counter()
  for month in range(120):
   for slot in range(4):
    opts=[x for x in s.action_options() if x['usable']]
    if not opts:break
    rec=s.recommend();recommended=next((x for x in opts if rec and x['kind']==rec['kind'] and x['args']==rec['args']),None)
    if policy=='guided':pick=recommended or rng.choice(opts)
    elif policy=='free_random':pick=rng.choice(opts)
    else:
     weights=[]
     for x in opts:
      k=x['kind'];w=1
      if policy=='balanced':w=5 if k=='course' else 2
      if policy=='social':w=12 if k in ('bond','life') else 1
      if policy=='frugal':w=10 if k in ('work','rest','ear') else 1
      if policy=='career':w=10 if k in ('course','project','event') else 1
      if policy=='mixed':w=5 if k in ('course','bond','life','ear') else 1
      weights.append(w)
     pick=rng.choices(opts,weights=weights,k=1)[0]
    try:s.act(pick['kind'],pick['args'])
    except ValueError:counts['rejected']+=1;break
    counts[pick['kind']]+=1;counts['actions']+=1
   assert s.engine.state.ap<=8 and s.engine.state.slots<=4
   s.next_month()
  assert s.ended and s.engine.state.earth_transfer_count==1
  missing=s.engine.ending_missing(ending);result=s.engine.resolve_endings()
  categories=collections.Counter({'ability':0,'education':0,'relation':0,'project':0,'event':0,'earth_readiness':0,'other':0})
  mapping={'stat':'ability','education':'education','relation':'relation','project':'project','event':'event','ear':'earth_readiness','autonomy':'earth_readiness','bond':'relation'}
  for item in missing:categories[mapping.get(item[0],'other')]+=1
  eligible=not missing
  if eligible:coverage[ending['id']]+=1
  actions.update(counts)
  row={'focus':ending['id'],'policy':policy,'seed':seed,'months':120,'actions':counts['actions'],'rejected':counts['rejected'],'eligible':int(eligible),'selected':result['selected']['id'] if result['selected'] else '', 'eligible_total':len(result['eligible']),'mean_stat':round(sum(s.engine.state.stats.values())/8,2),'ear':round(s.engine.state.ear,2),'relation':round(s.engine.state.relation,2),'stress':round(s.engine.state.stress,2),'courses':counts['course'],'bonds':counts['bond'],'rests':counts['rest'],**categories}
  rows.append(row)
  for item in missing:fails.append({'focus':ending['id'],'policy':policy,'type':item[0],'detail':json.dumps(item,ensure_ascii=False)})
  print(f'{len(rows)}/{len(endings)*len(POLICIES)}',flush=True) if len(rows)%48==0 else None
for filename,data in [('mgl_v18_trials.csv',rows),('mgl_v18_failures.csv',fails)]:
 with (ROOT/filename).open('w',newline='',encoding='utf-8-sig') as f:
  if data:w=csv.DictWriter(f,fieldnames=data[0]);w.writeheader();w.writerows(data)
summary={'runs':len(rows),'months':sum(x['months'] for x in rows),'actions':sum(x['actions'] for x in rows),'rejected':sum(x['rejected'] for x in rows),'eligible_runs':sum(x['eligible'] for x in rows),'reachable_endings':len(coverage),'total_endings':len(endings),'by_policy':{p:{'eligible':sum(x['eligible'] for x in rows if x['policy']==p),'mean_stat':round(sum(x['mean_stat'] for x in rows if x['policy']==p)/len(endings),2),'rests':sum(x['rests'] for x in rows if x['policy']==p)} for p in POLICIES},'failures_by_type':dict(collections.Counter(x['type'] for x in fails)),'reachable_ids':sorted(coverage)}
(ROOT/'mgl_v18_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False))
