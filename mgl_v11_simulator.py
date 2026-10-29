"""MGL v1.1 guided paths, 7 strategy benchmarks, event decision policies and replay audit.

python mgl_v11_simulator.py --balance-runs 24 --attempts 3
"""
from __future__ import annotations
import argparse,collections,csv,json,random,statistics,copy
from pathlib import Path
from mgl_event_engine import load_data,validate_catalog
from mgl_simulator import Planner
from mgl_social_engine import MGL11Engine,validate_social_catalog
ROOT=Path(__file__).resolve().parent

class SocialPlanner(Planner):
    def __init__(self,engine,ending,seed=20261029,mode='focused',choice_policy='empathetic',guided_key_choices=True):
        super().__init__(engine,ending,seed=seed,mode=mode)
        self.policy=choice_policy
        self.guided_key_choices=guided_key_choices
        self.social_month_counter=0
        self.prev_social_month=-1
        self.decisions=collections.Counter()

    def can_afford(self,action):
        if action['kind']=='bond':
            ap,cost,p=self.engine.SOCIAL_COSTS[action['args']['style']]
            nid=action['args']['npc']
            return nid in self.engine.npcs and self.engine.bond_count.get(nid,0)<2 and self.engine._resource_check(ap,cost,p) is None
        if action['kind']=='life':
            eid=action['args']['id'];choice=action['args']['choice']
            ev=next((x for x in self.engine.available_life_events() if x['id']==eid),None)
            if not ev:return False
            opt=next((x for x in ev['options'] if x['id']==choice),None)
            return opt is not None and self.engine._resource_check(opt['ap'],opt['cost'],opt['effects'].get('stress',0)) is None
        return super().can_afford(action)

    def _monthly_social_count(self):
        return sum(x['action'] in ('life','bond') and x['month']==self.engine.state.month for x in self.engine.state.log[-5:])

    def choose_option(self,event):
        e=self.engine;opts=event['options'];eid=event['id']
        forced={'S04':('L_CHOICE_14','respect'),'S07':('L_LEAD_15','share')}
        req=forced.get(self.ending['id'])
        if self.guided_key_choices and req and eid==req[0] and req[1] in [x['id'] for x in opts]:return req[1]
        if self.policy=='random':return self.rng.choice(opts)['id']
        preferences={
          'empathetic':['respect','cooperate','share','mediate','talk','own','research','prepare','remember','participate','listen','ask','efficient','economize','rest','plan'],
          'frugal':['economize','plan','efficient','ask','listen','independent','rest','avoid','skip','postpone','quiet','cooperate','share'],
          'ambitious':['practice','solo','mediate','research','prepare','participate','cooperate','share','efficient','remember','talk'],
          'independent':['independent','avoid','quiet','skip','rest','postpone','efficient','economize','listen','ask','plan'],
          'selfish':['insist','push','hide','refuse','solo','ignore','rest','postpone','skip','efficient','economize']
        }
        order=preferences.get(self.policy,preferences['empathetic'])
        options=sorted(opts,key=lambda x: (order.index(x['id']) if x['id'] in order else len(order),x['cost']))
        return next((x['id'] for x in options if e._resource_check(x['ap'],x['cost'],x['effects'].get('stress',0)) is None),None)

    def plan_bond(self,strong_need=False):
        e=self.engine
        if strong_need:
            needed=e.GATES[self.ending['id']]['strong_bonds']
            ids=['noah','rian'][:needed]
            target= (64,59) # allow some relationship decay without losing eligibility
            deficit=[(max(0,target[0]-e.npcs[n].affinity)+max(0,target[1]-e.npcs[n].trust),n) for n in ids]
            deficit.sort(reverse=True)
            if deficit and deficit[0][0]>0:
                n=deficit[0][1]; b=e.npcs[n]
                return self.action('bond',npc=n,style='listen' if b.trust<59 else 'collaborate')
            return None
        ids=list(e.npcs)
        # socialize with a preferred friend rather than grind one relationship every month
        ids.sort(key=lambda n:(-e.npcs[n].affinity,-e.npcs[n].trust,n))
        nid=ids[0] if self.policy not in ('independent','random') else self.rng.choice(ids)
        return self.action('bond',npc=nid,style='listen' if e.npcs[nid].trust<e.npcs[nid].affinity else 'share')

    def choice(self):
        e=self.engine;s=e.state;m=s.month;age=e.age
        if s.stress>67:return self.action('rest')
        sc=self._monthly_social_count()
        # Cannot miss finite-window turning points for the relationship-sensitive endings.
        mustflag={'S04':('L_CHOICE_14','respectful_dialogue'), 'S07':('L_LEAD_15','shared_community')}.get(self.ending['id'])
        if mustflag and mustflag[1] not in e.life_flags:
            ev=next((x for x in e.available_life_events() if x['id']==mustflag[0]),None)
            if ev and sc<2:
                choice=self.choose_option(ev)
                if choice:return self.action('life',id=ev['id'],choice=choice)
        gate=e.GATES.get(self.ending['id'])
        if gate and age>=18 and sc<2:
            act=self.plan_bond(strong_need=True)
            if act:return act
        # One or two deliberate social choices a month, sharing the SAME AP, slots, cash.
        cadence={'focused':5,'balanced':3,'relationship':2,'frugal':6,'special':4,'mixed':4,'random':3}.get(self.mode,5)
        budget=2 if self.mode=='relationship' else 1
        social_due=m%cadence==0
        if sc<budget and social_due:
            evs=e.available_life_events()
            if self.mode=='relationship' and sc==0 and self.rng.random()<.50:
                return self.plan_bond()
            if evs:
                ev=evs[0] if self.mode!='random' else self.rng.choice(evs)
                ch=self.choose_option(ev)
                if ch:return self.action('life',id=ev['id'],choice=ch)
            if self.mode=='relationship':return self.plan_bond()
        if self.mode=='random':
            if sc<1 and self.rng.random()<.20:return self.plan_bond()
        return super().choice()

    def play(self,actions_per_month=4):
        r=super().play(actions_per_month)
        e=self.engine
        r.update({'social_audit_ok':None,'strong_bonds':len(e.strong_bonds()),'life_actions':e.life_actions,
                  'npc_actions':e.npc_actions,'life_flags':sorted(e.life_flags),
                  'npc_trust_mean':round(statistics.mean(n.trust for n in e.npcs.values()),2),
                  'npc_affinity_mean':round(statistics.mean(n.affinity for n in e.npcs.values()),2),
                  'social_snapshot':e.social_snapshot()})
        return r

