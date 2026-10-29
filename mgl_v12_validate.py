"""MGL v1.2: replay all 48 documented v1.1 paths through the playable session.

This tests v1.1 compatibility, AP/cash/age limits, year reports, and mandatory transfer.
It does not claim unguided players can reliably discover those paths.
"""
from __future__ import annotations
import csv,json,random,statistics
from pathlib import Path
from collections import Counter
from mgl_play_session import PlaySession,ROOT
from mgl_v11_simulator import audit_social

WITNESSES=ROOT/'tests'/'v11_witness_paths.json'


def audit_session(session):
    e=session.engine;s=e.state;errors=[]
    if s.earth_transfer_count!=1 or not s.left_astellia:errors.append('transfer_missing')
    if len(session.reports)!=10:errors.append('year_reports_not_ten')
    if s.invalid_attempts:errors.append('invalid_attempts')
    if s.cash<-1e-8:errors.append('negative_cash')
    if any(x['month'] not in range(120) for x in s.log if x['action']!='TRANSFER'):errors.append('invalid_month')
    if any(x['ap']<0 or x['ap']>4 for x in s.log if x['action'] not in ('TRANSFER','SPECIALIZE')):errors.append('invalid_ap')
    errors+=audit_social(e)
    return errors


def replay_target(target,log,seed=20261029, save_probe=False):
    session=PlaySession(seed=seed,focus=target)
    by_month={m:[] for m in range(120)}
    for action in log:
        if action['action']=='TRANSFER':continue
        by_month[action['month']].append(action)
    for m in range(120):
        assert session.engine.state.month==m,(target,m,session.engine.state.month)
        for act in by_month[m]:
            if act['action']=='SPECIALIZE':session.specialize(act['stat']);continue
            keys=('facility','level','stat','hobby','id','choice','npc','style')
            arg={k:act[k] for k in keys if k in act}
            result=session.act(act['action'],arg)
            if result['ok']!=act['success']:
                raise AssertionError((target,m,act,result))
            if 'check_passed' in act and result['record'].get('check_passed')!=act['check_passed']:
                raise AssertionError((target,m,'check outcome mismatched'))
        if save_probe and m in (11,47,97):
            # Serialized and resumed game must make exactly the same decisions.
            payload=session.save_payload()
            recovered=PlaySession.from_payload(json.loads(json.dumps(payload,ensure_ascii=False)))
            assert recovered.save_payload()==payload, (target,m,'save mismatch')
            session=recovered
        status=session.next_month()
        if m==119:assert status['completed']
        else:assert not status['completed']
    resolved=session.engine.resolve_endings()
    selected=(resolved['selected'] or {}).get('id','')
    required_met=not session.engine.ending_missing(session.focus_ending)
    errors=audit_session(session)
    if not required_met:errors.append('goal_missing')
    if selected!=target:errors.append(f'selected_{selected}')
    return {'id':target,'name':session.focus_ending['name'],'goal_met':required_met,
            'selected':selected,'audit_ok':not errors,'errors':';'.join(errors),
            'actions':len(session.engine.state.log)-session.engine.state.earth_transfer_count,
            'year_reports':len(session.reports),'npc_bonds':len(session.engine.strong_bonds()),
            'cash':round(session.engine.state.cash,2),'ear':round(session.engine.state.ear,2),
            'transfer_count':session.engine.state.earth_transfer_count,
            'project_count':len(session.engine.state.project_scores)}


def run_witnesses():
    obj=json.loads(WITNESSES.read_text(encoding='utf8'))
    rows=[replay_target(target,path,seed=obj['seed'],save_probe=True) for target,path in obj['paths'].items()]
    return rows


def run_recommendations():
    """48 independently guided playthroughs, not path replays."""
    rows=[]
    for ed in PlaySession().engine.endings:
        session=PlaySession(seed=20261029,focus=ed['id'])
        errors=[]
        for m in range(120):
            for _ in range(4):
                a=session.recommend()
                if a is None:break
                try:
                    if a['kind']=='specialize':session.specialize(a['args']['stat'])
                    else:session.act(a['kind'],a['args'])
                except ValueError as exc:
                    errors.append(f'{m}:{exc}');break
            session.next_month()
        selected=(session.engine.resolve_endings()['selected'] or {}).get('id','')
        errors+=audit_session(session)
        rows.append({'id':ed['id'],'name':ed['name'],'goal_met':not session.engine.ending_missing(ed),
                     'selected':selected,'audit_ok':not errors,'errors':';'.join(errors),
                     'year_reports':len(session.reports),'transfer_count':session.engine.state.earth_transfer_count,
                     'cash':round(session.engine.state.cash,2),'ear':round(session.engine.state.ear,2)})
    return rows


