"""Static dependency diagnostics for unresolved endings; does not alter requirements."""
import csv,json,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parent
endings=json.loads((ROOT/'mgl_ending_conditions.json').read_text())['endings']
projects={p['id']:p for p in json.loads((ROOT/'mgl_projects.json').read_text()).get('projects',[])}
events={e['id']:e for e in json.loads((ROOT/'mgl_career_events.json').read_text()).get('events',[])} if (ROOT/'mgl_career_events.json').exists() else {}
missing={r['ending_id'] for r in csv.DictReader((ROOT/'mgl_v18_unresolved.csv').open(encoding='utf-8-sig'))} if False else set(json.loads((ROOT/'mgl_v18_diagnostics.json').read_text())['unresolved_ids'])
rows=[]
for e in endings:
 if e['id'] not in missing:continue
 m=e['mandatory'];rows.append({'ending':e['id'],'name':e['name'],'required_stats':json.dumps(m.get('stats',{}),ensure_ascii=False),'required_education':json.dumps(m.get('education',[]),ensure_ascii=False),'required_projects':';'.join(m.get('projects',[])),'required_events':';'.join(m.get('events',[])),'ear_min':m.get('ear_min',0),'additional_conditions':json.dumps(e.get('social_mandatory',{}),ensure_ascii=False)})
with (ROOT/'mgl_v18_dependency.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
print('unresolved dependency profiles:',len(rows))
