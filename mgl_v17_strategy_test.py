import csv,random,collections,json
from pathlib import Path
from mgl_play_v13 import PlaySession13
ROOT=Path(__file__).resolve().parent
POLICIES=['guided','free_random','balanced','social','frugal','mixed','career']
FOCI=['J01','J20','S04']
rows=[]
for policy in POLICIES:
 for trial,focus in enumerate(FOCI):
  rng=random.Random(20261029+trial*100+POLICIES.index(policy)*1000)
  s=PlaySession13(seed=20261029+trial,focus=focus)
  counts=collections.Counter()
  for month in range(24):
   for slot in range(4):
    options=[x for x in s.action_options() if x['usable']]
    if not options:break
    rec=s.recommend()
    recommended=next((x for x in options if rec and x['kind']==rec['kind'] and x['args']==rec['args']),None)
    if policy=='guided':pick=recommended or rng.choice(options)
    elif policy=='free_random':pick=rng.choice(options)
    else:
     weights=[]
     for x in options:
      k=x['kind']; group=x.get('group','')
      w=1
      if policy=='balanced':w=5 if k=='course' else 2
      if policy=='social':w=12 if k in ('bond','life') else 1
      if policy=='frugal':w=10 if k in ('work','rest','ear') else 1
      if policy=='career':w=10 if k in ('course','project','event') else 1
      if policy=='mixed':w=5 if k in ('course','bond','life','ear') else 1
      weights.append(w)
     pick=rng.choices(options,weights=weights,k=1)[0]
    try:s.act(pick['kind'],pick['args'])
    except ValueError:counts['rejected']+=1;break
    counts['actions']+=1;counts[pick['kind']]+=1
   v=s.view()
   assert v['ap_used']<=8 and v['slots_used']<=4
   s.next_month()
  v=s.view()
  restored=PlaySession13.from_payload(s.save_payload())
  assert restored.view()['stats']==v['stats']
  rows.append({'policy':policy,'focus':focus,'actions':counts['actions'],'rejected':counts['rejected'],
               'courses':counts['course'],'bond':counts['bond'],'life':counts['life'],
               'cash':v['cash'],'stress':v['stress'],'ear':v['ear'],
               'mean_stat':round(sum(t['value'] for t in v['stats'].values())/8,2),
               'invalid_attempts':v['invalid_attempt_count'],'month':v['month_index']})
with (ROOT/'mgl_v17_strategy_trials.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
print(json.dumps({'trials':len(rows),'actions':sum(r['actions'] for r in rows),'rejected':sum(r['rejected'] for r in rows),'invalid':sum(r['invalid_attempts'] for r in rows)},ensure_ascii=False))
