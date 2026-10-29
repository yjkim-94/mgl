"""Player-facing v1.3 extension of the lossless v1.2 save/session format."""
from __future__ import annotations
from mgl_play_session import PlaySession,load_data,ROOT,STAT_NAMES,format_missing
from mgl_story_engine import MGL13Engine

HINT_MODES=('off','light','detailed')

class PlaySession13(PlaySession):
    def __init__(self,seed=20261029,economy='standard',focus='J01',hint_mode='detailed'):
        super().__init__(seed,economy,focus)
        catalog,endings=load_data(ROOT)
        self.engine=MGL13Engine(catalog,endings,seed=int(seed),economy=economy)
        self.engine.state.chosen_focus=focus
        self.engine.start_month(0)
        self.year_baseline=self._baseline()
        self.hint_mode=self._valid_hint(hint_mode)

    @staticmethod
    def _valid_hint(mode):
        if mode not in HINT_MODES:raise ValueError('힌트 모드는 off/light/detailed 중 하나여야 합니다.')
        return mode

    def set_hint_mode(self,mode):
        self.hint_mode=self._valid_hint(mode)
        return self.hint_mode

    def action_options(self,all_projects=False):
        actions=super().action_options(all_projects)
        for a in actions:
            if a['kind']=='life' and a['args']['id'] in self.engine.story_ids:
                ev=self.engine.story_nodes[a['args']['id']]
                a['group']='story'
                a['description']=ev['story']['opening']
                a['story_scene']={'chapter':ev['story']['chapter'],
                                  'npc':ev['npc'],'route':ev['story']['route']}
        return actions

    def act(self,kind,kwargs=None):
        kwargs=kwargs or {}
        event=self.engine.story_nodes.get(kwargs.get('id')) if kind=='life' else None
        result=super().act(kind,kwargs)
        if event and result['ok']:
            choice=next(x for x in event['options'] if x['id']==kwargs['choice'])
            finale=event['story']['outcome']
            outcome=finale.get(event['story']['route']) if finale else None
            result['story_result']={'npc':self.engine.npc_defs[event['npc']]['name'],
                                    'chapter':event['story']['chapter'],
                                    'title':event['title'],
                                    'opening':event['story']['opening'],
                                    'choice':choice['text'],
                                    'aftermath':outcome or '함께 내린 선택이 앞으로의 인연에 새로운 흔적을 남겼다.',
                                    'branch':event['story']['route']}
        return result

    def career_roadmap(self):
        """Explainable milestone/priority UI; no secret scores or automatic changes."""
        e=self.engine;s=e.state;req=self.focus_ending['mandatory']
        entries=[]
        for stat,need in req.get('stats',{}).items():
            cur=s.stats[stat]
            if cur+1e-8>=need:continue
            specialized=stat in s.specializations
            if need>75 and not specialized:
                msg=('16세 이후 전문화 슬롯에 등록해야 상한을 넘어 성장할 수 있습니다.'
                     if e.age<16 else '지금 전문화 슬롯을 배정해야 합니다.')
            else:msg='교육과 집중 훈련으로 성장시킬 수 있습니다.'
            entries.append({'kind':'stat','name':STAT_NAMES.get(stat,stat),'current':round(cur,2),
                            'required':need,'gap':round(need-cur,2),'note':msg,
                            'priority':'긴급' if e.age>=18 and need-cur>=6 else '계획'})
        outstanding=[p for p in req.get('projects',[]) if p not in s.project_scores]
        for item in outstanding:
            node=e.projects.get(item)
            if node:
                missing=e.missing(node)
                entries.append({'kind':'project','name':node['name'],
                      'current':False,'required':True,'gap':len(missing),
                      'note':' · '.join(format_missing(v) for v in missing[:3]) if missing else '선행 조건 완료: 성공 가능 점수 확인',
                      'priority':'긴급' if e.age>=18 else '계획'})
        for item in req.get('events',[]):
            if item not in s.completed_events:
                node=e.events.get(item)
                if node:entries.append({'kind':'event','name':node['name'], 'current':False,'required':True,
                    'gap':len(e.missing(node)),
                    'note':' · '.join(format_missing(v) for v in e.missing(node)[:3]) or '진로 이벤트 실행 가능',
                    'priority':'긴급' if e.age>=18 else '계획'})
        for flag in self.focus_ending.get('social_mandatory',{}).get('flags',[]):
            if flag in e.life_flags:continue
            producers=[v for v in e.life_defs.values()
                       if any(flag in o['effects'].get('flags',[]) or flag in o.get('on_success',{}).get('flags',[])
                              for o in v['options'])]
            if producers:
                event=min(producers,key=lambda v:v['age_max'])
                deadline=event['age_max']
                priority='기한 지남' if e.age>deadline else '긴급' if e.age>=deadline else '계획'
                entries.append({'kind':'life','name':event['title'],'gap':1,
                                'current':False,'required':True,
                                'note':f'{deadline}세까지 가능한 생활 선택입니다. 필요한 선택지를 확인하세요.',
                                'priority':priority})
        for missing in e.education_missing(req.get('education',[])):
            entries.append({'kind':'education','name':'교육 과정', 'current':False,'required':True,
                            'gap':missing[-1] if isinstance(missing[-1],int) else 1,
                            'note':format_missing(missing), 'priority':'긴급' if e.age>=17 else '계획'})
        for hobby,need in req.get('counters',{}).items():
            current=s.counters.get(hobby,0)
            if current<need:
                entries.append({'kind':'hobby','name':f'{hobby} 누적 활동','current':current,
                                'required':need,'gap':need-current,
                                'note':f'{need-current}회 추가 활동이 필요합니다. 생활·관계와 행동력을 나누어 사용하세요.',
                                'priority':'긴급' if e.age>=18 else '계획'})
        for axis,need in req.get('value_min',{}).items():
            current=s.values.get(axis,0)
            if current+1e-8<need:
                entries.append({'kind':'value','name':f'{axis} 가치관','current':round(current,2),
                                'required':need,'gap':round(need-current,2),
                                'note':'생활 이벤트와 취미의 누적 선택으로 형성됩니다.',
                                'priority':'긴급' if e.age>=18 else '계획'})
        for key,label in (('relation_min','인간관계'),('autonomy_min','자율성'),('ear_min','지구 적응 준비')):
            current={'relation_min':s.relation,'autonomy_min':s.autonomy,'ear_min':s.ear}[key]
            need=req.get(key,0)
            if current+1e-8<need:
                entries.append({'kind':'ear' if key=='ear_min' else 'relation','name':label,
                                'current':round(current,2),'required':need,
                                'gap':round(need-current,2),
                                'note':'지구 생활 적응을 준비합니다.' if key=='ear_min' else '관계·생활 활동에서 관련 경험을 쌓습니다.',
                                'priority':'긴급' if e.age>=19 else '계획'})
        bond_goal=self.focus_ending.get('social_mandatory',{}).get('strong_bonds',0)
        current_bonds=len(e.strong_bonds())
        if current_bonds<bond_goal:
            entries.append({'kind':'relation','name':'오래가는 친구 관계',
                            'current':current_bonds,'required':bond_goal,'gap':bond_goal-current_bonds,
                            'note':'호감 60·신뢰 55 이상이고 갈등 25 이하인 NPC가 필요합니다.',
                            'priority':'긴급' if e.age>=18 else '계획'})
        total=len(entries)
        entries.sort(key=lambda a:({'기한 지남':0,'긴급':1,'계획':2}[a['priority']],
                                    {'life':0,'project':1,'event':2,'education':3,'stat':4,'hobby':5,'relation':6,'value':7,'ear':8}.get(a['kind'],9),
                                    -a['gap']))
        guide={'name':self.focus_ending['name'],'remaining_items':total,
               'status':'조건 충족' if not e.ending_missing(self.focus_ending) else ('이전 기한 미달' if any(x['priority']=='기한 지남' for x in entries) else '준비 중'),
               'milestones':entries[:12]}
        if self.hint_mode=='light':guide['milestones']=entries[:3]
        if self.hint_mode=='off':guide['milestones']=[]
        return guide

    def view(self):
        state=super().view()
        state['schema_version']='1.3'
        state['hint_mode']=self.hint_mode
        state['career_roadmap']=self.career_roadmap() if self.hint_mode!='off' else None
        if self.hint_mode=='off':state['recommendation']=None;state['warnings']=[]
        state['stories']=self.engine.story_snapshot()
        return state

    def save_payload(self):
        data=super().save_payload()
        data['hint_mode']=self.hint_mode
        return data

    @classmethod
    def from_payload(cls,data):
        obj=super().from_payload(data)
        obj.hint_mode=cls._valid_hint(data.get('hint_mode','detailed'))
        return obj
