"""MGL v1.0 120-turn guided path search, seeded strategy benchmark, replay auditing.
Run: python mgl_simulator.py [--attempts 4] [--balance-runs 12]
"""
from __future__ import annotations
import argparse,csv,json,random,collections,statistics
from pathlib import Path
from mgl_event_engine import GameEngine,load_data,validate_catalog,STAGES,STATS,HOBBIES,COURSE_AP,COURSE_COST,clamp
ROOT=Path(__file__).resolve().parent

def dependencies(engine,ending):
    allitems={**engine.projects,**engine.events};keep=set()
    def add(x):
        if x in keep:return
        for values in allitems[x].get('prerequisites',{}).values():
            for y in values:add(y)
        keep.add(x)
    for x in ending['mandatory'].get('events',[])+ending['mandatory'].get('projects',[]):add(x)
    # stable topological order sorted by earliest age, then phase
    pending=set(keep);order=[]
    while pending:
        available=[x for x in pending if not any(y in pending for vals in allitems[x].get('prerequisites',{}).values() for y in vals)]
        if not available:raise ValueError('dependency cycle')
        available.sort(key=lambda x:(allitems[x]['min_age'],x))
        order.extend(available)
        for x in available:pending.remove(x)
    return order

class Planner:
    def __init__(self,engine,ending,seed=0,mode='focused',secondary=None):
        self.engine=engine;self.ending=ending;self.mode=mode;self.secondary=secondary
        self.rng=random.Random(seed)
        self.order=dependencies(engine,ending);self.items={**engine.projects,**engine.events}
        engine.state.chosen_focus=ending['id']

    def can_afford(self,action):
        e=self.engine;s=e.state;k=action['kind'];z=action['args']
        if s.slots>=4:return False
        if k=='hobby' and z.get('hobby')=='romance' and e.age<14:return False
        if k=='course' and (s.courses[z['facility']][z['level']] >= (6,8,10)[z['level']] or (z['level']==1 and e.age<13) or (z['level']==2 and e.age<16)):return False
        if k=='course':
            ap=COURSE_AP[z['level']];cost=COURSE_COST[z['level']]
        elif k in ('project','event'):
            o=e.projects.get(z['id']) if k=='project' else e.events.get(z['id'])
            ap=o['ap'];cost=o['cost']
        else:ap=1 if k in ('rest','ear') else 2;cost=0
        pressure={'course':(3,5,8)[z['level']] if k=='course' else 0,'study':3,'rest':-23,'ear':1,'work':7,'hobby':3,'project':{'P1':5,'P2':9,'P3':12,'M':15}[e.projects[z['id']]['grade']] if k=='project' else 0,'event':5}[k]
        if ap+s.ap>8 or (k!='rest' and s.stress+pressure>100):return False
        return s.cash>=cost-min(s.subsidy,cost)-1e-8

    @staticmethod
    def action(kind,**kwargs):return {'kind':kind,'args':kwargs}

    def educate(self,reqs):
        s=self.engine.state;age=self.engine.age
        # training prerequisites in order of stage, keeping first-choice facility priority
        for req in reqs:
            f=req['facility'];level=STAGES.index(req['stage']);counts=s.courses[f]
            for i in range(min(2,level)+1):
                need=(6,8,10)[i] if i<level else req['count']
                if counts[i]>=need:continue
                if i==1 and (age<13 or counts[0]<6):break
                if i==2 and (age<16 or counts[1]<8):break
                if self.engine.cap('INT') < 1:break
                return self.action('course',facility=f,level=i)
        return None

    def study_for(self,needed,prioritize_high=False):
        s=self.engine.state;e=self.engine
        deficits=[(min(x,e.cap(k))-s.stats[k],k) for k,x in needed.items() if min(x,e.cap(k))-s.stats[k]>1e-6]
        if not deficits:return None
        # high attributes grow slowly, prioritize the largest normalized shortfall
        deficits.sort(key=lambda d:(-d[0], d[1]))
        return self.action('study',stat=deficits[0][1])

    def any_required_course(self):
        m=self.ending['mandatory'];reqs=m.get('education',[])
        return self.educate(reqs)

    def missing_step(self,item):
        e=self.engine;s=e.state
        unmet=e.missing(item)
        if not unmet:
            kind='project' if item['id'] in e.projects else 'event'
            score=e.project_score(item) if kind=='project' else e.event_score(item)
            if score>=item['success_threshold']+2.5:return self.action(kind,id=item['id'])
            if s.stress>20:return self.action('rest')
            # avoid repeated failure; improve one of the main stats
            possible=self.study_for({k:min(95,v+8) for k,v in item['required_stats'].items()})
            return possible
        # prerequisites blocked by age: prepare for it, but skip the locked action itself
        f=[x for x in unmet if x[0]=='course']
        if f:
            a=self.educate(item.get('education',[]))
            if a:return a
        f=[x for x in unmet if x[0]=='stat']
        if f:
            a=self.study_for({x[1]:x[2] for x in f})
            if a:return a
        if any(x[0]=='ear' for x in unmet):return self.action('ear')
        f=[x for x in unmet if x[0]=='counter']
        if f:return self.action('hobby',hobby=f[0][1])
        v=[x for x in unmet if x[0]=='value']
        if v:
            value_hobbies={'discipline':['fitness'],'expression':['dance','music'],'leadership':['community','leadership'],'empathy':['friendship','romance'],'visibility':['digital','creative'],'independence':['independence','creative'],'exploration':['travel']}
            opts=value_hobbies[v[0][1]]
            return self.action('hobby',hobby=next((h for h in opts if h!='romance' or e.age>=14),opts[0]))
        if any(x[0]=='autonomy' for x in unmet):return self.action('hobby',hobby='independence')
        if any(x[0]=='relation' for x in unmet):
            hobbies=self.ending['mandatory'].get('counters',{})
            hobby=next((x for x in hobbies if x in ('community','friendship','romance','leadership','dance','music')),'friendship')
            return self.action('hobby',hobby=hobby)
        return None

    def focus_choice(self):
        e=self.engine;s=e.state;m=self.ending['mandatory']
        # Aging phase preparatory actions: program unlocks at 13 and 16, so courses may be taken ahead of events.
        a=self.any_required_course()
        if a:return a
        for id in self.order:
            if id in s.project_scores or id in s.completed_events:continue
            item=self.items[id]
            # do not skip prerequisites: available nodes only
            if any(p not in s.project_scores for p in item['prerequisites']['projects']):continue
            if any(p not in s.completed_events for p in item['prerequisites']['events']):continue
            a=self.missing_step(item)
            if a:return a
        # meet ending attributes, Earth readiness and youth-safe hobby counters
        a=self.study_for(m['stats'])
        if a:return a
        for h,v in m.get('counters',{}).items():
            if s.counters.get(h,0)<v:return self.action('hobby',hobby=h)
        if s.relation<m.get('relation_min',0):
            return self.action('hobby',hobby=next((h for h in m['counters'] if h in ('community','leadership','romance','friendship','dance','music')),'friendship'))
        if s.ear<m['ear_min']:return self.action('ear')
        value_hobbies={'discipline':'fitness','expression':'dance','leadership':'community','empathy':'friendship','visibility':'digital','independence':'independence','exploration':'travel'}
        for value,n in m.get('value_min',{}).items():
            if s.values.get(value,0)<n:return self.action('hobby',hobby=value_hobbies[value])
        if s.autonomy<m.get('autonomy_min',0):return self.action('hobby',hobby='independence')
        return None

    def choice(self):
        e=self.engine;s=e.state;m=self.ending['mandatory']
        if s.stress>67:return self.action('rest')
        if self.mode=='random':
            kinds=['study','course','hobby','ear','work','rest','project','event']
            k=self.rng.choice(kinds)
            if k=='course':
                f=self.rng.choice(list(e.facilities));c=s.courses[f]
                lv=0 if c[0]<6 or e.age<13 else 1 if c[1]<8 or e.age<16 else 2
                return self.action('course',facility=f,level=lv)
            if k in ('project','event'):
                opts=e.projects if k=='project' else e.events
                completed=s.project_scores if k=='project' else s.completed_events
                choices=[o for o in opts.values() if o['id'] not in completed and not e.missing(o)]
                return self.action(k,id=self.rng.choice(choices)['id']) if choices else self.action('hobby',hobby=self.rng.choice(list(HOBBIES)))
            if k=='study':return self.action('study',stat=self.rng.choice(STATS))
            if k=='hobby':return self.action('hobby',hobby=self.rng.choice(list(HOBBIES)))
            return self.action(k)
        # strategy-specific deliberate deviations (focus still has a chance)
        if self.mode=='balanced' and self.rng.random()<.45:
            low=min(STATS,key=lambda x:s.stats[x]);return self.action('study',stat=low)
        if self.mode=='relationship' and self.rng.random()<.60:
            return self.action('hobby',hobby=self.rng.choice(['community','friendship','leadership','romance']))
        if self.mode=='frugal' and self.rng.random()<.22 and s.cash<3500:return self.action('work')
        if self.mode=='mixed' and self.rng.random()<.40:
            if self.rng.random()<.6:return self.action('hobby',hobby=self.rng.choice(list(HOBBIES)))
            return self.action('study',stat=self.rng.choice(STATS))
        return self.focus_choice()

    def play(self,actions_per_month=4):
        e=self.engine;s=e.state
        # preselect at 16, no ability points are silently added and only two skills may specialize
        special_keys=[k for k,v in self.ending['mandatory']['stats'].items() if v>75]
        extras=sorted(self.ending['mandatory']['stats'],key=self.ending['mandatory']['stats'].get,reverse=True)
        specs=(special_keys+[x for x in extras if x not in special_keys])[:2]
        for month in range(120):
            e.start_month(month)
            if e.age==16:
                for st in specs:e.select_specialization(st)
            for _ in range(actions_per_month):
                a=self.choice()
                if a is None:break
                if not self.can_afford(a):
                    # do not attempt actions which would exceed AP, cash, stress, slots
                    candidates=[self.action('ear'),self.action('rest'),self.action('work')]
                    a=next((x for x in candidates if self.can_afford(x)),None)
                    if a is None:break
                success,message=e.act(a['kind'],**a['args'])
                if not success and message not in ('score_failed',):
                    # Invalid requests are recorded and rejected without mutation.
                    # Fail gracefully if a random strategy targets an early-stage course already locked.
                    break
        decision=e.finish()
        target_met=not e.ending_missing(self.ending)
        return {'target':self.ending['id'],'name':self.ending['name'],'type':self.ending['type'],'grade':self.ending['grade'],
                'pass':target_met,'selected':decision['selected']['id'] if decision['selected'] else '',
                'ending_count':len(decision['eligible']), 'missing':e.ending_missing(self.ending),
                'stats':{k:round(v,2) for k,v in s.stats.items()},'ear':round(s.ear,2),'stress':round(s.stress,2),
                'max_stress':round(s.max_stress,2),'cash':round(s.cash,2),'spent':round(s.spent,2),
                'subsidy_used':round(s.subsidy_spent,2),'relation':round(s.relation,2),
                'actions':len([x for x in s.log if x['action'] not in ('SPECIALIZE','TRANSFER')]),
                'project_count':len(s.project_scores),'event_count':len(s.completed_events),
                'invalid_attempt_count':len(s.invalid_attempts),'failed_checks':len(s.failures),
                'earth_transfer_count':s.earth_transfer_count,'log':s.log}

