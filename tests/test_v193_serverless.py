import unittest
from mgl_serverless import dispatch

class StatelessTests(unittest.TestCase):
    def test_isolation_and_roundtrip(self):
        a=dispatch('state',{})
        b=dispatch('advance',{},a['snapshot'])
        self.assertNotEqual(a['state']['calendar_month'],b['state']['calendar_month'])
        self.assertEqual(a['state']['calendar_month'],dispatch('state',{},a['snapshot'])['state']['calendar_month'])
        self.assertEqual(b['state'],dispatch('state',{},b['snapshot'])['state'])
    def test_reject_invalid_action(self):
        with self.assertRaises(ValueError):dispatch('action',{'kind':'rest','args':{'unexpected':1}})
    def test_new(self):
        a=dispatch('advance',{})
        b=dispatch('new',{'seed':7},a['snapshot'])
        self.assertEqual(b['state']['age'],10)
    def test_hint_persistence(self):
        a=dispatch('hint',{'mode':'off'})
        b=dispatch('state',{},a['snapshot'])
        self.assertEqual(b['state']['hint_mode'],'off')
if __name__=='__main__':unittest.main()
