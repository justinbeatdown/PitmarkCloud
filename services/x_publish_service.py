from __future__ import annotations

import base64, hashlib, hmac, time, uuid
from urllib.parse import quote
import httpx
from utils.config import settings

class XPublishError(RuntimeError): pass

def configured()->bool:
    return all(x.strip() for x in (settings.x_api_key, settings.x_api_secret, settings.x_access_token, settings.x_access_token_secret))

def connection_status()->dict:
    return {'configured':configured(),'connected':configured(),'read_write':True if configured() else False,'realtime_search_enabled':configured()}

def _enc(v): return quote(str(v), safe='~-._')
def _oauth(method,url,params=None):
    oauth={'oauth_consumer_key':settings.x_api_key.strip(),'oauth_nonce':uuid.uuid4().hex,'oauth_signature_method':'HMAC-SHA1','oauth_timestamp':str(int(time.time())),'oauth_token':settings.x_access_token.strip(),'oauth_version':'1.0'}
    pairs=list((params or {}).items())+list(oauth.items()); pairs.sort(key=lambda x:(_enc(x[0]),_enc(x[1])))
    norm='&'.join(f'{_enc(k)}={_enc(v)}' for k,v in pairs)
    base='&'.join((_enc(method.upper()),_enc(url),_enc(norm)))
    key=f'{_enc(settings.x_api_secret.strip())}&{_enc(settings.x_access_token_secret.strip())}'
    oauth['oauth_signature']=base64.b64encode(hmac.new(key.encode(),base.encode(),hashlib.sha1).digest()).decode()
    return 'OAuth '+', '.join(f'{_enc(k)}="{_enc(v)}"' for k,v in sorted(oauth.items()))

def _decode(r):
    try: data=r.json()
    except Exception: data={'raw':r.text}
    if r.is_error: raise XPublishError(f'X rejected the request ({r.status_code}): {data}')
    return data

def publish_x_post(text:str)->dict:
    if not configured(): raise XPublishError('X publishing is not configured on the server.')
    body=(text or '').strip()
    if not body: raise XPublishError('X post body is empty.')
    if len(body)>280: raise XPublishError(f'X post is {len(body)} characters; maximum is 280.')
    url='https://api.x.com/2/tweets'
    try: r=httpx.post(url,headers={'Authorization':_oauth('POST',url),'Content-Type':'application/json'},json={'text':body},timeout=30)
    except httpx.HTTPError as e: raise XPublishError(f'X request failed: {e}') from e
    data=_decode(r); pid=(data.get('data') or {}).get('id')
    if not pid: raise XPublishError('X returned success without a post id.')
    return {'ok':True,'platform':'x','external_post_id':pid,'raw':data}

def search_recent(query:str,max_results:int=10)->list[dict]:
    if not configured(): return []
    url='https://api.x.com/2/tweets/search/recent'
    params={'query':query,'max_results':max(10,min(100,max_results)),'tweet.fields':'created_at,author_id,public_metrics,lang'}
    try: r=httpx.get(url,headers={'Authorization':_oauth('GET',url,params)},params=params,timeout=20)
    except httpx.HTTPError: return []
    if r.is_error: return []
    return r.json().get('data') or []