def audit_history(engine):
    """Independent replay enforces every logged AP/slot/cash/age/precondition/score transaction."""
    c=engine.catalog;e={'endings':engine.endings};s=engine.state
    rec=GameEngine(c,e,seed=0,economy=engine.economy)
    action_logs=[x for x in s.log if x['action'] not in ('TRANSFER',)]
    events_by_month=collections.defaultdict(list)
    for x in action_logs:events_by_month[x['month']].append(x)
    errors=[]
    for month in range(120):
        rec.start_month(month)
        for x in events_by_month[month]:
            if x['action']=='SPECIALIZE':
                if not rec.select_specialization(x['stat']):errors.append(f'specialization month {month}')
                continue
            args={k:x[k] for k in ('facility','level','stat','hobby','id') if k in x}
            valid,message=rec.act(x['action'],**args)
            if valid!=x['success']:
                errors.append(f'month {month}: {x["action"]} outcome mismatch ({message})')
            # A failed project score is legitimate, but forbidden actions are not.
            if not valid and message!='score_failed':errors.append(f'month {month}: invalid executed action {message}')
        if rec.state.ap>8 or rec.state.slots>4:errors.append(f'month {month}: AP/slot budget')
        if rec.state.cash < -1e-7:errors.append(f'month {month}: negative money')
        if any(v>rec.cap(k)+1e-7 or v < -1e-7 for k,v in rec.state.stats.items()):errors.append(f'month {month}: cap violation')
    rec.finish()
    if rec.state.earth_transfer_count!=1:errors.append('missing Earth transfer')
    if rec.state.project_scores!=s.project_scores or rec.state.completed_events!=s.completed_events:errors.append('replay record mismatch')
    if len(rec.state.log)!=len(s.log):errors.append('replay action log mismatch')
    return errors