def audit_social(engine):
    """Independent replay: replays all actions with the same initial data and seed.
    Original v1.0 actions and social actions share AP/slot checks on replay.
    """
    if hasattr(engine,'story_ids'):
        from mgl_story_engine import MGL13Engine
        rec=MGL13Engine(engine.catalog,{'endings':engine.endings},seed=engine.seed,economy=engine.economy)
    else:
        rec=MGL11Engine(engine.catalog,{'endings':engine.endings},seed=engine.seed,economy=engine.economy,
                        npcs=list(engine.npc_defs.values()),life_events=list(engine.life_defs.values()))
    # v1.0 planner intent is pre-run configuration, not an AP-costing action.
    rec.state.chosen_focus=engine.state.chosen_focus
    errors=[];by_month=collections.defaultdict(list)
    for a in engine.state.log:
        if a['action']!='TRANSFER':by_month[a['month']].append(a)
    for month in range(120):
        rec.start_month(month)
        for a in by_month[month]:
            kind=a['action']
            if kind=='SPECIALIZE':
                if not rec.select_specialization(a['stat']):errors.append(f'{month}:specialization')
                continue
            kwargs={k:a[k] for k in ('facility','level','stat','hobby','id','choice','npc','style') if k in a}
            success,message=rec.act(kind,**kwargs)
            if success!=a['success']:errors.append(f'{month}:{kind}:outcome:{message}')
            if not success and message!='score_failed':errors.append(f'{month}:{kind}:invalid:{message}')
            if kind=='life' and rec.state.log[-1].get('check_passed')!=a.get('check_passed'):errors.append(f'{month}:check mismatch')
        if rec.state.ap>8 or rec.state.slots>4:errors.append(f'{month}:budget')
        if rec.state.cash< -1e-7:errors.append(f'{month}:cash')
        if any(v>rec.cap(k)+1e-7 or v<0 for k,v in rec.state.stats.items()):errors.append(f'{month}:statcap')
    rec.finish()
    if rec.state.earth_transfer_count!=1:errors.append('transfer count')
    for f in ('stats','courses','project_scores','completed_events','ear','confidence','cash','stress','happiness','relation','autonomy','separation'):
        if getattr(rec.state,f)!=getattr(engine.state,f):errors.append(f'state mismatch: {f}')
    if rec.social_snapshot()!=engine.social_snapshot():errors.append('social snapshot mismatch')
    if len(rec.state.log)!=len(engine.state.log):errors.append('log length mismatch')
    if rec.resolve_endings()['selected']!=engine.resolve_endings()['selected']:errors.append('ending mismatch')
    return errors

