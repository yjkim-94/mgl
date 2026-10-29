"""Real HTTP end-to-end regression (no browser dependency)."""
import json
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from mgl_web import GameServer

class WebFlow(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.server=GameServer(('127.0.0.1',0),save_dir=self.tmp.name)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def call(self,path,payload=None):
        data=None if payload is None else json.dumps(payload).encode()
        req=Request(f'http://127.0.0.1:{self.server.server_port}{path}',data=data,headers={'Content-Type':'application/json'} if data is not None else {})
        with urlopen(req,timeout=20) as res:return json.load(res)
    def test_120_month_http_flow_and_persistence(self):
        s=self.call('/api/state')
        self.assertEqual((s['month_index'],s['ap_left'],s['slots_left'],len(s['endings'])),(0,8,4,48))
        self.assertEqual(self.call('/api/actions')['actions'].__class__,list)
        self.call('/api/save',{'slot':'checkpoint'})
        self.call('/api/hint',{'mode':'off'})
        self.assertIsNone(self.call('/api/state')['recommendation'])
        self.call('/api/load',{'slot':'checkpoint'})
        self.assertNotEqual(self.call('/api/state')['hint_mode'],'off')
        for month in range(120):
            s=self.call('/api/state')
            self.assertEqual(s['month_index'],month)
            self.assertFalse(s['completed'])
            self.assertLessEqual(s['ap_used'],8)
            self.assertLessEqual(s['slots_used'],4)
            if month in (0,23,60,119):
                acts=self.call('/api/actions')['actions']
                usable=next((a for a in acts if a['usable'] and a['kind']=='rest'),None)
                if usable:
                    r=self.call('/api/action',{'kind':usable['kind'],'args':usable['args']})
                    self.assertIn('result',r)
            r=self.call('/api/advance',{})
            self.assertEqual(bool(r['result']['completed']),month==119)
        s=self.call('/api/state')
        self.assertTrue(s['completed'])
        self.assertEqual(s['transfer_count'],1)
        self.assertEqual(len(s['year_reports']),10)
        self.assertEqual(len(s['endings']),48)
        self.assertEqual(s['month_index'],119)  # terminal month is indexed 119; completed is the 120th month
        with self.assertRaises(HTTPError) as ctx:self.call('/api/advance',{})
        self.assertEqual(ctx.exception.code,400)
        self.call('/api/save',{'slot':'earth'})
        self.call('/api/new',{'seed':123,'economy':'standard','focus':'J01'})
        self.assertEqual(self.call('/api/state')['month_index'],0)
        self.call('/api/load',{'slot':'earth'})
        self.assertEqual(self.call('/api/state')['transfer_count'],1)
    def test_static_and_invalid_requests(self):
        for path in ('/','/app.js','/styles.css'):
            with urlopen(f'http://127.0.0.1:{self.server.server_port}{path}') as res:self.assertEqual(res.status,200)
        for payload in ({'kind':'rest','args':{'unexpected':1}},{'kind':'unknown','args':{}}):
            with self.assertRaises(HTTPError) as ctx:self.call('/api/action',payload)
            self.assertEqual(ctx.exception.code,400)
        with self.assertRaises(HTTPError):self.call('/api/save',{'slot':'../invalid'})
if __name__=='__main__':unittest.main()
