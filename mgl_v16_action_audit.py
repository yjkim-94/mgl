
import csv,json,random
from pathlib import Path
from mgl_play_v13 import PlaySession13
ROOT=Path(__file__).resolve().parent
rows=[]
for focus in ('J01','J10','J20','J30','J40','S01','S04','S08'):
 s=PlaySession13(seed=20261029,focus=focus)
 counts={'attempts':0,'success':0,'fail':0,'months_active':0}
 for month in range(24):
  for attempt in range(4):
   v=s.view()
   # Inspect candidate actions, prioritizing guided recommendations where possible.
   choices=[v.get('recommendation')] if v.get('recommendation') else []
   if not choices:break
   candidate=choices[0]
   if not isinstance(candidate,dict):break
   kind=candidate.get('kind')
   args=candidate.get('args',{})
   if not kind:break
   try:
    s.act(kind,args);counts['success']+=1
   except (ValueError,TypeError,KeyError) as e:
    counts['fail']+=1
    break
   counts['attempts']+=1
  if counts['attempts']:counts['months_active']+=1
  v=s.view()
  assert v['ap_used']<=8 and v['slots_used']<=4
  s.next_month()
 v=s.view()
 restored=PlaySession13.from_payload(s.save_payload())
 assert restored.view()['stats']==v['stats']
 rows.append({'focus':focus,**counts,'month':v['month_index'],'year_reports':len(v['year_reports']),'invalid_attempts':v['invalid_attempt_count']})
with (ROOT/'mgl_v16_action_audit.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(rows,ensure_ascii=False))
