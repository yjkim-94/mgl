import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class QASourceChecks(unittest.TestCase):
 def test_modal_accessibility(self):
  html=(ROOT/'web/index.html').read_text()
  js=(ROOT/'web/app.js').read_text()
  self.assertIn('aria-modal="true"',html)
  self.assertIn("e.key==='Escape'",js)
  self.assertIn('modalReturnFocus.focus()',js)
 def test_mobile_layout_guards(self):
  css=(ROOT/'web/styles.css').read_text()
  self.assertIn('.topbar{flex-wrap:wrap}',css)
  self.assertIn('.npcs{grid-template-columns:minmax(0,1fr)}',css)
if __name__=='__main__':unittest.main()
