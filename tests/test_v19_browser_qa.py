"""Browser QA with local server responses proxied through Playwright route.
Chromium's direct localhost networking may be administratively blocked.
"""
import sys,threading,tempfile,urllib.request,urllib.error,mimetypes
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mgl_web import GameServer
from playwright.sync_api import sync_playwright

def main():
    with tempfile.TemporaryDirectory() as tmp:
        server=GameServer(('127.0.0.1',0),save_dir=tmp)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
                try:
                    for width,height,label in [(390,844,'mobile'),(1440,900,'desktop')]:
                        page=browser.new_page(viewport={'width':width,'height':height})
                        errors=[]
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        def proxy(route):
                            req=route.request
                            path=req.url.split('mgl.test',1)[-1]
                            url=f'http://127.0.0.1:{server.server_port}{path}'
                            data=req.post_data.encode() if req.post_data is not None else None
                            try:
                                with urllib.request.urlopen(urllib.request.Request(url,data=data,method=req.method,headers={'Content-Type':'application/json'}),timeout=8) as r:
                                    route.fulfill(status=r.status,body=r.read(),headers={'content-type':r.headers.get('Content-Type','text/plain')})
                            except urllib.error.HTTPError as e:
                                route.fulfill(status=e.code,body=e.read(),headers={'content-type':'application/json'})
                        page.route('http://mgl.test/**',proxy)
                        page.goto('http://mgl.test/',wait_until='networkidle')
                        page.locator('#journey-label').wait_for()
                        assert '0 / 120' in page.locator('#journey-label').inner_text()
                        assert '8' in page.locator('#ap').inner_text()
                        assert page.locator('#focus option').count()==48
                        assert page.locator('#npcs .npc').count()>0
                        assert not errors,errors
                        if label=='mobile':
                            page.locator('#tutorial-dismiss').click()
                            assert page.locator('#onboarding').is_hidden()
                            page.locator('#tutorial-restore').click()
                            assert page.locator('#onboarding').is_visible()
                            page.locator('#next').click()
                            page.wait_for_function("document.querySelector('#journey-label').textContent.includes('1 / 120')")
                            assert '1 / 120' in page.locator('#journey-label').inner_text()
                            page.locator('#hint-mode').select_option('off')
                            page.wait_for_function("document.querySelector('#hint-mode').value==='off'")
                        page.screenshot(path=str(Path(tmp)/f'{label}.png'),full_page=True)
                        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 2'),f'{label} horizontal overflow'
                        print(f'{label}: PASS, page errors={len(errors)}')
                        page.close()
                finally:browser.close()
        finally:server.shutdown()
if __name__=='__main__':main()
