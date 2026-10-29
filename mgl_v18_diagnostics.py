import csv,collections,json
from pathlib import Path
p=Path(__file__).resolve().parent
rows=list(csv.DictReader((p/'mgl_v18_trials.csv').open(encoding='utf-8-sig')))
fails=list(csv.DictReader((p/'mgl_v18_failures.csv').open(encoding='utf-8-sig')))
coverage={r['focus'] for r in rows if r['eligible']=='1'}
missing=sorted({r['focus'] for r in rows}-coverage)
by=collections.defaultdict(collections.Counter)
for f in fails:
 if f['focus'] in missing:by[f['focus']][f['type']]+=1
out=[{'ending':e,'success_paths':0,'top_failure_types':';'.join(f'{k}:{v}' for k,v in by[e].most_common(4))} for e in missing]
with (p/'mgl_v18_unresolved.csv').open('w',encoding='utf-8-sig',newline='') as fh:
 w=csv.DictWriter(fh,fieldnames=out[0]);w.writeheader();w.writerows(out)
summary={'unresolved_count':len(missing),'unresolved_ids':missing,'failures_unresolved':dict(sum((by[e] for e in missing),collections.Counter()))}
(p/'mgl_v18_diagnostics.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
