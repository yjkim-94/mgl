"""Paired 120-month policy audit, original v1.7 versus v1.8 recommendation."""
import csv, json, random, collections, zipfile, tempfile, sys
from pathlib import Path
from mgl_play_v13 import PlaySession13
from mgl_play_session import load_data, ROOT

archive=Path(__file__).resolve().parents[2]/'MGL_v1.7_strategy_balance(2).zip'
endings=load_data(ROOT)[1]['endings']
rows=[]
with tempfile.TemporaryDirectory() as tmp:
 with zipfile.ZipFile(archive) as z:z.extractall(tmp)
 original=Path(tmp)/'mgl_v17'/'mgl_play_session.py'
 old=original.read_text()
 new=(ROOT/'mgl_play_session.py').read_text()
 start='        # v1.8: goal-aware fallback instead of unconditional rest/EAR/work.'
 end='        if candidate is None:return None'
 a=new.index(start);b=new.index(end,a)
 a0=old.index('        if candidate is None:\n            for kind in (\'rest\',\'ear\',\'work\'):')
 b0=old.index(end,a0)
 old_fallback=old[a0:b0]
 # swap the method on disk temporarily, restoring it even on errors.
 file=ROOT/'mgl_play_session.py'
 try:
  for version in ('v17','v18'):
   if version=='v17':file.write_text(new[:a]+old_fallback+new[b:])
   else:file.write_text(new)
   # source module reload is required; isolate via a fresh subprocess below instead.
   import subprocess
   proc=subprocess.run([sys.executable,'-c', '''import csv,random,collections,sys,json
from mgl_play_v13 import PlaySession13
from mgl_play_session import load_data,ROOT
endings=load_data(ROOT)[1]['endings']; rows=[]
for idx,ending in enumerate(endings):
 seed=20261029+idx*100
 s=PlaySession13(seed=seed,focus=ending['id']);counts=collections.Counter(); rng=random.Random(seed)
 for month in range(120):
  for slot in range(4):
   opts=[x for x in s.action_options() if x['usable']]
   if not opts:break
   rec=s.recommend();pick=next((x for x in opts if rec and x['kind']==rec['kind'] and x['args']==rec['args']),None) or rng.choice(opts)
   s.act(pick['kind'],pick['args']);counts[pick['kind']]+=1
  s.next_month()
 result=s.engine.resolve_endings();rows.append(dict(focus=ending['id'],seed=seed,eligible=int(not s.engine.ending_missing(ending)),selected_match=int(bool(result['selected']) and result['selected']['id']==ending['id']),actions=sum(counts.values()),rests=counts['rest'],courses=counts['course'],bonds=counts['bond'],projects=counts['project'],events=counts['event'],mean_stat=round(sum(s.engine.state.stats.values())/8,2),relation=s.engine.state.relation,earth_transfer=s.engine.state.earth_transfer_count))
print(json.dumps(rows))'''],cwd=ROOT,capture_output=True,text=True,check=True)
   for row in json.loads(proc.stdout):row['version']=version;rows.append(row)
 finally:file.write_text(new)
fields=list(rows[0]);out=ROOT/'mgl_v18_paired_comparison.csv'
with out.open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
summary={v:{'runs':48,'eligible':sum(r['eligible'] for r in rows if r['version']==v),'selected_match':sum(r['selected_match'] for r in rows if r['version']==v),'rests':sum(r['rests'] for r in rows if r['version']==v),'courses':sum(r['courses'] for r in rows if r['version']==v),'bonds':sum(r['bonds'] for r in rows if r['version']==v),'mean_stat':round(sum(r['mean_stat'] for r in rows if r['version']==v)/48,3),'earth_violations':sum(r['earth_transfer']!=1 for r in rows if r['version']==v)} for v in ('v17','v18')}
(ROOT/'mgl_v18_paired_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
print(summary)
