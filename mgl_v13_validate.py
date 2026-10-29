"""v1.3 reproducible witness, story, partial guidance & compatibility validations."""
from __future__ import annotations
from pathlib import Path
import csv, json, random, statistics, sys
from mgl_play_v13 import PlaySession13
from mgl_story_engine import validate_story_data
from mgl_v12_validate import audit_session
ROOT=Path(__file__).resolve().parent


def story_route(npc,route,save_probe=False,stage_choice="commit",final_choice="fulfill"):
    """A concrete 120-month legal route, with resource spending and branch locks."""
    session=PlaySession13(seed=20261029,focus='J01')
    first=f'ST_{npc.upper()}_1_START'
    second=f'ST_{npc.upper()}_2_{route.upper()}'
    third=f'ST_{npc.upper()}_3_{route.upper()}'
    outcomes=[]
    for m in range(120):
        age=session.engine.age
        if age==12 and m%12==0:
            result=session.act('life',{'id':first,'choice':'together' if route=='a' else 'independent'})
            outcomes.append(result['story_result'])
        if age in (15,18) and (age==15 and len(outcomes)==1 or age==18 and len(outcomes)==2):
            chapter=second if age==15 else third
            if chapter in [x['id'] for x in session.engine.available_life_events()]:
                result=session.act('life',{'id':chapter,'choice':stage_choice if age==15 else final_choice})
                outcomes.append(result['story_result'])
            else:
                # In-year relationship rebuilding; never bypass actual life eligibility.
                for style in ('listen','share'):
                    possible=[x for x in session.action_options() if x['usable'] and x['kind']=='bond'
                              and x['args']=={'npc':npc,'style':style}]
                    if possible:session.act('bond',{'npc':npc,'style':style})
        if save_probe and m in (36,80):
            payload=session.save_payload()
            restored=PlaySession13.from_payload(json.loads(json.dumps(payload,ensure_ascii=False)))
            if restored.save_payload()!=payload:raise AssertionError(('save',npc,route,m))
            session=restored
        session.next_month()
    arc=next(a for a in session.engine.story_snapshot() if a['npc']==npc)
    errors=audit_session(session)
    if arc['chapter']!=3:errors.append('story_incomplete')
    if arc['branch']!=route:errors.append('wrong_branch')
    if len(outcomes)!=3:errors.append('not_three_scenes')
    return {'npc':npc,'route':route,'stage_choice':stage_choice,'final_choice':final_choice,'finished':arc['chapter']==3,'scenes':len(outcomes),
            'selected':(session.engine.resolve_endings()['selected'] or {}).get('id',''),
            'audit':not errors,'errors':';'.join(errors),
            'cash':round(session.engine.state.cash,2),'ap_used':sum(l.get('ap',0) for l in session.engine.state.log),
            'transfer':session.engine.state.earth_transfer_count,
            'epilogue':arc['outcome'] or ''}


def replay_legacy():
    obj=json.loads((ROOT/'tests'/'v11_witness_paths.json').read_text(encoding='utf8'))
    rows=[]
    for target,path in obj['paths'].items():
        s=PlaySession13(seed=obj['seed'],focus=target)
        by_month={m:[] for m in range(120)}
        for a in path:
            if a['action']!='TRANSFER':by_month[a['month']].append(a)
        errors=[]
        for m in range(120):
            for act in by_month[m]:
                if act['action']=='SPECIALIZE':s.specialize(act['stat']);continue
                args={k:act[k] for k in ('facility','level','stat','hobby','id','choice','npc','style') if k in act}
                try:r=s.act(act['action'],args)
                except ValueError as exc:
                    errors.append(f'{m}: {exc}')
                    break
                if r['ok']!=act['success']:errors.append(f'{m}: score mismatch')
                if 'check_passed' in act and r['record'].get('check_passed')!=act['check_passed']:
                    errors.append(f'{m}: choice check mismatch')
            s.next_month()
        errors+=audit_session(s)
        selected=(s.engine.resolve_endings()['selected'] or {}).get('id')
        if selected!=target:errors.append(f'selected={selected}')
        if s.engine.ending_missing(s.focus_ending):errors.append('goal_not_met')
        rows.append({'id':target,'name':s.focus_ending['name'],'selected':selected,'goal_met':not s.engine.ending_missing(s.focus_ending),
                     'audit':not errors,'errors':';'.join(errors),'transfer':s.engine.state.earth_transfer_count,
                     'story_chapters':sum(x['chapter'] for x in s.engine.story_snapshot())})
    return rows