def run_48(attempts=3,seed=20261029):
    c,d=load_data();catalog=validate_catalog(c,d)
    npcs=json.loads((ROOT/'mgl_npcs.json').read_text(encoding='utf8'))['npcs']
    events=json.loads((ROOT/'mgl_life_events.json').read_text(encoding='utf8'))['events']
    social=validate_social_catalog(npcs,events,d['endings'])
    if not catalog['ok'] or not social['ok']:raise ValueError((catalog['errors'],social['errors']))
    results=[];instances={}
    for ed in d['endings']:
        best=None;quality=-1e20
        for i in range(attempts):
            e=MGL11Engine(c,d,seed=seed+i);planner=SocialPlanner(e,ed,seed=seed+i,mode='special' if ed['type']=='special' else 'focused')
            r=planner.play()
            issues=audit_social(e)
            score=10000*(r['pass'] and r['selected']==ed['id'])-500*len(r['missing'])-100*len(issues)-10*r['invalid_attempt_count']
            if score>quality:best,quality=(r,e,issues),score
            if not issues and r['pass'] and r['selected']==ed['id'] and r['invalid_attempt_count']==0:break
        r,e,issues=best
        r['audit_errors']=issues;r['social_audit_ok']=not issues
        r['selected_target']=r['selected']==ed['id'];results.append(r);instances[ed['id']]=e
    return results,instances,{'base':catalog,'social':social}

def benchmark(runs=24,seed=20261029):
    c,d=load_data();strategies=['focused','balanced','relationship','frugal','special','random','mixed']
    out=[]
    for mode in strategies:
        for i in range(runs):
            rng=random.Random(seed+1000*i+strategies.index(mode)*37)
            ed=d['endings'][40+(i%8)] if mode=='special' else rng.choice(d['endings'][:40])
            eng=MGL11Engine(c,d,seed=seed+i,economy='strained' if mode=='frugal' else 'standard')
            policy={'frugal':'frugal','relationship':'empathetic','random':'random'}.get(mode,'empathetic')
            sim=SocialPlanner(eng,ed,seed=seed+100*i+strategies.index(mode),mode=mode if mode!='special' else 'special',choice_policy=policy)
            r=sim.play();audit=audit_social(eng)
            out.append({'strategy':mode,'run':i,'target':ed['id'],'target_met':r['pass'],'selected_target':r['selected_target'] if 'selected_target' in r else r['selected']==ed['id'],
                        'selected':r['selected'] or 'NONE','mean_stat':round(statistics.mean(r['stats'].values()),2),
                        'ear':r['ear'],'stress':r['stress'],'max_stress':r['max_stress'],'cash':r['cash'],
                        'relation':r['relation'],'npc_mean_trust':r['npc_trust_mean'],'npc_mean_affinity':r['npc_affinity_mean'],
                        'strong_bonds':r['strong_bonds'],'life_choices':r['life_actions'],'npc_actions':r['npc_actions'],
                        'invalid':r['invalid_attempt_count'],'score_failures':r['failed_checks'],
                        'audit_ok':not audit,'audit_issue':'; '.join(audit[:2]),'transfer_count':r['earth_transfer_count']})
    return out

def compare_choices(seed=20261029):
    """Fixed target and seed: choice policy alone changes costs, trust and social outcomes."""
    c,d=load_data();ed=next(x for x in d['endings'] if x['id']=='J06')
    out=[]
    for policy in ('empathetic','frugal','ambitious','independent','selfish'):
        e=MGL11Engine(c,d,seed=seed)
        r=SocialPlanner(e,ed,seed=seed,mode='balanced',choice_policy=policy).play()
        out.append({'policy':policy,'career_met':r['pass'],'selected':r['selected'],
                    'cash':r['cash'],'stress':r['stress'],'ear':r['ear'],'npc_mean_trust':r['npc_trust_mean'],
                    'strong_bonds':r['strong_bonds'],'life_choices':r['life_actions'],'trust_guardian':round(e.state.trust,2),
                    'life_flags':','.join(sorted(e.life_flags)),'audit_ok':not audit_social(e)})
    return out