def test_all(attempts=4,seed=20261029):
    c,d=load_data();validation=validate_catalog(c,d)
    if not validation['ok']:raise ValueError(validation['errors'])
    results=[];instances={}
    for ed in d['endings']:
        best=None;bestscore=-1e20
        for i in range(attempts):
            eng=GameEngine(c,d,seed=seed+i)
            sim=Planner(eng,ed,seed+i)
            r=sim.play()
            missing=r['missing']
            score=100000 if r['pass'] else -2000*len(missing)-sum(x[2] if len(x)>2 and isinstance(x[2],(float,int)) else 1 for x in missing)
            score-=r['invalid_attempt_count']*100
            if score>bestscore:best,bestscore=(r,eng),score
            if r['pass'] and not r['invalid_attempt_count']:break
        r,eng=best
        aud=audit_history(eng)
        r['audit_errors']=aud;r['audit_ok']=not aud
        results.append(r);instances[ed['id']]=eng
    return results,instances,validation

def balance_test(c,d,runs=12,seed=20261029):
    # one fixed target per strategy run, drawn from the 48-ending pool.
    strategies=['focused','balanced','relationship','frugal','special','random','mixed']
    result=[]
    for mode in strategies:
        for i in range(runs):
            rng=random.Random(seed+1000*i+strategies.index(mode)*37)
            if mode=='special':ed=d['endings'][40+i%8]
            else:ed=rng.choice(d['endings'][:40])
            econ='strained' if mode=='frugal' else 'standard'
            eng=GameEngine(c,d,seed=seed+i,economy=econ)
            r=Planner(eng,ed,seed=seed+100*i+strategies.index(mode),mode='focused' if mode=='special' else mode).play()
            result.append({'strategy':mode,'run':i,'target':ed['id'],'success':r['pass'],'selected':r['selected'] or 'NONE',
                           'ending_count':r['ending_count'],'mean_stat':round(statistics.mean(r['stats'].values()),2),
                           'ear':r['ear'],'stress':r['stress'],'max_stress':r['max_stress'],'cash':r['cash'],
                           'invalid':r['invalid_attempt_count'],'audit_ok':not audit_history(eng)})
    return result

