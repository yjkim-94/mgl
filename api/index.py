"""Vercel Python Function: one stateless API endpoint."""
import json
from http.server import BaseHTTPRequestHandler
from mgl_serverless import dispatch

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=2_000_000:raise ValueError('요청 크기 제한 초과')
            request=json.loads(self.rfile.read(size))
            if not isinstance(request,dict):raise ValueError('잘못된 요청')
            output=dispatch(request.get('op'),request.get('data',{}),request.get('snapshot'))
            status=200
        except (ValueError,TypeError,KeyError,OverflowError,RecursionError) as exc:
            output={'error':str(exc)};status=400
        except Exception:
            output={'error':'서버 오류'};status=500
        body=json.dumps(output,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)
