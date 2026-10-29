"""MGL v1.3 local web UI/API server (Python stdlib, no Internet dependency).

Run: python mgl_web.py --port 8765
Only listens on 127.0.0.1 by default, with fixed save slots and no arbitrary file paths.
"""
from __future__ import annotations

from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit, parse_qs
import json
import mimetypes
import re
import webbrowser

from mgl_play_v13 import PlaySession13 as PlaySession
from mgl_play_session import ROOT

MAX_BODY=64*1024
SLOT_PATTERN=re.compile(r'^[a-zA-Z0-9_-]{1,30}$')


class GameServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self, address, save_dir=None, seed=20261029, economy='standard', focus='J01'):
        super().__init__(address, GameHandler)
        self.lock=RLock()
        self.save_dir=Path(save_dir) if save_dir else ROOT/'saves'
        self.save_dir.mkdir(parents=True,exist_ok=True)
        autosave=self.save_dir/'autosave.json'
        try:
            self.session=PlaySession.load(autosave) if autosave.exists() else PlaySession(seed,economy,focus)
        except (ValueError,KeyError,TypeError,FileNotFoundError, json.JSONDecodeError) as exc:
            print(f'[MGL] 자동 저장 복원 실패: {exc}. 새로운 게임을 시작합니다.')
            self.session=PlaySession(seed,economy,focus)
        self.autosave()

    def autosave(self):
        self.session.save(self.save_dir/'autosave.json')

    def slot_path(self,slot):
        if not isinstance(slot,str) or not SLOT_PATTERN.fullmatch(slot) or slot=='autosave':
            raise ValueError('저장 슬롯은 영문·숫자·밑줄·하이픈만 허용합니다. (최대 30자)')
        return self.save_dir/f'{slot}.json'


class GameHandler(BaseHTTPRequestHandler):
    server:GameServer
    def log_message(self,fmt,*args):
        return  # Quiet local UI

    def send_json(self,data,status=200):
        body=json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path=urlsplit(self.path).path
        if path in ('/','/index.html','/styles.css','/app.js'):
            name='index.html' if path=='/' else path[1:]
            file=ROOT/'web'/name
            if not file.is_file():return self.send_error(404)
            data=file.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type',mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers();self.wfile.write(data);return
        with self.server.lock:
            if path=='/api/state':return self.send_json(self.server.session.view())
            if path=='/api/actions':
                q=parse_qs(urlsplit(self.path).query)
                show=q.get('all',['0'])[0]=='1'
                return self.send_json({'actions':self.server.session.action_options(all_projects=show)})
            if path=='/api/slots':
                names=sorted(p.stem for p in self.server.save_dir.glob('*.json') if p.stem!='autosave')
                return self.send_json({'slots':names})
        return self.send_json({'error':'요청한 API를 찾을 수 없습니다.'},404)

    def do_POST(self):
        path=urlsplit(self.path).path
        size=self.headers.get('Content-Length')
        if size is None or not size.isdigit() or int(size)>MAX_BODY:
            return self.send_json({'error':'요청 본문이 너무 크거나 길이가 없습니다.'},413)
        try:
            params=json.loads(self.rfile.read(int(size)).decode('utf-8'))
            if not isinstance(params,dict):raise ValueError('객체 형식의 JSON을 전송해야 합니다.')
        except (json.JSONDecodeError, UnicodeDecodeError,ValueError) as exc:
            return self.send_json({'error':str(exc)},400)
        try:
            with self.server.lock:
                s=self.server.session
                if path=='/api/action':
                    kind=params.get('kind');args=params.get('args',{})
                    if not isinstance(kind,str) or not isinstance(args,dict):raise ValueError('잘못된 행동 요청')
                    # Explicit allowlist stops callers from passing arbitrary kwargs.
                    allowed={'course':{'facility','level'},'study':{'stat'},'rest':set(),
                             'ear':set(),'work':set(),'hobby':{'hobby'},'project':{'id'},
                             'event':{'id'},'bond':{'npc','style'},'life':{'id','choice'}}
                    if kind not in allowed or set(args)!=allowed[kind]:raise ValueError('지원하지 않는 행동 또는 매개변수')
                    result=s.act(kind,args);self.server.autosave()
                elif path=='/api/advance':
                    result=s.next_month();self.server.autosave()
                elif path=='/api/specialize':
                    result=s.specialize(params.get('stat'));self.server.autosave()
                elif path=='/api/hint':
                    result={'hint_mode':s.set_hint_mode(params.get('mode'))};self.server.autosave()
                elif path=='/api/focus':
                    s.set_focus(params.get('focus'));self.server.autosave();result={'focus':s.focus}
                elif path=='/api/save':
                    slot=params.get('slot','slot1');s.save(self.server.slot_path(slot));result={'saved_slot':slot}
                elif path=='/api/load':
                    slot=params.get('slot','slot1');self.server.session=PlaySession.load(self.server.slot_path(slot));
                    self.server.autosave();result={'loaded_slot':slot}
                elif path=='/api/new':
                    focus=params.get('focus','J01')
                    seed=params.get('seed',20261029)
                    economy=params.get('economy','standard')
                    if economy not in ('standard','strained','affluent'):raise ValueError('지원하지 않는 경제 난이도')
                    if not isinstance(seed,int) or isinstance(seed,bool) or not 0<=seed<=2147483647:raise ValueError('시드 범위 오류')
                    self.server.session=PlaySession(seed=seed,economy=economy,focus=focus)
                    self.server.autosave();result={'started':True}
                else:return self.send_json({'error':'요청한 API가 없습니다.'},404)
                return self.send_json({'result':result,'state':self.server.session.view()})
        except (ValueError,FileNotFoundError,KeyError,TypeError,OverflowError) as exc:
            return self.send_json({'error':str(exc)},400)


def main():
    p=ArgumentParser(description='MGL v1.3 월간 육성 브라우저 게임')
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--save-dir',type=Path,default=ROOT/'saves')
    p.add_argument('--no-browser',action='store_true')
    p.add_argument('--seed',type=int,default=20261029)
    p.add_argument('--economy',choices=['standard','strained','affluent'],default='standard')
    p.add_argument('--focus',default='J01')
    args=p.parse_args()
    server=GameServer(('127.0.0.1',args.port),args.save_dir,args.seed,args.economy,args.focus)
    url=f'http://127.0.0.1:{server.server_port}'
    print(f'MGL v1.3 로컬 게임: {url}  (종료: Ctrl+C)')
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
