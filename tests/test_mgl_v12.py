"""python -m unittest discover -s tests -v"""
import http.client,json,tempfile,threading,unittest
from pathlib import Path
from mgl_play_session import PlaySession,encode,decode
from mgl_web import GameServer

class SessionTests(unittest.TestCase):
 def test_month_actions_and_no_underage_club(self):
  s=PlaySession()
  self.assertEqual((s.view()['age'],s.view()['ap_left'],s.view()['slots_left']),(10,8,4))
  self.assertTrue(s.view()['recommendation'])
  self.assertTrue(any(x['kind']=='project' and not x['usable'] for x in s.action_options()))
  with self.assertRaises(ValueError):s.act('hobby',{'hobby':'romance'})
  with self.assertRaises(ValueError):s.act('club',{})
  for _ in range(4):s.act('rest')
  with self.assertRaises(ValueError):s.act('rest')
  self.assertEqual((s.view()['ap_used'],s.view()['slots_used']),(4,4))
 def test_life_choices_change_outcome(self):
  a,b=PlaySession(),PlaySession()
  a.act('life',{'id':'L_HOME_10','choice':'talk'})
  b.act('life',{'id':'L_HOME_10','choice':'plan'})
  self.assertNotEqual(a.engine.life_flags,b.engine.life_flags)
  self.assertNotEqual(a.view()['trust'],b.view()['trust'])
 def test_year_report_and_ending(self):
  s=PlaySession()
  for _ in range(120):s.next_month()
  self.assertEqual(len(s.reports),10)
  self.assertTrue(s.view()['completed'])
  self.assertEqual(s.view()['transfer_count'],1)
  self.assertIsNone(s.view()['final']['selected'])
  with self.assertRaises(ValueError):s.next_month()
 def test_specialization_and_focus(self):
  s=PlaySession();orig=s.engine.state.cash
  s.set_focus('J40');self.assertEqual(s.engine.state.cash,orig)
  with self.assertRaises(ValueError):s.specialize('INT')
  for _ in range(72):s.next_month()
  s.specialize('INT');s.specialize('CHA')
  with self.assertRaises(ValueError):s.specialize('SKL')
 def test_save_load_midgame(self):
  s=PlaySession(focus='S04')
  s.act('life',{'id':'L_HOME_10','choice':'talk'})
  s.act('bond',{'npc':'rian','style':'listen'})
  for _ in range(13):s.next_month()
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'s.json';s.save(path);r=PlaySession.load(path)
  self.assertEqual(s.save_payload(),r.save_payload())
  self.assertEqual(s.view(),r.view())
  s.next_month();r.next_month();self.assertEqual(s.save_payload(),r.save_payload())
 def test_recommendation_side_effect_free(self):
  s=PlaySession(focus='J05');a=s.save_payload()
  self.assertTrue(s.recommend())
  self.assertEqual(s.save_payload(),a)
 def test_codec(self):
  obj={'x':{(1,2),(3,4)},'y':('a',{'b'})}
  self.assertEqual(decode(json.loads(json.dumps(encode(obj)))),obj)

class HttpTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.srv=GameServer(('127.0.0.1',0),Path(self.temp.name))
  self.thread=threading.Thread(target=self.srv.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):
  self.srv.shutdown();self.srv.server_close();self.thread.join(timeout=3);self.temp.cleanup()
 def request(self,method,path,obj=None):
  con=http.client.HTTPConnection('127.0.0.1',self.srv.server_port,timeout=4)
  kw=({'body':json.dumps(obj),'headers':{'Content-Type':'application/json'}} if obj is not None else {})
  con.request(method,path,**kw);r=con.getresponse();body=r.read();status=r.status;con.close()
  return status,json.loads(body) if path.startswith('/api/') else body
 def test_html_and_api_actions(self):
  status,body=self.request('GET','/');self.assertEqual(status,200);self.assertIn('별의 아이'.encode(),body)
  st,view=self.request('GET','/api/state');self.assertEqual(st,200);self.assertEqual(view['age'],10)
  st,actions=self.request('GET','/api/actions');self.assertEqual(st,200);self.assertGreater(len(actions['actions']),30)
 def test_action_and_advance(self):
  st,res=self.request('POST','/api/action',{'kind':'life','args':{'id':'L_HOME_10','choice':'talk'}})
  self.assertEqual(st,200);self.assertEqual(res['state']['slots_used'],1)
  st,res=self.request('POST','/api/advance',{})
  self.assertEqual(st,200);self.assertEqual(res['state']['month_index'],1)
  self.assertTrue((Path(self.temp.name)/'autosave.json').exists())
 def test_slot_and_traversal(self):
  self.assertEqual(self.request('POST','/api/save',{'slot':'slot1'})[0],200)
  self.request('POST','/api/advance',{})
  st,res=self.request('POST','/api/load',{'slot':'slot1'})
  self.assertEqual(st,200);self.assertEqual(res['state']['month_index'],0)
  self.assertEqual(self.request('POST','/api/save',{'slot':'../escape'})[0],400)
  self.assertEqual(self.request('POST','/api/action',{'kind':'club','args':{}})[0],400)

if __name__=='__main__':unittest.main()