def write_files(results,instances,static,balance,seed,attempts):
    short=[{k:v for k,v in r.items() if k!='log'} for r in results]
    with (ROOT/'mgl_validation_results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['ID','엔딩','유형','등급','120턴 달성','최종 선택 엔딩','선택 가능 엔딩 수','부족 조건','재생검증','감사 오류','프로젝트 수','이벤트 수','행동 수','유효성 위반 시도','판정 실패','EAR','최종 스트레스','최대 스트레스','잔액 G','지출 G','지급 지원금 G','20세 지구 이동'])
        for r in results:
            w.writerow([r['target'],r['name'],r['type'],r['grade'],r['pass'],r['selected'],r['ending_count'],json.dumps(r['missing'],ensure_ascii=False),r['audit_ok'],'; '.join(r['audit_errors']),r['project_count'],r['event_count'],r['actions'],r['invalid_attempt_count'],r['failed_checks'],r['ear'],r['stress'],r['max_stress'],r['cash'],r['spent'],r['subsidy_used'],r['earth_transfer_count']])
    with (ROOT/'mgl_validation_details.json').open('w',encoding='utf8') as f:json.dump({'seed':seed,'attempts':attempts,'static':{k:static[k] for k in ('ok','errors','nodes','edges')},'results':short},f,ensure_ascii=False,indent=2)
    with (ROOT/'mgl_balance_trials.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=balance[0].keys());w.writeheader();w.writerows(balance)
    with (ROOT/'mgl_paths.json').open('w',encoding='utf8') as f:
        json.dump({'seed':seed,'paths':{id:eng.state.log for id,eng in instances.items()}},f,ensure_ascii=False,indent=1)
    return short

def main():
    p=argparse.ArgumentParser();p.add_argument('--attempts',type=int,default=4);p.add_argument('--balance-runs',type=int,default=12);p.add_argument('--seed',type=int,default=20261029)
    args=p.parse_args()
    c,d=load_data();results,instances,static=test_all(args.attempts,args.seed)
    balance=balance_test(c,d,args.balance_runs,args.seed)
    write_files(results,instances,static,balance,args.seed,args.attempts)
    print('PASS',sum(x['pass'] for x in results),'/',len(results),'AUDIT',sum(x['audit_ok'] for x in results),'/',len(results),'STATIC',static['ok'])
    print('INVALID ATTEMPTS',sum(x['invalid_attempt_count'] for x in results),'SCORE FAILURES',sum(x['failed_checks'] for x in results))
    for r in results:
        if not r['pass'] or not r['audit_ok']:print('FAIL',r['target'],r['name'],r['missing'][:6],r['audit_errors'][:3],r['stats'],r['cash'])
    for mode in ('focused','balanced','relationship','frugal','special','random','mixed'):
        arr=[x for x in balance if x['strategy']==mode]
        print('STRATEGY',mode,'target',sum(x['success'] for x in arr),'/',len(arr),'any',sum(x['selected']!='NONE' for x in arr),'mean stat',round(statistics.mean(x['mean_stat'] for x in arr),1),'EAR',round(statistics.mean(x['ear'] for x in arr),1),'CASH',round(statistics.mean(x['cash'] for x in arr),1),'AUDIT',sum(x['audit_ok'] for x in arr))

if __name__=='__main__':main()
