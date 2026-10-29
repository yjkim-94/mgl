"""MGL v1.3 authored branching stories. No independent AP/stat economy.

Story chapters are ordinary v1.1 life-event actions using the exact existing
resource/eligibility engine. Branch flags are in the existing life_flags and
therefore survive saves and share the same immutable 20-year transfer rule.
"""
from __future__ import annotations
import json
from pathlib import Path
from mgl_social_engine import MGL11Engine,validate_social_catalog

ROOT=Path(__file__).resolve().parent

class MGL13Engine(MGL11Engine):
    def __init__(self,catalog=None,endings=None,seed=20261029,economy='standard'):
        original=json.loads((ROOT/'mgl_life_events.json').read_text(encoding='utf8'))['events']
        story=json.loads((ROOT/'mgl_story_arcs.json').read_text(encoding='utf8'))['events']
        super().__init__(catalog,endings,seed=seed,economy=economy,life_events=original+story)
        self.story_ids={e['id'] for e in story}
        self.story_nodes={e['id']:e for e in story}

    def available_life_events(self,limit=3):
        """Preserve all original top-three offers; separately surface story arcs.

        Priority is bounded per category, rather than allowing a new narrative
        node to hide required v1.1 milestone/ending events.
        """
        if self.state.month<0 or self.state.left_astellia:return []
        ordinary=[e for e in self.life_defs.values()
                  if e['id'] not in self.story_ids and self._eligible_life(e)]
        story=[e for e in self.story_nodes.values() if self._eligible_life(e)]
        ordinary.sort(key=lambda e:(-e['priority'],e['id']))
        story.sort(key=lambda e:(e['npc'],-e['story']['chapter'],e['id']))
        if not limit:return ordinary+story
        # Original events stay at three; at most one chapter per NPC is offered.
        per_npc={}
        for node in story:per_npc.setdefault(node['npc'],node)
        return ordinary[:limit]+list(per_npc.values())

    def story_snapshot(self):
        results=[]
        for nid,meta in self.npc_defs.items():
            flags=self.life_flags
            route=('a' if f'story_{nid}_a1' in flags else 'b' if f'story_{nid}_b1' in flags else None)
            chapter=0
            if route:
                chapter=1
                if f'story_{nid}_{route}2' in flags:chapter=2
                if f'story_{nid}_{route}_finished' in flags:chapter=3
            route_name={'a':'협력의 길','b':'자립의 길'}.get(route,'아직 선택하지 않음')
            offered=[e for e in self.available_life_events() if e['id'] in self.story_ids and e['npc']==nid]
            results.append({'npc':nid,'name':meta['name'],
                            'theme':next(e['story']['theme'] for e in self.story_nodes.values() if e['npc']==nid),
                            'chapter':chapter,'branch':route,'branch_name':route_name,
                            'done':chapter==3,
                            'next_scene':offered[0]['id'] if offered else None,
                            'outcome':self._outcome(nid,route) if chapter==3 else None})
        return results

    def _outcome(self,nid,route):
        if not route:return None
        final=self.story_nodes[f'ST_{nid.upper()}_3_{route.upper()}']
        return final['story']['outcome'][route]


def validate_story_data(root=ROOT):
    root=Path(root)
    npc=json.loads((root/'mgl_npcs.json').read_text(encoding='utf8'))['npcs']
    originals=json.loads((root/'mgl_life_events.json').read_text(encoding='utf8'))['events']
    stories=json.loads((root/'mgl_story_arcs.json').read_text(encoding='utf8'))['events']
    errors=list(validate_social_catalog(npc,originals+stories)['errors'])
    if len(stories)!=30:errors.append('expected 30 story nodes')
    for n in npc:
        nid=n['id'];nodes=[x for x in stories if x['npc']==nid]
        if len(nodes)!=5:errors.append(f'{nid}: expected five branches')
        for route in ('a','b'):
            if not any(x['id']==f'ST_{nid.upper()}_3_{route.upper()}' for x in nodes):
                errors.append(f'{nid}/{route}: missing resolution')
    return errors
