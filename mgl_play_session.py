"""MGL v1.2: playable month-by-month session on top of the v1.1 rule engine.

The social/project engines are intentionally NOT duplicated here. UI operations
use exactly the same engine.act() and engine.finish() rules as headless tests.
Standard-library only. All dates represent a fictional 120-month timeline.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import fields
from pathlib import Path
import json
import math
import re

from mgl_event_engine import State, STATS, STAGES, HOBBIES, COURSE_AP, COURSE_COST, load_data
from mgl_social_engine import MGL11Engine, NPCBond

ROOT = Path(__file__).resolve().parent
SAVE_VERSION = 1

STAT_NAMES = {'INT':'지능','CHA':'매력','VIT':'체력','SEN':'감성','SOC':'사교성',
              'WIL':'정신력','SKL':'기술','MAG':'마법 적성'}
STAGE_NAMES = ('입문','심화','전문')
HOBBY_NAMES = {'fitness':'운동','dance':'무용','music':'음악','community':'모임 활동',
               'leadership':'리더십','friendship':'우정','romance':'첫사랑·교제',
               'digital':'디지털 제작','creative':'창작','independence':'독립 연습','travel':'여행'}
BOND_NAMES = {'listen':'이야기 들어주기','collaborate':'함께 과제하기','share':'일상 나누기','reconcile':'갈등 풀기'}
SEASONS = ('겨울','겨울','봄','봄','봄','여름','여름','여름','가을','가을','가을','겨울')


def encode(value):
    """Lossless JSON encoding of nested sets/tuples used by the base engine."""
    if isinstance(value, set):
        return {'__mgl_type__':'set','items':[encode(x) for x in sorted(value, key=repr)]}
    if isinstance(value, tuple):
        return {'__mgl_type__':'tuple','items':[encode(x) for x in value]}
    if isinstance(value, dict):
        return {str(k):encode(v) for k,v in value.items()}
    if isinstance(value, list):
        return [encode(v) for v in value]
    if value is None or isinstance(value,(str,bool,int,float)):
        return value
    raise TypeError(f'unsupported serialization type: {type(value).__name__}')


def decode(value):
    if isinstance(value, list):return [decode(x) for x in value]
    if isinstance(value,dict):
        if value.get('__mgl_type__')=='set' and set(value)=={'__mgl_type__','items'}:
            return set(decode(x) for x in value['items'])
        if value.get('__mgl_type__')=='tuple' and set(value)=={'__mgl_type__','items'}:
            return tuple(decode(x) for x in value['items'])
        return {k:decode(v) for k,v in value.items()}
    return value


def format_missing(entry):
    if isinstance(entry,str):return entry
    if not entry:return '미상'
    key=entry[0];args=entry[1:]
    if key=='age':return f'{args[0]}세 이후'
    if key=='stat':return f'{STAT_NAMES.get(args[0],args[0])} {args[1]:g} 이상'
    if key=='project':return f'선행 프로젝트 {args[0]}'
    if key=='event':return f'선행 진로 이벤트 {args[0]}'
    if key=='course':return f'{args[0]} 교육 {STAGE_NAMES[args[1]]} {args[2]}회 추가'
    if key=='master_stage':return f'{args[0]} 전문 이수 후 18세부터'
    if key=='ear':return f'지구 적응 준비도 {args[0]:g} 이상'
    if key=='value':return f'가치관 {args[0]} {args[1]:g} 이상'
    if key=='counter':return f'{HOBBY_NAMES.get(args[0],args[0])} {args[1]}회 추가'
    if key=='relation':return f'전체 인간관계 {args[0]:g} 이상'
    if key=='autonomy':return f'자율성 {args[0]:g} 이상'
    if key=='npc_strong_bonds':return f'강한 우정 {args[0]}명 추가'
    if key=='life_flag':return f'생활 이벤트 선택: {args[0]}'
    return ', '.join(map(str,entry))


class PlaySession:
    def __init__(self, seed=20261029, economy='standard', focus='J01'):
        c,d=load_data(ROOT)
        if focus not in {e['id'] for e in d['endings']}:
            raise ValueError(f'알 수 없는 엔딩 목표: {focus}')
        self.engine=MGL11Engine(c,d,seed=int(seed),economy=economy)
        self.engine.state.chosen_focus=focus
        self.focus=focus
        self.reports=[]
        self.year_baseline={}
        self.last_month=None
        self.seed=int(seed)
        self.economy=economy
        self.engine.start_month(0)
        self.year_baseline=self._baseline()

    @property
    def ended(self):return self.engine.state.left_astellia

    @property
    def focus_ending(self):
        return next(x for x in self.engine.endings if x['id']==self.focus)

    def set_focus(self, target):
        if self.ended:raise ValueError('지구 이동 후에는 진로 목표를 변경할 수 없습니다.')
        if target not in {x['id'] for x in self.engine.endings}:
            raise ValueError('존재하지 않는 목표입니다.')
        self.focus=target
        self.engine.state.chosen_focus=target
        return self.view()

    def _baseline(self):
        s=self.engine.state
        return {'stats':dict(s.stats),'ear':s.ear,'stress':s.stress,'happiness':s.happiness,
                'cash':s.cash,'relation':s.relation,'log_index':len(s.log),'projects':len(s.project_scores),
                'career_events':len(s.completed_events),'strong_bonds':len(self.engine.strong_bonds()),
                'life_actions':self.engine.life_actions,'npc_actions':self.engine.npc_actions}

    def _summarize_month(self):
        s=self.engine.state
        a=[x for x in s.log if x['month']==s.month and x['action']!='SPECIALIZE']
        counts=Counter(x['action'] for x in a)
        return {'age':self.engine.age,'month':s.month%12+1,'ap_used':s.ap,'ap_unused':8-s.ap,
                'actions':s.slots,'cash':round(s.cash,1),'ear':round(s.ear,2),'stress':round(s.stress,2),
                'summary':dict(counts),'score_failures':sum(not x['success'] for x in a)}

    def _year_report(self):
        s=self.engine.state;b=self.year_baseline
        actions=[x for x in s.log[b['log_index']:] if x['action']!='SPECIALIZE']
        counter=Counter(x['action'] for x in actions)
        delta={k:round(s.stats[k]-b['stats'][k],2) for k in STATS}
        best=sorted(delta.items(),key=lambda x:(-x[1],x[0]))[:3]
        notes=[]
        if s.stress>=60:notes.append('피로가 누적되었습니다. 다음 해에는 휴식 비중을 높여 보세요.')
        if s.ear < 15+(self.engine.age-10)*5:
            notes.append('지구 정착 준비가 현재 연령에 비해 느립니다.')
        if s.cash<200:notes.append('가정 자금이 넉넉하지 않습니다. 교육비와 생활비를 함께 살펴보세요.')
        if counter.get('bond',0)+counter.get('life',0)==0:notes.append('올해는 NPC와의 교류가 없었습니다.')
        if not notes:notes.append('일상과 성장을 이어 갔습니다. 미래를 위한 선택이 쌓이고 있습니다.')
        report={'year':len(self.reports)+1,'age':self.engine.age,
                'stat_delta':delta,'top_growth':[{'stat':k,'name':STAT_NAMES[k],'delta':v} for k,v in best],
                'ear_delta':round(s.ear-b['ear'],2),'cash_delta':round(s.cash-b['cash'],2),
                'happiness_delta':round(s.happiness-b['happiness'],2),
                'strong_bonds':len(self.engine.strong_bonds()),
                'project_completed':len(s.project_scores)-b['projects'],
                'career_events_completed':len(s.completed_events)-b['career_events'],
                'life_event_choices':self.engine.life_actions-b['life_actions'],
                'npc_visits':self.engine.npc_actions-b['npc_actions'],
                'action_counts':dict(counter), 'notes':notes}
        return report

    def next_month(self):
        if self.ended:raise ValueError('20세 지구 이동 후에는 육성을 계속할 수 없습니다.')
        s=self.engine.state
        self.last_month=self._summarize_month()
        report=None
        if s.month%12==11:
            report=self._year_report()
            self.reports.append(report)
        if s.month==119:
            ending=self.engine.finish()
            return {'completed':True,'last_month':self.last_month,'year_report':report,'ending':ending}
        self.engine.start_month(s.month+1)
        if s.month%12==0:self.year_baseline=self._baseline()
        return {'completed':False,'last_month':self.last_month,'year_report':report,'ending':None}

    def act(self,kind,kwargs=None):
        if self.ended:raise ValueError('20세의 지구 이동 이후에는 아스텔리아에서 행동할 수 없습니다.')
        kwargs=kwargs or {}
        ok,message=self.engine.act(kind,**kwargs)
        # A project/event skill check can legitimately fail after spending AP.
        if not ok and message!='score_failed':raise ValueError(f'행동 거부: {message}')
        return {'ok':ok,'reason':message,'record':self.engine.state.log[-1]}

    def specialize(self,stat):
        if self.ended:raise ValueError('이미 지구로 이동했습니다.')
        if not self.engine.select_specialization(stat):raise ValueError('전문화는 16세부터, 최대 두 능력치까지 가능합니다.')
        return {'stat':stat,'specializations':list(self.engine.state.specializations)}

    def _core_related(self):
        """Career graph closure for compact project/event UI; all content stays accessible."""
        relevant=set(self.focus_ending['mandatory'].get('projects',[])+self.focus_ending['mandatory'].get('events',[]))
        queue=list(relevant)
        while queue:
            id=queue.pop()
            node=self.engine.projects.get(id) or self.engine.events.get(id)
            if not node:continue
            for dep in node.get('prerequisites',{}).get('projects',[])+node.get('prerequisites',{}).get('events',[]):
                if dep not in relevant:relevant.add(dep);queue.append(dep)
        return relevant

    def _action_entry(self,kind,label,args,ap,cost=0,stress=0,missing=None,score=None,threshold=None,description='',group=None):
        e=self.engine;s=e.state
        own_cost=cost-(min(s.subsidy,cost) if kind in ('course','project','event') else 0)
        errors=list(missing or [])
        if s.slots>=4:errors.append('월 최대 4회 활동')
        if s.ap+ap>8:errors.append('월 8 AP')
        if s.cash+1e-8<own_cost:errors.append('자금 부족')
        if kind!='rest' and s.stress+max(0,stress)>100:errors.append('스트레스 상한')
        if self.ended:errors.append('지구 이동 완료')
        return {'kind':kind,'args':args,'label':label,'ap':ap,'cost':cost,
                'pay':round(own_cost,2),'stress':stress,'usable':not errors,'lock_reasons':errors,
                'score':round(score,2) if score is not None else None,'threshold':threshold,
                'description':description,'group':group or kind}

    def action_options(self,all_projects=False):
        e=self.engine;s=e.state
        if self.ended:return []
        opts=[]
        for f,counts in s.courses.items():
            for lv in range(3):
                max_count=(6,8,10)[lv]
                if counts[lv]>=max_count:continue
                allowed=(lv==0 or (lv==1 and e.age>=13 and counts[0]>=6) or
                         (lv==2 and e.age>=16 and counts[1]>=8))
                name=e.catalog['facility_names'].get(f,f)
                opts.append(self._action_entry('course',f'{name} · {STAGE_NAMES[lv]} ({counts[lv]}/{max_count})',
                    {'facility':f,'level':lv},COURSE_AP[lv],COURSE_COST[lv],(3,5,8)[lv],
                    [] if allowed else ['선행 이수 또는 연령 제한'],group='education'))
        for k in STATS:
            opts.append(self._action_entry('study',f'{STAT_NAMES[k]} 집중 훈련',{'stat':k},2,0,3,
                [f'현재 연령·전문화 상한 {e.cap(k)}'] if s.stats[k]>=e.cap(k)-1e-8 else [],group='training'))
        for key,label in HOBBY_NAMES.items():
            opts.append(self._action_entry('hobby',label,{'hobby':key},2,0,3,
                ['14세부터 가능'] if key=='romance' and e.age<14 else [],group='hobby'))
        for nid,npc in e.npc_defs.items():
            for style,label in BOND_NAMES.items():
                ap,cost,stress=e.SOCIAL_COSTS[style]
                opts.append(self._action_entry('bond',f'{npc["name"]} · {label}',{'npc':nid,'style':style},ap,cost,stress,
                    ['같은 NPC 월 2회 제한'] if e.bond_count.get(nid,0)>=2 else [],group='relationship',description=npc.get('interest','')))
        for life in e.available_life_events():
            for choice in life['options']:
                opts.append(self._action_entry('life',f'{life["title"]} · {choice["text"]}',
                    {'id':life['id'],'choice':choice['id']},choice['ap'],choice['cost'],
                    max(0,choice['effects'].get('stress',0)),group='life',description=life['description']))
        related=self._core_related()
        for kind,candidates in [('event',e.events),('project',e.projects)]:
            for item in candidates.values():
                if not all_projects and item['id'] not in related:continue
                if item['id'] in (s.completed_events if kind=='event' else s.project_scores):continue
                if item['id'] in s.failed_once and not item.get('retryable',False):continue
                missing=[format_missing(x) for x in e.missing(item)]
                if not all_projects and item['min_age']>e.age+3:continue
                score=(e.event_score(item) if kind=='event' else e.project_score(item)) if not any(x[0]=='project' for x in e.missing(item)) else None
                stress=5 if kind=='event' else {'P1':5,'P2':9,'P3':12,'M':15}[item['grade']]
                opts.append(self._action_entry(kind,item['name'],{'id':item['id']},item['ap'],item['cost'],stress,
                    missing,score,item['success_threshold'],description=item['id'],group='career'))
        for kind,label,ap,stress in [('ear','지구 정착 준비',1,1),('rest','휴식',1,-23),('work','아르바이트 (+115 G)',2,7)]:
            opts.append(self._action_entry(kind,label,{},ap,0,stress,group='daily'))
        return opts

    def recommend(self):
        """One transparent, *optional* action suggestion; never executes itself.

        Advisor uses the existing v1.1 goal planner. Recommendations are filtered
        against the actual live-session available-actions list so no free action
        or invalid v1.1 action is offered.
        """
        if self.ended:return None
        e=self.engine;s=e.state
        if e.age>=16 and len(s.specializations)<2:
            required=self.focus_ending['mandatory'].get('stats',{})
            # Prefer only traits which truly exceed the ordinary cap.
            spec=[k for k,v in required.items() if v>75 and k not in s.specializations]
            if spec:
                k=max(spec,key=required.get)
                return {'kind':'specialize','args':{'stat':k},'label':f'{STAT_NAMES[k]} 전문화 설정',
                        'reason':'75를 넘는 능력치 조건을 충족하려면 전문화가 필요합니다.'}
        from mgl_v11_simulator import SocialPlanner
        planner=SocialPlanner(e,self.focus_ending,seed=self.seed+s.month*101+s.slots,
                              mode='special' if self.focus_ending['type']=='special' else 'focused')
        suggestion=planner.choice()
        available={(x['kind'],json.dumps(x['args'],sort_keys=True)):x for x in self.action_options() if x['usable']}
        def match(a):
            if a is None:return None
            return available.get((a['kind'],json.dumps(a['args'],sort_keys=True)))
        candidate=match(suggestion)
        # v1.8: goal-aware fallback instead of unconditional rest/EAR/work.
        if candidate is None:
            req=self.focus_ending['mandatory']
            deficits={k:max(0,v-s.stats[k]) for k,v in req.get('stats',{}).items()}
            required_projects=set(req.get('projects',[]))-set(s.project_scores)
            required_events=set(req.get('events',[]))-set(s.completed_events)
            def score(x):
                kind=x['kind'];args=x['args'];points=0.0
                if kind=='rest':points=90 if s.stress>=65 else (15 if s.stress>=45 else -30)
                elif kind=='ear':points=75 if s.ear<req.get('ear_min',0) else -10
                elif kind=='work':points=80 if s.cash<200 else (20 if s.cash<500 else -20)
                elif kind=='study':points=65+max(deficits.values(),default=0)*0.3
                elif kind=='course':points=85
                elif kind=='project':points=105 if args.get('id') in required_projects else 30
                elif kind=='event':points=110 if args.get('id') in required_events else 35
                elif kind=='life':points=45
                elif kind=='bond':points=40 if req.get('relation_min',0)>s.relation else 20
                else:points=25
                return (points,-x['ap'],x['label'])
            if available:candidate=max(available.values(),key=score)
        if candidate is None:return None
        kind=candidate['kind']
        reason=({'course':'목표 직업의 선행 교육 과정을 먼저 진행합니다.',
                 'project':'완료 가능한 목표 프로젝트를 진행합니다.',
                 'event':'진로 진행에 필요한 이벤트를 수행합니다.',
                 'study':'필수 능력치의 부족분을 메웁니다.',
                 'life':'진로와 성장에 도움이 될 수 있는 생활 선택입니다.',
                 'bond':'NPC와의 장기적인 신뢰 관계를 유지합니다.',
                 'ear':'지구 이동 이후의 독립을 준비합니다.',
                 'rest':'스트레스 또는 행동력 제약을 고려한 휴식입니다.',
                 'work':'경제적인 부담을 낮추기 위한 활동입니다.'}).get(kind,'균형 잡힌 육성을 위한 추천입니다.')
        return {'kind':kind,'args':candidate['args'],'label':candidate['label'],
                'reason':reason,'ap':candidate['ap'],'pay':candidate['pay']}

    def _warnings(self):
        s=self.engine.state;age=self.engine.age
        warnings=[]
        if s.stress>=65:warnings.append('스트레스가 높습니다. 성장 효율이 떨어지므로 휴식이 필요할 수 있습니다.')
        if s.cash<200:warnings.append('가정 자금이 200 G 미만입니다. 고액 프로젝트 진행 전에 예산을 확인하세요.')
        if age>=16 and s.ear<35:warnings.append('지구 적응 준비도가 낮습니다. 미래의 독립 생활을 준비하세요.')
        if age==19:warnings.append('20세가 되면 지구로 반드시 이동합니다. 남은 준비 기간을 고려하세요.')
        # Time-limited social flags. Only warn when a required goal flag is not already earned.
        for needed in self.focus_ending.get('social_mandatory',{}).get('flags',[]):
            if needed in self.engine.life_flags:continue
            windows=[]
            for ev in self.engine.life_defs.values():
                if any(needed in o['effects'].get('flags',[]) or needed in o.get('on_success',{}).get('flags',[])
                       for o in ev['options']): windows.append((ev['age_min'],ev['age_max'],ev['title']))
            for amin,amax,title in windows:
                if age>amax:warnings.append(f'필수 생활 선택 「{title}」의 시기를 놓쳤습니다.')
                elif age>=amin:warnings.append(f'필수 생활 선택 「{title}」을(를) 놓치지 마세요. ({amax}세까지)')
        return list(dict.fromkeys(warnings))

    def _progress(self):
        e=self.engine;s=e.state;target=self.focus_ending
        missing=e.ending_missing(target)
        return {'id':target['id'],'name':target['name'],'grade':target['grade'],
                'type':target['type'],'ready':not missing,
                'missing':[format_missing(x) for x in missing],
                'completed_projects':list(s.project_scores),
                'required_projects':target['mandatory'].get('projects',[]),
                'required_events':target['mandatory'].get('events',[])}

    def view(self):
        e=self.engine;s=e.state
        action_log=[x for x in s.log if x.get('month')==s.month and x.get('action')!='SPECIALIZE']
        final=e.resolve_endings() if self.ended else None
        return {'schema_version':'1.2','seed':self.seed,'economy':self.economy,
            'month_index':s.month,'calendar_month':s.month%12+1,
            'age':20 if self.ended else e.age,'season':SEASONS[s.month%12],
            'completed':self.ended,'ap_used':s.ap,'ap_left':8-s.ap,'slots_used':s.slots,'slots_left':4-s.slots,
            'cash':round(s.cash,2),'subsidy_left':round(s.subsidy,2),'stress':round(s.stress,2),
            'happiness':round(s.happiness,2),'ear':round(s.ear,2),'trust':round(s.trust,2),
            'autonomy':round(s.autonomy,2),'confidence':round(s.confidence,2),
            'relation':round(s.relation,2),'separation':round(s.separation,2),
            'stats':{k:{'name':STAT_NAMES[k],'value':round(v,2),'cap':e.cap(k)} for k,v in s.stats.items()},
            'specializations':list(s.specializations),
            'courses':{k:list(v) for k,v in s.courses.items()},
            'npcs':[{'id':k,'name':e.npc_defs[k]['name'],'interest':e.npc_defs[k]['interest'],
                     'affinity':round(v.affinity,2),'trust':round(v.trust,2),'intimacy':round(v.intimacy,2),
                     'conflict':round(v.conflict,2)} for k,v in e.npcs.items()],
            'life_flags':sorted(e.life_flags),'project_count':len(s.project_scores),
            'career_event_count':len(s.completed_events),'recent_month_actions':action_log,
            'last_month':self.last_month,'year_reports':self.reports,
            'focus':self._progress(),'warnings':self._warnings(),'final':final,
            'recommendation':self.recommend(),
            'endings':[{'id':x['id'],'name':x['name'],'grade':x['grade'],'type':x['type']} for x in e.endings],
            'transfer_count':s.earth_transfer_count,'invalid_attempt_count':len(s.invalid_attempts)}

    def save_payload(self):
        e=self.engine
        return {'save_schema':SAVE_VERSION,'seed':self.seed,'economy':self.economy,'focus':self.focus,
                'state':encode(vars(e.state)),'npcs':{k:encode(vars(v)) for k,v in e.npcs.items()},
                'life_complete':encode(e.life_complete),'life_flags':encode(e.life_flags),
                'bond_count':encode(e.bond_count),'life_actions':e.life_actions,'npc_actions':e.npc_actions,
                'life_issues':encode(e.life_issues),'rng_state':encode(e.rng.getstate()),
                'reports':encode(self.reports),'year_baseline':encode(self.year_baseline),
                'last_month':encode(self.last_month)}

    @classmethod
    def from_payload(cls,data):
        if data.get('save_schema')!=SAVE_VERSION:raise ValueError('지원하지 않는 저장 파일 버전')
        obj=cls(seed=data['seed'],economy=data['economy'],focus=data['focus'])
        state_values=decode(data['state'])
        legal={f.name for f in fields(State)}
        if set(state_values)!=legal:raise ValueError('저장 파일 State 구조 불일치')
        obj.engine.state=State(**state_values)
        if not 0<=obj.engine.state.month<120:raise ValueError('저장 파일 월 범위 오류')
        if obj.engine.state.left_astellia and obj.engine.state.earth_transfer_count!=1:
            raise ValueError('차원 이동 무결성 오류')
        if not obj.engine.state.left_astellia and obj.engine.state.earth_transfer_count:
            raise ValueError('차원 이동 상태 오류')
        if set(data['npcs'])!=set(obj.engine.npcs):raise ValueError('NPC 구조 불일치')
        obj.engine.npcs={k:NPCBond(**decode(v)) for k,v in data['npcs'].items()}
        obj.engine.life_complete=decode(data['life_complete'])
        obj.engine.life_flags=decode(data['life_flags'])
        obj.engine.bond_count=decode(data['bond_count'])
        obj.engine.life_actions=data['life_actions'];obj.engine.npc_actions=data['npc_actions']
        obj.engine.life_issues=decode(data['life_issues'])
        obj.engine.rng.setstate(decode(data['rng_state']))
        obj.reports=decode(data['reports']);obj.year_baseline=decode(data['year_baseline'])
        obj.last_month=decode(data['last_month'])
        obj.engine.state.chosen_focus=obj.focus
        return obj

    def save(self,path):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(path.suffix+'.tmp')
        tmp.write_text(json.dumps(self.save_payload(),ensure_ascii=False,indent=2),encoding='utf-8')
        tmp.replace(path)
        return path

    @classmethod
    def load(cls,path):
        return cls.from_payload(json.loads(Path(path).read_text(encoding='utf-8')))


if __name__=='__main__':
    e=PlaySession();print(json.dumps({'age':e.view()['age'],'actions':len(e.action_options()),'focus':e.focus},ensure_ascii=False))
