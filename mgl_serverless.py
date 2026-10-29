"""Stateless game request dispatcher for Vercel. No shared sessions or disk writes."""
import re
from mgl_play_v13 import PlaySession13

SLOT_RE = re.compile(r'^[A-Za-z0-9_-]{1,30}$')
ALLOWED = {'course':{'facility','level'},'study':{'stat'},'rest':set(),'ear':set(),'work':set(),'hobby':{'hobby'},'project':{'id'},'event':{'id'},'bond':{'npc','style'},'life':{'id','choice'}}

def dispatch(op, data, payload=None):
    if not isinstance(data,dict): raise ValueError('요청 데이터는 객체여야 합니다.')
    if payload is not None and not isinstance(payload,dict):raise ValueError('잘못된 저장 데이터')
    s=PlaySession13.from_payload(payload) if payload is not None else PlaySession13()
    if op=='state': result=s.view()
    elif op=='actions': result={'actions':s.action_options(all_projects=data.get('all') is True)}
    elif op=='action':
        kind,args=data.get('kind'),data.get('args')
        if kind not in ALLOWED or not isinstance(args,dict) or set(args)!=ALLOWED[kind]:raise ValueError('지원하지 않는 행동 또는 매개변수')
        result=s.act(kind,args)
    elif op=='advance':result=s.next_month()
    elif op=='specialize':result=s.specialize(data.get('stat'))
    elif op=='hint':result={'hint_mode':s.set_hint_mode(data.get('mode'))}
    elif op=='focus':s.set_focus(data.get('focus'));result={'focus':s.focus}
    elif op=='new':
        seed=data.get('seed',20261029);economy=data.get('economy','standard');focus=data.get('focus','J01')
        if type(seed) is not int or not 0<=seed<=2147483647 or economy not in ('standard','strained','affluent'):raise ValueError('새 게임 설정 오류')
        s=PlaySession13(seed=seed,economy=economy,focus=focus);result={'started':True}
    else:raise ValueError('지원하지 않는 요청')
    return {'result':result,'state':s.view(),'snapshot':s.save_payload()}
