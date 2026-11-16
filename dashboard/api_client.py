import os, requests
class APIError(RuntimeError): pass
class APIClient:
    def __init__(self, base_url=None): self.base_url=(base_url or os.getenv('API_BASE_URL','http://localhost:8001')).rstrip('/')
    def request(self, method,path,**kwargs):
        try:
            r=requests.request(method,self.base_url+path,timeout=15,**kwargs)
            if not r.ok: raise APIError(f'HTTP {r.status_code}: {r.text}')
            return r.json()
        except requests.RequestException as e: raise APIError(str(e)) from e
    def get(self,path,params=None): return self.request('GET',path,params=params)
    def post(self,path,payload): return self.request('POST',path,json=payload)