def choice_gate_counterfactual(seed=20261029):
    """Keep the same target and planner; remove privileged answer-key choices.
    Tests whether respectful dialogue and inclusive leadership actually matter.
    """
    c,d=load_data();rows=[]
    for target in ('S04','S07'):
        ed=next(x for x in d['endings'] if x['id']==target)
        for guided,policy in ((True,'empathetic'),(False,'selfish'),(False,'empathetic')):
            e=MGL11Engine(c,d,seed=seed)
            r=SocialPlanner(e,ed,seed=seed,mode='special',choice_policy=policy,guided_key_choices=guided).play()
            rows.append({'target':target,'guided_decisions':guided,'policy':policy,'eligible':r['pass'],
                         'selected':r['selected'] or 'NONE','social_flags':','.join(sorted(e.life_flags)),
                         'strong_bonds':r['strong_bonds'],'life_actions':r['life_actions'],
                         'missing':json.dumps(r['missing'],ensure_ascii=False),'audit_ok':not audit_social(e)})
    return rows

def write_outputs(results,instances,static,balance,choices,counterfactual,seed):
    rows=[]
    for r in results:
        rows.append({'ID':r['target'],'name':r['name'],'kind':r['type'],'grade':r['grade'],
                     'target_met':r['pass'],'selected_target':r['selected_target'],'selected':r['selected'],
                     'audit_ok':r['social_audit_ok'],'audit_errors':'; '.join(r['audit_errors']),
                     'missing':json.dumps(r['missing'],ensure_ascii=False),'actions':r['actions'],
                     'life_choices':r['life_actions'],'npc_actions':r['npc_actions'],'strong_bonds':r['strong_bonds'],
                     'mean_npc_trust':r['npc_trust_mean'],'ear':r['ear'],'stress':r['stress'],'cash_G':r['cash'],
                     'invalid':r['invalid_attempt_count'],'earth_transfer':r['earth_transfer_count']})
    def writecsv(file,items):
        with (ROOT/file).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)
    writecsv('mgl_v11_validation.csv',rows)
    writecsv('mgl_v11_strategy_trials.csv',balance)
    writecsv('mgl_v11_choice_comparison.csv',choices)
    writecsv('mgl_v11_counterfactual.csv',counterfactual)
    with (ROOT/'mgl_v11_replay_paths.json').open('w',encoding='utf8') as f:
        json.dump({'seed':seed,'paths':{k:e.state.log for k,e in instances.items()}},f,ensure_ascii=False,separators=(',',':'))
    with (ROOT/'mgl_v11_validation.json').open('w',encoding='utf8') as f:
        json.dump({'seed':seed,'catalog_static':{k:static['base'][k] for k in ('ok','errors','nodes','edges')},
                   'social_static':static['social'],'results':rows},f,ensure_ascii=False,indent=2)
    return rows

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempts',type=int,default=3)
    parser.add_argument('--balance-runs',type=int,default=24);parser.add_argument('--seed',type=int,default=20261029)
    args=parser.parse_args()
    results,instances,static=run_48(args.attempts,args.seed)
    balance=benchmark(args.balance_runs,args.seed)
    choices=compare_choices(args.seed)
    counterfactual=choice_gate_counterfactual(args.seed)
    rows=write_outputs(results,instances,static,balance,choices,counterfactual,args.seed)
    print('ENDINGS',sum(r['target_met'] for r in rows),'/',len(rows),'SELECTED',sum(r['selected_target'] for r in rows),'AUDIT',sum(r['audit_ok'] for r in rows))
    for r in rows:
        if not r['target_met'] or not r['selected_target'] or not r['audit_ok'] or r['invalid']:print('FAIL',r['ID'],r['missing'],r['audit_errors'],r['invalid'],r['selected'])
    for mode in ('focused','balanced','relationship','frugal','special','random','mixed'):
        xs=[b for b in balance if b['strategy']==mode]
        print('BENCH',mode,'target',sum(x['selected_target'] for x in xs),'/',len(xs),'audits',sum(x['audit_ok'] for x in xs),'median-social',statistics.median(x['life_choices']+x['npc_actions'] for x in xs),'avg-cash',round(statistics.mean(x['cash'] for x in xs)))
    print('CHOICES',[(x['policy'],x['cash'],x['npc_mean_trust']) for x in choices])
    print('COUNTERFACTUAL',[(x['target'],x['guided_decisions'],x['policy'],x['eligible'],x['selected']) for x in counterfactual])
if __name__=='__main__':main()