def mixed_play(seed,guided_slots):
    """Not an empirical player study: reproducible simple synthetic policies."""
    rng=random.Random(seed)
    endings=PlaySession13().engine.endings
    focus=endings[seed%len(endings)]['id']
    s=PlaySession13(seed=seed,focus=focus)
    errors=[]
    for m in range(120):
        for step in range(4):
            if step<guided_slots:
                suggestion=s.recommend()
                if not suggestion:continue
                if suggestion['kind']=='specialize':
                    try:s.specialize(suggestion['args']['stat'])
                    except ValueError as exc:errors.append(str(exc))
                    continue
                kind=suggestion['kind'];args=suggestion['args']
            else:
                choices=[x for x in s.action_options() if x['usable']]
                if not choices:break
                x=rng.choice(choices);kind=x['kind'];args=x['args']
            try:s.act(kind,args)
            except ValueError as exc:
                errors.append(f'{m} {exc}')
                break
        s.next_month()
    errors+=audit_session(s)
    selected=(s.engine.resolve_endings()['selected'] or {}).get('id')
    return {'seed':seed,'guided_slots':guided_slots,'focus':focus,'selected':selected,
            'goal_met':not s.engine.ending_missing(s.focus_ending),'audit':not errors,
            'errors':';'.join(errors),'registered':bool(selected),
            'ear':round(s.engine.state.ear,2),'cash':round(s.engine.state.cash,2),
            'stress':round(s.engine.state.stress,2),
            'mean_stat':round(statistics.mean(s.engine.state.stats.values()),2),
            'transfer':s.engine.state.earth_transfer_count}


def dump(rows,name):
    with (ROOT/name).open('w',encoding='utf-8-sig',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    from argparse import ArgumentParser
    p=ArgumentParser();p.add_argument('--balance-runs',type=int,default=12);opt=p.parse_args()
    static=validate_story_data()
    print('STATIC',len(static),'ERRORS',static,flush=True)
    stories=[story_route(n,r,save_probe=(c=='commit' and f=='fulfill'),stage_choice=c,final_choice=f)
             for n in ('rian','edwin','sion','eden','kail','noah') for r in 'ab'
             for c in ('commit','careful') for f in ('fulfill','appreciate')]
    dump(stories,'mgl_v13_story_paths.csv')
    print('STORY',sum(x['finished'] and x['audit'] for x in stories),'/',len(stories),flush=True)
    legacy=replay_legacy();dump(legacy,'mgl_v13_legacy_replay.csv')
    print('LEGACY',sum(x['audit'] for x in legacy),'/',len(legacy),flush=True)
    # Identical seeds across all guidance levels, no hidden advantage.
    balance=[mixed_play(20261029+i*97,j) for j in (0,1,2,3,4) for i in range(opt.balance_runs)]
    dump(balance,'mgl_v13_guidance_balance.csv')
    for j in (0,1,2,3,4):
        x=[r for r in balance if r['guided_slots']==j]
        print('GUIDED',j,'GOAL',sum(r['goal_met'] for r in x),'REGISTERED',sum(r['registered'] for r in x),
              'AUDIT',sum(r['audit'] for r in x),'/',len(x),flush=True)
    fail=[x for x in stories+legacy+balance if not x['audit'] or ('finished' in x and not x['finished'])]
    if fail or static:
        print('FAILED',len(fail),[(x.get('npc',x.get('id',x.get('seed'))),x['errors']) for x in fail[:10]])
        sys.exit(1)

if __name__=='__main__':main()
