"""Audit full prerequisite closure and static feasibility; no game rules are modified."""
import json,csv,collections
from pathlib import Path
R=Path(__file__).resolve().parent
catalog=json.loads((R/'mgl_projects.json').read_text()); nodes={x['id']:x for kind in ('projects','events') for x in catalog[kind]}
endings=json.loads((R/'mgl_ending_conditions.json').read_text())['endings']
unresolved=set(json.loads((R/'mgl_v18_diagnostics.json').read_text())['unresolved_ids'])
rows=[];issues=[]
for ending in endings:
 if ending['id'] not in unresolved:continue
 roots=ending['mandatory'].get('projects',[])+ending['mandatory'].get('events',[])
 seen=set();active=set();order=[]
 def visit(n):
  if n in active:issues.append({'ending':ending['id'],'node':n,'issue':'cycle'});return
  if n in seen:return
  if n not in nodes:issues.append({'ending':ending['id'],'node':n,'issue':'missing_node'});return
  active.add(n)
  for dep in nodes[n].get('prerequisites',{}).get('projects',[])+nodes[n].get('prerequisites',{}).get('events',[]):visit(dep)
  active.remove(n);seen.add(n);order.append(n)
 for root in roots:visit(root)
 edu=collections.defaultdict(int);stats=collections.defaultdict(float);age=10
 for n in order:
  x=nodes[n];age=max(age,x.get('min_age',10))
  for ed in x.get('education',[]):edu[(ed['facility'],ed['stage'])]=max(edu[(ed['facility'],ed['stage'])],ed['count'])
  for k,v in x.get('required_stats',{}).items():stats[k]=max(stats[k],v)
 for ed in ending['mandatory'].get('education',[]):edu[(ed['facility'],ed['stage'])]=max(edu[(ed['facility'],ed['stage'])],ed['count'])
 for k,v in ending['mandatory'].get('stats',{}).items():stats[k]=max(stats[k],v)
 rows.append({'ending':ending['id'],'name':ending['name'],'node_count':len(order),'earliest_node_age':age,'ordered_nodes':';'.join(order),'education_max':json.dumps({f'{k[0]}:{k[1]}':v for k,v in sorted(edu.items())},ensure_ascii=False),'stat_max':json.dumps(dict(stats),ensure_ascii=False),'node_ap_total':sum(nodes[n]['ap'] for n in order),'node_cost_total':sum(nodes[n]['cost'] for n in order)})
for name,data in [('mgl_v18_graph_audit.csv',rows),('mgl_v18_graph_issues.csv',issues)]:
 with (R/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(data[0]) if data else ['ending','node','issue']);w.writeheader();w.writerows(data)
print(json.dumps({'endings':len(rows),'issues':len(issues),'nodes_total':sum(r['node_count'] for r in rows)},ensure_ascii=False))
