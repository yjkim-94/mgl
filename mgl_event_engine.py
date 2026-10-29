"""MGL v1.0: deterministic, auditable 120-month rules and project/event/ending resolution.

Standard library only. Project/event definitions are declarative JSON. This is a
playable balance prototype, NOT a verified production game specification.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from pathlib import Path
import copy,json,math,random

ROOT=Path(__file__).resolve().parent
STATS=('INT','CHA','VIT','SEN','SOC','WIL','SKL','MAG')
STAGES=('intro','advanced','professional','master')
COURSE_COST=(0,80,150);COURSE_AP=(2,2,3)

def clamp(x,a=0,b=100):return max(a,min(b,x))

def load_data(root=ROOT):
    with open(root/'mgl_projects.json',encoding='utf8') as f:catalog=json.load(f)
    with open(root/'mgl_ending_conditions.json',encoding='utf8') as f:ed=json.load(f)
    return catalog,ed

@dataclass
class State:
    month:int=-1
    stats:dict=field(default_factory=lambda:{s:20.0 for s in STATS})
    courses:dict=field(default_factory=dict)
    specializations:list=field(default_factory=list)
    mastered:set=field(default_factory=set)
    project_scores:dict=field(default_factory=dict)
    completed_events:set=field(default_factory=set)
    flags:set=field(default_factory=set)
    counters:dict=field(default_factory=dict)
    values:dict=field(default_factory=lambda:{x:20.0 for x in ('discipline','expression','leadership','empathy','visibility','independence','exploration')})
    relation:float=20.
    ear:float=0.
    stress:float=0.
    max_stress:float=0.
    happiness:float=65.
    trust:float=60.
    autonomy:float=45.
    confidence:float=20.
    separation:float=0.
    cash:float=300.
    subsidy:float=0.
    spent:float=0.
    subsidy_spent:float=0.
    ap:int=0
    slots:int=0
    left_astellia:bool=False
    earth_transfer_count:int=0
    log:list=field(default_factory=list)
    invalid_attempts:list=field(default_factory=list)
    failures:list=field(default_factory=list)
    failed_once:set=field(default_factory=set)
    repetitions:dict=field(default_factory=dict)
    chosen_focus:str=''

class GameEngine:
    def __init__(self,catalog=None,endings=None,seed=0,economy='standard'):
        if catalog is None or endings is None:
            c,e=load_data();catalog=c if catalog is None else catalog;endings=e if endings is None else endings
        self.catalog=catalog
        self.endings=endings['endings'] if isinstance(endings,dict) else endings
        self.projects={p['id']:p for p in catalog['projects']}
        self.events={e['id']:e for e in catalog['events']}
        self.facilities=catalog['facility_stat_growth']
        self.state=State(courses={f:[0,0,0] for f in self.facilities})
        self.rng=random.Random(seed)
        self.economy=economy
        self.earnings={'standard':155,'strained':125,'affluent':195}[economy]
        self.upkeep={'standard':100,'strained':105,'affluent':110}[economy]
        self.subsidy_month={'standard':110,'strained':70,'affluent':110}[economy]

    @property
    def age(self):return 10+self.state.month//12 if self.state.month>=0 else 10
    def cap(self,stat,age=None):
        age=self.age if age is None else age
        if age<13:return 45
        if age<16:return 65
        if age<18:return 75
        if stat in self.state.mastered:return 100
        return 95 if stat in self.state.specializations else 75

    def start_month(self,month):
        s=self.state
        if month!=s.month+1 or not 0<=month<120:raise ValueError('Months must advance sequentially from 0 to 119')
        if s.left_astellia:raise ValueError('Earth transfer is irreversible')
        s.month=month;s.ap=0;s.slots=0;s.repetitions={}
        s.cash+=self.earnings-self.upkeep
        s.subsidy=self.subsidy_month
        s.stress=clamp(s.stress-7)
        s.ear=clamp(s.ear+0.15)
        s.happiness=clamp(s.happiness+0.2)
        s.separation=clamp(s.ear*0.9)
        if month==119:
            # the 20th-birthday transfer is finalized by finish(), always and only once.
            pass

    def finish(self):
        s=self.state
        if s.month!=119:raise ValueError('Must complete 120 months')
        if not s.left_astellia:
            s.left_astellia=True;s.earth_transfer_count+=1
            s.log.append({'month':120,'age':20,'action':'TRANSFER','success':True,'ap':0,'cost':0,'note':'Mandatory transfer; no alternative branch'})
        return self.resolve_endings()

    def select_specialization(self,stat):
        s=self.state
        if self.age<16 or stat not in STATS or stat in s.specializations or len(s.specializations)>=2:return False
        s.specializations.append(stat)
        s.log.append({'month':s.month,'age':self.age,'action':'SPECIALIZE','stat':stat,'success':True,'ap':0,'cost':0})
        return True

    def education_missing(self,education):
        s=self.state;out=[]
        for req in education:
            f=req['facility'];st=req['stage'];n=req['count']
            if f not in s.courses:out.append(('unknown_facility',f));continue
            stage_idx=STAGES.index(st)
            if stage_idx==3:
                if self.age<18 or s.courses[f][2]<10:out.append(('master_stage',f,10))
            elif s.courses[f][stage_idx]<n:out.append(('course',f,stage_idx,n-s.courses[f][stage_idx]))
        return out

    def missing(self,item):
        s=self.state;d=[]
        if self.age<item.get('min_age',0):d.append(('age',item['min_age']))
        for x in self.education_missing(item.get('education',[])):d.append(x)
        for stat,v in item.get('required_stats',{}).items():
            if s.stats[stat]+1e-8<v:d.append(('stat',stat,v))
        for pid in item.get('prerequisites',{}).get('projects',[]):
            if pid not in s.project_scores:d.append(('project',pid))
        for eid in item.get('prerequisites',{}).get('events',[]):
            if eid not in s.completed_events:d.append(('event',eid))
        if s.ear+1e-8<item.get('ear_min',0):d.append(('ear',item['ear_min']))
        for k,v in item.get('counters',{}).items():
            if s.counters.get(k,0)<v:d.append(('counter',k,v))
        if s.relation+1e-8<item.get('relation_min',0):d.append(('relation',item['relation_min']))
        for k,v in item.get('value_min',{}).items():
            if s.values.get(k,0)+1e-8<v:d.append(('value',k,v))
        if s.autonomy+1e-8<item.get('autonomy_min',0):d.append(('autonomy',item['autonomy_min']))
        return d

    def project_score(self,p):
        s=self.state
        stats=p['required_stats'];stat_score=sum(s.stats[k] for k in stats)/max(1,len(stats))
        ed=p['education'];ed_score=100 if not ed else min(100,min((100*s.courses[x['facility']][min(2,STAGES.index(x['stage']))]/x['count']) for x in ed))
        prev=[s.project_scores[x] for x in p['prerequisites']['projects']]
        predecessor=80 if not prev else sum(prev)/len(prev)
        condition=clamp(100-0.85*s.stress+0.15*(s.happiness-50))
        return 0.4*stat_score+0.3*ed_score+0.2*predecessor+0.1*condition

    def event_score(self,e):
        s=self.state
        avg=sum(s.stats[k] for k in e['required_stats'])/len(e['required_stats']) if e['required_stats'] else 60
        support=clamp(100-0.6*s.stress+0.2*(s.happiness-50))
        # An individual event is deterministic for a fixed state/seed; no hidden re-rolls.
        return .55*avg+.25*support+.20*min(100,50+s.confidence)

    def _gain(self,stat,base):
        s=self.state;x=s.stats[stat]
        rate=1 if x<40 else .65 if x<60 else .37 if x<75 else .19 if x<95 else .06
        condition=0.7 if s.stress>=70 else 0.85 if s.stress>=45 else 1
        key=('growth',stat);prev=s.repetitions.get(key,0)
        repeat=1 if prev<2 else .60
        s.repetitions[key]=prev+1
        s.stats[stat]=min(self.cap(stat),x+base*rate*condition*repeat)

    def act(self,kind,**kwargs):
        s=self.state
        if s.month<0 or s.month>=120 or s.left_astellia:return False,'invalid_date'
        f=kwargs.get('facility');level=kwargs.get('level');stat=kwargs.get('stat');target=kwargs.get('id');hobby=kwargs.get('hobby')
        ap={'course':COURSE_AP[level] if kind=='course' and isinstance(level,int) and 0<=level<=2 else 2,
            'study':2,'rest':1,'ear':1,'work':2,'hobby':2,'project':self.projects[target]['ap'] if kind=='project' and target in self.projects else 100,
            'event':self.events[target]['ap'] if kind=='event' and target in self.events else 100}.get(kind,100)
        cost={'course':COURSE_COST[level] if kind=='course' and isinstance(level,int) and 0<=level<=2 else 0,
              'project':self.projects[target]['cost'] if kind=='project' and target in self.projects else 0,
              'event':self.events[target]['cost'] if kind=='event' and target in self.events else 0}.get(kind,0)
        restricted=kind in ('course','project','event')
        discount=min(s.subsidy,cost) if restricted else 0
        own_cost=cost-discount
        error=None
        if s.ap+ap>8:error='ap_limit'
        elif s.slots>=4:error='slot_limit'
        elif s.cash+1e-8<own_cost:error='cash'
        elif kind=='course':
            if f not in self.facilities or level not in (0,1,2):error='course_parameters'
            elif s.courses[f][level]>=(6,8,10)[level]:error='course_completed'
            elif (level==1 and (self.age<13 or s.courses[f][0]<6)) or (level==2 and (self.age<16 or s.courses[f][1]<8)):error='course_locked'
        elif kind=='study' and stat not in STATS:error='stat_invalid'
        elif kind=='hobby' and hobby not in HOBBIES:error='hobby_invalid'
        elif kind=='hobby' and hobby=='romance' and self.age<14:error='hobby_age_locked'
        elif kind in ('project','event'):
            obj=self.projects.get(target) if kind=='project' else self.events.get(target)
            if obj is None:error='unknown_id'
            elif target in (s.project_scores if kind=='project' else s.completed_events):error='already_done'
            elif target in s.failed_once and not obj.get('retryable',False):error='no_retry'
            elif self.missing(obj):error='prerequisites'
        elif kind not in ('ear','rest','work','study','hobby'):error='action_invalid'
        if error:
            s.invalid_attempts.append({'month':s.month,'kind':kind,'id':target,'error':error})
            return False,error
        pressure={'course':(3,5,8)[level] if kind=='course' else 0,'study':3,'rest':-23,
                  'ear':1,'work':7,'hobby':3,'project':{'P1':5,'P2':9,'P3':12,'M':15}[self.projects[target]['grade']] if kind=='project' else 0,
                  'event':5}.get(kind,0)
        if kind!='rest' and s.stress+pressure>100:
            s.invalid_attempts.append({'month':s.month,'kind':kind,'error':'stress_cap'})
            return False,'stress_cap'
        s.ap+=ap;s.slots+=1;s.cash-=own_cost;s.subsidy-=discount;s.spent+=cost;s.subsidy_spent+=discount
        s.stress=clamp(s.stress+pressure);s.max_stress=max(s.max_stress,s.stress)
        score=None;success=True
        if kind=='course':
            s.courses[f][level]+=1
            main,aux=self.facilities[f][level]
            self._gain(main,(3.2,3.8,4.4)[level]);self._gain(aux,(0.9,1.1,1.4)[level]);s.confidence=clamp(s.confidence+0.3)
        elif kind=='study':self._gain(stat,4.5)
        elif kind=='rest':s.happiness=clamp(s.happiness+2.4)
        elif kind=='ear':s.ear=clamp(s.ear+5);s.autonomy=clamp(s.autonomy+.35)
        elif kind=='work':s.cash+=115;s.stress=clamp(s.stress+0);s.autonomy=clamp(s.autonomy+.5)
        elif kind=='hobby':
            st1,st2=HOBBIES[hobby];self._gain(st1,3.2);self._gain(st2,1.0)
            s.counters[hobby]=s.counters.get(hobby,0)+1
            VALUE_MAP={'fitness':('discipline',),'dance':('expression',),'music':('expression',),'community':('leadership',),'leadership':('leadership',),'friendship':('empathy',),'romance':('empathy',),'digital':('visibility',),'creative':('visibility','independence'),'independence':('independence',),'travel':('exploration',)}
            for key in VALUE_MAP[hobby]:s.values[key]=clamp(s.values[key]+3.5)
            if hobby in ('community','friendship','romance','leadership','dance','music'):
                s.relation=clamp(s.relation+4.5)
            s.happiness=clamp(s.happiness+.7);s.autonomy=clamp(s.autonomy+(1.6 if hobby=='independence' else .3))
        elif kind=='project':
            p=self.projects[target];score=self.project_score(p)
            success=score+1e-8>=p['success_threshold']
            if success:
                s.project_scores[target]=round(score,3)
                s.confidence=clamp(s.confidence+p['rewards']['career_confidence']);s.happiness=clamp(s.happiness+1)
                if p['grade']=='M':
                    # A master achievement unlocks a 100 cap, but never grants free raw points.
                    for key in p['required_stats']:
                        if key in s.specializations:s.mastered.add(key)
            else:
                s.failed_once.add(target);s.stress=clamp(s.stress+p['failure']['stress']);s.max_stress=max(s.max_stress,s.stress)
                s.failures.append({'month':s.month,'kind':'project','id':target,'score':round(score,2),'threshold':p['success_threshold']})
        elif kind=='event':
            e=self.events[target];score=self.event_score(e)
            success=score+1e-8>=e['success_threshold']
            if success:
                s.completed_events.add(target);s.flags.update(e['rewards'].get('flags',[]));s.confidence=clamp(s.confidence+e['rewards'].get('career_confidence',0));s.happiness=clamp(s.happiness+e['rewards'].get('happiness',0))
            else:
                s.failed_once.add(target);s.stress=clamp(s.stress+e['failure']['stress']);s.max_stress=max(s.max_stress,s.stress)
                s.failures.append({'month':s.month,'kind':'event','id':target,'score':round(score,2),'threshold':e['success_threshold']})
        rec={'month':s.month,'age':self.age,'action':kind,'success':success,'ap':ap,'cost':cost,'own_cost':round(own_cost,2),'discount':discount,'stress':round(s.stress,2)}
        if f is not None:rec['facility']=f
        if level is not None:rec['level']=level
        if stat is not None:rec['stat']=stat
        if hobby is not None:rec['hobby']=hobby
        if target is not None:rec['id']=target
        if score is not None:rec['score']=round(score,3)
        s.log.append(rec)
        return success,('success' if success else 'score_failed')

    def ending_missing(self,ending):
        s=self.state;m=ending['mandatory'];missing=[]
        for k,v in m.get('stats',{}).items():
            if s.stats[k]+1e-8<v:missing.append(('stat',k,round(v-s.stats[k],2)))
        if s.ear+1e-8<m.get('ear_min',0):missing.append(('ear',round(m['ear_min']-s.ear,2)))
        for x in self.education_missing(m.get('education',[])):missing.append(x)
        for p in m.get('projects',[]):
            if p not in s.project_scores:missing.append(('project',p))
        for ev in m.get('events',[]):
            if ev not in s.completed_events:missing.append(('event',ev))
        for h,n in m.get('counters',{}).items():
            if s.counters.get(h,0)<n:missing.append(('counter',h,n-s.counters.get(h,0)))
        if s.relation+1e-8<m.get('relation_min',0):missing.append(('relation',round(m['relation_min']-s.relation,2)))
        for k,v in m.get('value_min',{}).items():
            if s.values.get(k,0)+1e-8<v:missing.append(('value',k,round(v-s.values.get(k,0),2)))
        if s.autonomy+1e-8<m.get('autonomy_min',0):missing.append(('autonomy',round(m['autonomy_min']-s.autonomy,2)))
        return missing

    def resolve_endings(self):
        s=self.state
        if not s.left_astellia or s.earth_transfer_count!=1:return {'eligible':[],'selected':None,'reason':'mandatory earth transfer not complete'}
        eligible=[]
        for ed in self.endings:
            if self.ending_missing(ed):continue
            w=ed['priority'];score=w['base']+w['career_confidence_weight']*s.confidence+w['ear_weight']*s.ear+w['happiness_weight']*s.happiness
            if ed['type']=='special' and s.chosen_focus==ed['id']:score+=w.get('special_focus_bonus',0)
            eligible.append({'id':ed['id'],'name':ed['name'],'score':round(score,3)})
        eligible.sort(key=lambda x:(-x['score'],x['id']))
        return {'eligible':eligible,'selected':eligible[0] if eligible else None}

# for youth-safe, nonsexual hobbies. Adult-only clubbing is not an available action.
HOBBIES={'fitness':('VIT','WIL'),'dance':('CHA','VIT'),'music':('SEN','CHA'),
         'community':('SOC','WIL'),'leadership':('SOC','INT'),'friendship':('SOC','SEN'),
         'romance':('SEN','SOC'),'digital':('SKL','CHA'),'creative':('SEN','SKL'),
         'independence':('WIL','INT'),'travel':('SEN','VIT')}

def validate_catalog(catalog,ending_data):
    """Fail on unresolved dependencies, cycles, age/cap impossibility, and invalid references."""
    e=ending_data['endings'] if isinstance(ending_data,dict) else ending_data
    errors=[];nodes={x['id']:x for x in catalog['projects']+catalog['events']}
    if len(nodes)!=len(catalog['projects'])+len(catalog['events']):errors.append('duplicate project/event IDs')
    edges={k:set() for k in nodes}
    facilities=set(catalog['facility_stat_growth'])
    for node in nodes.values():
        for label,values in node.get('prerequisites',{}).items():
            for p in values:
                if p not in nodes:errors.append(f'{node["id"]}: missing {label} {p}')
                else:edges[node['id']].add(p)
        for req in node.get('education',[]):
            if req['facility'] not in facilities:errors.append(f'{node["id"]}: missing facility {req["facility"]}')
            if req['stage'] not in STAGES:errors.append(f'{node["id"]}: unknown stage {req["stage"]}')
            else:
                idx=STAGES.index(req['stage']); minage=(10,13,16,18)[idx];limit=(6,8,10,1)[idx]
                if node['min_age']<minage:errors.append(f'{node["id"]}: min_age below education stage unlock')
                if req['count']>limit:errors.append(f'{node["id"]}: course count impossible')
        for st,val in node.get('required_stats',{}).items():
            if st not in STATS or val>100:errors.append(f'{node["id"]}: stat impossible {st} {val}')
            maxcap=45 if node['min_age']<13 else 65 if node['min_age']<16 else 75 if node['min_age']<18 else 95
            if val>maxcap:errors.append(f'{node["id"]}: stat requires age beyond min-age {st}:{val}>{maxcap}')
    visited=set();onstack=set();order=[]
    def visit(n):
        if n in onstack:errors.append(f'cyclic prerequisite at {n}');return
        if n in visited:return
        onstack.add(n)
        for x in edges[n]:visit(x)
        onstack.remove(n);visited.add(n);order.append(n)
    for n in nodes:visit(n)
    for ending in e:
        m=ending['mandatory']
        if any(x not in nodes for x in m.get('projects',[])+m.get('events',[])):errors.append(f'{ending["id"]}: unresolved ending prerequisite')
        if sum(v>75 for v in m.get('stats',{}).values())>2:errors.append(f'{ending["id"]}: requires >2 specialization slots')
        for k in m.get('counters',{}):
            if k not in HOBBIES:errors.append(f'{ending["id"]}: invalid hobby {k}')
    return {'ok':not errors,'errors':errors,'nodes':len(nodes),'edges':sum(map(len,edges.values())),'topological_order':order}

if __name__=='__main__':
    c,e=load_data();v=validate_catalog(c,e)
    print(json.dumps({k:v[k] for k in ('ok','errors','nodes','edges')},ensure_ascii=False,indent=2))
