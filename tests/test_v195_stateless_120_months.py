"""Full lifecycle and snapshot regression tests for the stateless dispatcher."""
import json
import unittest
from mgl_serverless import dispatch


class StatelessLifecycleQA(unittest.TestCase):
    def test_120_months_and_mandatory_earth_transfer(self):
        response = dispatch('state', {})
        self.assertEqual(response['state']['age'], 10)
        self.assertEqual(len(response['state']['endings']), 48)
        for month in range(120):
            previous = response['snapshot']
            response = dispatch('advance', {}, previous)
            self.assertEqual(response['state']['completed'], month == 119)
            self.assertEqual(response['state']['transfer_count'], int(month == 119))
        self.assertEqual(response['state']['age'], 20)
        self.assertIsNotNone(response['state']['final'])
        self.assertEqual(dispatch('state', {}, response['snapshot'])['state'], response['state'])
        self.assertLess(len(json.dumps(response['snapshot']).encode()), 2_000_000)
        with self.assertRaises(ValueError):
            dispatch('advance', {}, response['snapshot'])

    def test_new_game_does_not_inherit_prior_snapshot(self):
        advanced = dispatch('advance', {})
        fresh = dispatch('new', {'seed': 42}, advanced['snapshot'])
        self.assertEqual(fresh['state']['month_index'], 0)
        self.assertEqual(fresh['state']['transfer_count'], 0)
        self.assertFalse(fresh['state']['completed'])


if __name__ == '__main__':
    unittest.main()
