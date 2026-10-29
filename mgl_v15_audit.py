from pathlib import Path
import csv, json, re, subprocess
from mgl_play_v13 import PlaySession13
ROOT=Path(__file__).resolve().parent

def run():
 rows=[]
 for focus in ('J01','J10','J20','J30','J40','S01','S04','S08'):
  s=PlaySession13(seed=20261029,focus=focus)
  baseline=s.view()
  assert baseline['month_index']==0
  for i in range(24):
   v=s.view()
   assert v['month_index']==i and v['ap_used']<=8 and v['slots_used']<=4
   assert v['invalid_attempt_count']==0
   s.next_month()
  v=s.view()
  assert v['month_index']==24 and v['age']==12 and len(v['year_reports'])==2
  assert v['transfer_count']==0
  restored=PlaySession13.from_payload(s.save_payload())
  assert restored.view()['month_index']==24
  assert restored.view()['stats']==v['stats']
  rows.append({'focus':focus,'months':24,'year_reports':len(v['year_reports']),'invalid_attempts':v['invalid_attempt_count'],'restore_match':True,'ap_slot_violations':0})
 with (ROOT/'mgl_v15_24month_audit.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 js=(ROOT/'web/app.js').read_text();html=(ROOT/'web/index.html').read_text()
 for ident in ['tutorial-dismiss','tutorial-restore','tutorial-progress','tutorial-toggle','tutorial-message']:
  assert f'id="{ident}"' in html
 assert 'localStorage.setItem(TUTORIAL_KEY' in js
 assert 'tutorialHidden||s.completed||s.month_index>=24' in js
 subprocess.run(['node','--check',str(ROOT/'web/app.js')],check=True)
 print(json.dumps({'sample_24month_paths':len(rows),'months_total':24*len(rows),'year_reports':16,'save_restore':len(rows),'tutorial_ui_static_checks':5,'js_syntax':'pass'},ensure_ascii=False))
if __name__=='__main__':run()
