import json, tempfile, unittest, http.client, threading
from pathlib import Path
from mgl_play_v13 import PlaySession13
from mgl_story_engine import validate_story_data
from mgl_web import GameServer
from mgl_v13_validate import story_route

class StoryTests(unittest.TestCase):
 def test_catalog_and_windows(self):
  self.assertFalse(validate_story_data())
  s=PlaySession13()
  self.assertFalse(any(x['group']=='story' for x in s.action_options()))
  for i in range(24):s.next_month()
  self.assertEqual(len([x for x in s.action_options() if x['group']=='story']),12)
  self.assertTrue(s.view()['stories'][0]['next_scene'])
 def test_two_routes_different(self):
  left=story_route('rian','a',save_probe=True)
  right=story_route('rian','b',save_probe=True)
  self.assertTrue(left['audit'] and right['audit'] and left['finished'] and right['finished'])
  self.assertNotEqual(left['epilogue'],right['epilogue'])
 def test_cannot_skip_chapters(self):
  s=PlaySession13()
  for _ in range(96):s.next_month()
  with self.assertRaises(ValueError):s.act('life',{'id':'ST_RIAN_3_A','choice':'fulfill'})
  self.assertEqual(s.engine.state.earth_transfer_count,0)
 def test_hint_mode_and_save_restore(self):
  s=PlaySession13(focus='J40')
  self.assertGreater(s.view()['career_roadmap']['remaining_items'],0)
  s.set_hint_mode('off')
  self.assertIsNone(s.view()['career_roadmap'])
  s.set_hint_mode('light')
  payload=json.loads(json.dumps(s.save_payload()))
  other=PlaySession13.from_payload(payload)
  self.assertEqual(other.hint_mode,'light')
  self.assertEqual(other.save_payload(),s.save_payload())
 def test_load_legacy_save(self):
  from mgl_play_session import PlaySession
  old=PlaySession()
  old.act('bond',{'npc':'rian','style':'listen'})
  legacy=old.save_payload()
  restored=PlaySession13.from_payload(legacy)
  self.assertEqual(old.engine.state.log,restored.engine.state.log)
  self.assertEqual(restored.view()['schema_version'],'1.3')
  self.assertEqual(restored.hint_mode,'detailed')

class ApiTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.server=GameServer(('127.0.0.1',0),Path(self.temp.name))
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
  self.thread.start()
 def tearDown(self):
  self.server.shutdown();self.server.server_close();self.thread.join(timeout=3);self.temp.cleanup()
 def request(self,method,path,obj=None):
  con=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=4)
  args=({'body':json.dumps(obj),'headers':{'Content-Type':'application/json'}} if obj is not None else {})
  con.request(method,path,**args);r=con.getresponse();body=r.read();code=r.status;con.close()
  return code,json.loads(body) if path.startswith('/api/') else body
 def test_get_story_ui_and_api(self):
  status,body=self.request('GET','/')
  self.assertEqual(status,200);self.assertIn('인연의 이야기'.encode(),body)
  status,v=self.request('GET','/api/state');self.assertEqual(status,200)
  self.assertEqual(v['schema_version'],'1.3')
  self.assertIn('career_roadmap',v)
  status,v=self.request('POST','/api/hint',{'mode':'off'})
  self.assertEqual(status,200);self.assertEqual(v['state']['hint_mode'],'off')
  self.assertIsNone(v['state']['career_roadmap'])
  self.assertEqual(self.request('POST','/api/hint',{'mode':'invalid'})[0],400)
 def test_story_action_cost_and_save(self):
  for _ in range(24):self.request('POST','/api/advance',{})
  before=self.request('GET','/api/state')[1]
  status,r=self.request('POST','/api/action',{'kind':'life','args':{'id':'ST_RIAN_1_START','choice':'together'}})
  self.assertEqual(status,200)
  self.assertEqual(r['state']['ap_left'],before['ap_left']-2)
  self.assertIn('story_result',r['result'])
  self.assertEqual(r['state']['stories'][0]['branch'],'a')
  self.assertEqual(self.request('POST','/api/save',{'slot':'arc1'})[0],200)
  self.request('POST','/api/advance',{})
  status,r=self.request('POST','/api/load',{'slot':'arc1'})
  self.assertEqual(status,200);self.assertEqual(r['state']['stories'][0]['branch'],'a')

if __name__=='__main__': unittest.main()