def run_casual(seed,mode):
    rng=random.Random(seed)
    endings=PlaySession(seed=seed).engine.endings
    if mode=='focused':target=endings[(seed*3)%40]['id']
    elif mode=='special':target=endings[40+(seed%8)]['id']
    else:target=endings[seed%48]['id']
    s=PlaySession(seed=seed,focus=target)
    for month in range(120):
        if s.engine.age==16 and mode in ('focused','special'):
            keys=sorted(s.focus_ending['mandatory'].get('stats',{}),key=s.focus_ending['mandatory'].get('stats',{}).get,reverse=True)
            for key in keys[:2]:
                try:s.specialize(key)
                except ValueError:pass
        for _ in range(4):
            opts=[x for x in s.action_options() if x['usable']]
            if not opts:break
            if mode=='random':choice=rng.choice(opts)
            elif mode=='social':
                socials=[x for x in opts if x['kind'] in ('life','bond','hobby')]
                choice=rng.choice(socials if socials else opts)
            elif mode=='frugal':
                zero=[x for x in opts if x['pay']==0 and x['kind'] in ('work','ear','study','rest','hobby')]
                choice=rng.choice(zero if zero else opts)
            elif mode=='balanced':
                keys=[x for x in opts if x['kind']=='study']
                keys.sort(key=lambda o:s.engine.state.stats[o['args']['stat']]);
                choice=keys[0] if keys and rng.random()<0.65 else rng.choice(opts)
            elif mode=='focused':
                prefs=[x for x in opts if x['kind'] in ('project','event') and (x['score'] is not None and x['score']>=x['threshold'])]
                if not prefs:prefs=[x for x in opts if x['kind']=='course']
                if not prefs:prefs=[x for x in opts if x['kind']=='study']
                choice=prefs[0] if prefs else rng.choice(opts)
            elif mode=='special':
                prefs=[x for x in opts if x['kind'] in ('hobby','life','bond')]
                choice=rng.choice(prefs if prefs else opts)
            else: # mixed
                preferred=[x for x in opts if x['kind'] in ('course','study','hobby','life','bond')]
                choice=rng.choice(preferred if preferred else opts)
            try:s.act(choice['kind'],choice['args'])
            except ValueError:break
        s.next_month()
    final=s.engine.resolve_endings();selected=(final['selected'] or {}).get('id','')
    return {'strategy':mode,'seed':seed,'focus':target,'goal_met':not s.engine.ending_missing(s.focus_ending),
            'selected':selected,'any_registered_ending':bool(selected),
            'mean_stat':round(statistics.mean(s.engine.state.stats.values()),2),
            'ear':round(s.engine.state.ear,2),'stress':round(s.engine.state.stress,2),
            'cash':round(s.engine.state.cash,2),'happiness':round(s.engine.state.happiness,2),
            'year_reports':len(s.reports),'transfer_count':s.engine.state.earth_transfer_count,
            'invalid_count':len(s.engine.state.invalid_attempts)}


def run_balance(runs=8,seed=20261029):
    modes=('focused','balanced','social','frugal','special','random','mixed')
    return [run_casual(seed+modei*12345+i,mode) for modei,mode in enumerate(modes) for i in range(runs)]


def write_csv(rows,path):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--balance-runs',type=int,default=8);args=p.parse_args()
    rows=run_witnesses();write_csv(rows,ROOT/'mgl_v12_validation.csv')
    guided=run_recommendations();write_csv(guided,ROOT/'mgl_v12_recommended.csv')
    bal=run_balance(args.balance_runs);write_csv(bal,ROOT/'mgl_v12_balance.csv')
    counters={k:(sum(bool(x[k]) for x in rows)) for k in ('goal_met','audit_ok')}
    print('WITNESS',len(rows),'GOAL',counters['goal_met'],'AUDIT',counters['audit_ok'])
    print('RECOMMENDED',len(guided),'GOAL',sum(x['goal_met'] for x in guided),'SELECTED',sum(x['selected']==x['id'] for x in guided),'AUDIT',sum(x['audit_ok'] for x in guided))
    for mode in sorted({x['strategy'] for x in bal}):
        subset=[x for x in bal if x['strategy']==mode]
        print('BALANCE',mode,'GOAL',sum(x['goal_met'] for x in subset),'ANY',sum(x['any_registered_ending'] for x in subset),
              'OUT OF',len(subset),'TRANSFER',sum(x['transfer_count']==1 for x in subset))
    if any(not x['audit_ok'] or x['selected']!=x['id'] for x in rows+guided):
        for x in rows+guided:
            if not x['audit_ok'] or x['selected']!=x['id']:print('ERROR',x['id'],x['errors'])
        raise SystemExit(1)

if __name__=='__main__':main()
