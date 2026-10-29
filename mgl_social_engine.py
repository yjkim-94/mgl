"""MGL v1.1 social/life layer atop the unmodified v1.0 engine.

All interactions happen during ages 10-19 in Astellia. They are age-appropriate,
nonsexual and do not allow club attendance. Earth transfer stays irreversible.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from pathlib import Path
import copy,json
from mgl_event_engine import GameEngine,STATS,clamp,validate_catalog
ROOT=Path(__file__).resolve().parent

@dataclass
class NPCBond:
    affinity:float=20.
    trust:float=20.
    intimacy:float=10.  # emotional closeness / friendship, not sexual
    conflict:float=0.
    last_seen:int=-1
    times:int=0
    months_together:int=0

class MGL11Engine(GameEngine):
    SOCIAL_COSTS={'listen':(1,0,1),'collaborate':(2,10,4),'share':(2,0,2),'reconcile':(2,0,2)}
    def __init__(self,catalog=None,endings=None,seed=20261029,economy='standard',npcs=None,life_events=None):
        super().__init__(catalog,endings,seed=seed,economy=economy)
        self.seed=seed
        # Source of truth is the ending catalog, not hardcoded special-ending IDs.
        self.GATES={x['id']:x['social_mandatory'] for x in self.endings if x.get('social_mandatory')}
        if npcs is None:npcs=json.loads((ROOT/'mgl_npcs.json').read_text(encoding='utf8'))['npcs']
        if life_events is None:life_events=json.loads((ROOT/'mgl_life_events.json').read_text(encoding='utf8'))['events']
        self.npc_defs={n['id']:n for n in npcs}
        self.npcs={n['id']:NPCBond(**n['initial']) for n in npcs}
        self.life_defs={x['id']:x for x in life_events}
        self.life_complete=set() # (event ID, year / None)
        self.life_flags=set()
        self.bond_count={}
        self.life_actions=0
        self.npc_actions=0
        self.life_issues=[]

    def start_month(self,month):
        super().start_month(month)
        self.bond_count={}
        for bond in self.npcs.values():
            gap=month-bond.last_seen if bond.last_seen>=0 else month+1
            # Friendship can cool when neglected; it cannot drop below its starting floor.
            if gap>6:
                bond.affinity=clamp(bond.affinity-.42,15,100)
                bond.trust=clamp(bond.trust-.24,15,100)
                bond.intimacy=clamp(bond.intimacy-.32,0,100)
            bond.conflict=clamp(bond.conflict-.1)

    def _complete_key(self,ev):
        return (ev['id'],self.age if ev['frequency']=='yearly' else None)

    def _eligible_life(self,ev):
        if not ev['age_min']<=self.age<=ev['age_max']:return False
        if self.state.month % 12 not in ev['months']:return False
        if self._complete_key(ev) in self.life_complete:return False
        r=ev.get('requires',{})
        if any(k not in self.life_flags for k in r.get('flags',[])):return False
        if ev['npc'] is not None:
            n=self.npcs[ev['npc']]
            if n.affinity+1e-8<r.get('npc_affinity',0) or n.trust+1e-8<r.get('npc_trust',0):return False
        return True

    def available_life_events(self,limit=3):
        if self.state.month<0 or self.state.left_astellia:return []
        items=[e for e in self.life_defs.values() if self._eligible_life(e)]
        # Milestone > character arc > seasonal. Deterministic; no invisible re-roll.
        items.sort(key=lambda x:(-x['priority'],x['id']))
        return items[:limit] if limit else items

    def _resource_check(self,ap,cost,stress_delta):
        s=self.state
        if s.month<0 or s.left_astellia:return 'invalid_date'
        if s.slots>=4:return 'slot_limit'
        if s.ap+ap>8:return 'ap_limit'
        if s.cash+1e-8<cost:return 'cash'
        if s.stress+max(0,stress_delta)>100:return 'stress_cap'
        return None

    def _spend(self,ap,cost,stress_delta):
        s=self.state;s.ap+=ap;s.slots+=1;s.cash-=cost;s.spent+=cost
        s.stress=clamp(s.stress+stress_delta);s.max_stress=max(s.max_stress,s.stress)

    def _npc_update(self,nid,effect):
        if nid not in self.npcs:raise ValueError('unknown NPC')
        n=self.npcs[nid]
        for k,v in effect.items():
            if k not in ('affinity','trust','intimacy','conflict'):raise ValueError('unknown NPC metric')
            setattr(n,k,clamp(getattr(n,k)+v))
        if n.last_seen!=self.state.month:n.months_together+=1
        n.last_seen=self.state.month;n.times+=1

    def _apply_effects(self,effects,nid=None):
        s=self.state
        for key in ('happiness','trust','autonomy','confidence','separation','ear','relation','stress'):
            if key in effects:
                attr='relation' if key=='relation' else key
                setattr(s,attr,clamp(getattr(s,attr)+effects[key]))
        s.max_stress=max(s.max_stress,s.stress)
        for k,v in effects.get('values',{}).items():
            if k not in s.values:raise ValueError('unknown value')
            s.values[k]=clamp(s.values[k]+v)
        for k,v in effects.get('stat_growth',{}).items():
            if k not in STATS:raise ValueError('unknown stat')
            self._gain(k,v)
        self.life_flags.update(effects.get('flags',[]))
        if nid and effects.get('npc'):self._npc_update(nid,effects['npc'])

    def act(self,kind,**kwargs):
        if kind=='bond':return self.bond(kwargs.get('npc'),kwargs.get('style','listen'))
        if kind=='life':return self.life_choice(kwargs.get('id'),kwargs.get('choice'))
        return super().act(kind,**kwargs)

    def bond(self,nid,style):
        s=self.state
        if nid not in self.npcs or style not in self.SOCIAL_COSTS:
            s.invalid_attempts.append({'month':s.month,'kind':'bond','error':'unknown_npc_or_style'});return False,'unknown_npc_or_style'
        if self.bond_count.get(nid,0)>=2:
            s.invalid_attempts.append({'month':s.month,'kind':'bond','error':'npc_monthly_limit'});return False,'npc_monthly_limit'
        ap,cost,pressure=self.SOCIAL_COSTS[style]
        err=self._resource_check(ap,cost,pressure)
        if err:s.invalid_attempts.append({'month':s.month,'kind':'bond','error':err});return False,err
        self._spend(ap,cost,pressure)
        n=self.npcs[nid]
        if style=='listen':effects={'affinity':3.5,'trust':6.2,'intimacy':1.5,'conflict':-2.5}
        elif style=='collaborate':effects={'affinity':6.5,'trust':4.3,'intimacy':2,'conflict':-1}
        elif style=='share':effects={'affinity':6,'trust':3,'intimacy':4,'conflict':-1}
        else:effects={'affinity':1,'trust':5,'intimacy':1,'conflict':-12}
        diminishing=.55 if self.bond_count.get(nid,0)==1 else 1.0
        for k in effects:effects[k]*=diminishing
        self._npc_update(nid,effects)
        s.relation=clamp(s.relation+1.1*diminishing)
        s.happiness=clamp(s.happiness+.8)
        s.values['empathy']=clamp(s.values['empathy']+.6*diminishing)
        self.bond_count[nid]=self.bond_count.get(nid,0)+1
        self.npc_actions+=1
        s.log.append({'month':s.month,'age':self.age,'action':'bond','npc':nid,'style':style,'success':True,
                      'ap':ap,'cost':cost,'own_cost':cost,'stress':round(s.stress,2)})
        return True,'success'

    def life_choice(self,event_id,choice_id):
        s=self.state
        choices={x['id']:x for x in self.available_life_events(limit=3)}
        ev=choices.get(event_id)
        if not ev:
            s.invalid_attempts.append({'month':s.month,'kind':'life','id':event_id,'error':'event_not_offered'});return False,'event_not_offered'
        option=next((x for x in ev['options'] if x['id']==choice_id),None)
        if option is None:
            s.invalid_attempts.append({'month':s.month,'kind':'life','id':event_id,'error':'choice_unknown'});return False,'choice_unknown'
        ap,cost=option['ap'],option['cost'];pressure=option['effects'].get('stress',0)
        err=self._resource_check(ap,cost,pressure)
        if err:s.invalid_attempts.append({'month':s.month,'kind':'life','id':event_id,'error':err});return False,err
        self._spend(ap,cost,0) # option stress applied only once, in effects
        self._apply_effects(option['effects'],ev['npc'])
        passed=None
        if 'check' in option:
            test=option['check'];stat=test['stat'];n=self.npcs.get(ev['npc'])
            score=s.stats[stat]+(.10*n.trust if n else 0)-.10*s.stress
            passed=score+1e-8>=test['target']
            self._apply_effects(option['on_success'] if passed else option['on_failure'],ev['npc'])
        self.life_complete.add(self._complete_key(ev));self.life_actions+=1
        s.log.append({'month':s.month,'age':self.age,'action':'life','id':event_id,'choice':choice_id,
                      'success':True,'check_passed':passed,'ap':ap,'cost':cost,'own_cost':cost,'stress':round(s.stress,2)})
        return True,'success'

    def strong_bonds(self):
        return [nid for nid,b in self.npcs.items() if b.affinity>=60-1e-8 and b.trust>=55-1e-8 and b.conflict<=25]

    def ending_missing(self,ending):
        missing=super().ending_missing(ending)
        req=self.GATES.get(ending['id'],{})
        n=req.get('strong_bonds',0)
        if len(self.strong_bonds())<n:missing.append(('npc_strong_bonds',n-len(self.strong_bonds())))
        for flag in req.get('flags',[]):
            if flag not in self.life_flags:missing.append(('life_flag',flag))
        return missing

    def resolve_endings(self):
        result=super().resolve_endings()
        if not self.state.left_astellia:return result
        top=sorted(self.npcs.items(),key=lambda x:(x[1].trust+x[1].affinity,-x[1].conflict),reverse=True)
        best=top[0] if top else None
        result['social_epilogue']={
            'earth_transfer':'mandatory_at_age_20',
            'friendship_memory':self.npc_defs[best[0]]['name'] if best and best[1].affinity>=55 else None,
            'lasting_bonds':len(self.strong_bonds()),
            'respectful_dialogue':'respectful_dialogue' in self.life_flags,
            'farewell_prepared':bool(self.life_flags & {'farewell_memory','farewell_plan'}),
            'future_note':'아스텔리아의 친구들은 지구로 함께 이동하지 않는다. 기억과 배운 태도가 지구 성인기의 인간관계에 영향을 준다.'
        }
        return result

    def social_snapshot(self):
        return {'npcs':{k:vars(v).copy() for k,v in self.npcs.items()},
                'life_complete':[list(x) for x in sorted(self.life_complete,key=str)],
                'life_flags':sorted(self.life_flags),'life_actions':self.life_actions,'npc_actions':self.npc_actions,
                'strong_bonds':self.strong_bonds()}


def validate_social_catalog(npcs, life_events, endings=None):
    """Static syntax, flag-DAG, and time-window feasibility checks.

    The fixed-point analysis is intentionally optimistic about NPC stats/skill checks.
    Dynamic witness tests supply concrete action paths; the static test alone does
    not prove that every optional effect is obtainable.
    """
    errors = []
    npc_ids = [x['id'] for x in npcs]
    ids = [x['id'] for x in life_events]
    if len(set(ids)) != len(ids): errors.append('duplicate life ID')
    if len(set(npc_ids)) != len(npc_ids): errors.append('duplicate NPC ID')
    earliest_flags = {}
    flag_producers = {}
    for e in life_events:
        eid = e['id']
        if not 10 <= e['age_min'] <= e['age_max'] <= 19: errors.append(f'{eid}: age window')
        if not e['months'] or any(not 0 <= v <= 11 for v in e['months']): errors.append(f'{eid}: months')
        if e['npc'] is not None and e['npc'] not in npc_ids: errors.append(f'{eid}: unknown NPC')
        if e['frequency'] not in ('yearly', 'lifetime'): errors.append(f'{eid}: recurrence')
        if len(e['options']) < 2: errors.append(f'{eid}: insufficient options')
        if len({x['id'] for x in e['options']}) != len(e['options']): errors.append(f'{eid}: duplicate option')
        req = e.get('requires', {})
        if any(not 0 <= req.get(k, 0) <= 100 for k in ('npc_affinity', 'npc_trust')):
            errors.append(f'{eid}: impossible NPC threshold')
        for opt in e['options']:
            if opt['ap'] not in (1, 2, 3, 4) or opt['cost'] < 0: errors.append(f'{eid}: bad resources')
            for d in (opt['effects'], opt.get('on_success', {}), opt.get('on_failure', {})):
                for f in d.get('flags', []):
                    flag_producers.setdefault(f, set()).add(eid)
                if any(k not in STATS for k in d.get('stat_growth', {})): errors.append(f'{eid}: bad stat')
                if any(k not in ('affinity', 'trust', 'intimacy', 'conflict') for k in d.get('npc', {})):
                    errors.append(f'{eid}: bad NPC delta')
                if 'npc' in d and e['npc'] is None: errors.append(f'{eid}: npc effect without NPC')
            if 'check' in opt and (opt['check']['stat'] not in STATS or not 0 <= opt['check']['target'] <= 100):
                errors.append(f'{eid}: check')
    # Flag requirements must have a producer and be possible in chronological order.
    for e in life_events:
        for f in e.get('requires', {}).get('flags', []):
            if f not in flag_producers: errors.append(f'{e["id"]}: impossible prerequisite flag {f}')

    # A flag granted by an event cannot precede that event's earliest legal month.
    # Events can share a month, so same-month dependencies are permitted and
    # are later subject to AP/slot accounting in the dynamic coverage test.
    earliest_events = {}
    for _ in range(len(life_events) + 1):
        changed = False
        for e in life_events:
            req = e.get('requires', {}).get('flags', [])
            if not all(f in earliest_flags for f in req): continue
            earliest = max([(e['age_min'] - 10) * 12] + [earliest_flags[f] for f in req])
            eligible_months = [m for m in range(earliest, min(120, (e['age_max'] - 9) * 12))
                               if m % 12 in e['months']]
            if not eligible_months: continue
            month = eligible_months[0]
            if e['id'] not in earliest_events or month < earliest_events[e['id']]:
                earliest_events[e['id']] = month
                changed = True
            for option in e['options']:
                for effects in (option['effects'], option.get('on_success', {}), option.get('on_failure', {})):
                    for flag in effects.get('flags', []):
                        if flag not in earliest_flags or month < earliest_flags[flag]:
                            earliest_flags[flag] = month
                            changed = True
        if not changed: break
    for e in life_events:
        if e['id'] not in earliest_events:
            errors.append(f'{e["id"]}: unresolvable flag dependency or age window (possible cycle)')
    for ending in endings or []:
        req = ending.get('social_mandatory', {})
        if not isinstance(req.get('strong_bonds', 0), int) or not 0 <= req.get('strong_bonds', 0) <= len(npcs):
            errors.append(f'{ending["id"]}: impossible number of strong bonds')
        for f in req.get('flags', []):
            if f not in earliest_flags: errors.append(f'{ending["id"]}: impossible social flag {f}')
    return {'ok': not errors, 'errors': errors, 'npc_count': len(npcs),
            'life_event_count': len(life_events),
            'choice_count': sum(len(e['options']) for e in life_events),
            'chronologically_reachable_event_definitions': len(earliest_events)}
