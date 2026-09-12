from __future__ import annotations

import base64, hashlib, hmac, time, uuid
from urllib.parse import quote
import httpx
from utils.config import settings

class XPublishError(RuntimeError): pass

def configured()->bool:
    return all(x.strip() for x in (settings.x_api_key, settings.x_api_secret, settings.x_access_token, settings.x_access_token_secret))

def _max_post_chars()->int:
    try:
        return max(280, min(25000, int(settings.x_post_max_characters)))
    except (TypeError, ValueError):
        return 25000

def connection_status()->dict:
    max_chars = _max_post_chars()
    return {
        'configured': configured(),
        'connected': configured(),
        'read_write': True if configured() else False,
        'realtime_search_enabled': configured(),
        'max_post_characters': max_chars,
        'premium_long_posts': max_chars > 280,
    }

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
    max_chars = _max_post_chars()
    if len(body)>max_chars:
        raise XPublishError(f'X post is {len(body)} characters; configured maximum is {max_chars:,}.')
    url='https://api.x.com/2/tweets'
    try: r=httpx.post(url,headers={'Authorization':_oauth('POST',url),'Content-Type':'application/json'},json={'text':body},timeout=30)
    except httpx.HTTPError as e: raise XPublishError(f'X request failed: {e}') from e
    data=_decode(r); pid=(data.get('data') or {}).get('id')
    if not pid: raise XPublishError('X returned success without a post id.')
    return {'ok':True,'platform':'x','external_post_id':pid,'raw':data,'character_count':len(body),'max_post_characters':max_chars}

def search_recent(query:str,max_results:int=10)->list[dict]:
    if not configured(): return []
    url='https://api.x.com/2/tweets/search/recent'
    params={'query':query,'max_results':max(10,min(100,max_results)),'tweet.fields':'created_at,author_id,public_metrics,lang'}
    try: r=httpx.get(url,headers={'Authorization':_oauth('GET',url,params)},params=params,timeout=20)
    except httpx.HTTPError: return []
    if r.is_error: return []
    return r.json().get('data') or []


def _current_user() -> dict | None:
    if not configured():
        return None
    url = 'https://api.x.com/2/users/me'
    params = {'user.fields': 'id,name,username'}
    try:
        r = httpx.get(url, headers={'Authorization': _oauth('GET', url, params)}, params=params, timeout=20)
    except httpx.HTTPError:
        return None
    if r.is_error:
        return None
    return r.json().get('data') or None


def fetch_mentions(max_results: int = 25) -> list[dict]:
    """Fetch recent mentions of the connected Pitmark X account.

    Read failures return an empty list so Social Operator can continue serving Facebook/Instagram.
    """
    user = _current_user()
    if not user or not user.get('id'):
        return []
    user_id = str(user['id'])
    url = f'https://api.x.com/2/users/{user_id}/mentions'
    params = {
        'max_results': max(5, min(100, max_results)),
        'tweet.fields': 'created_at,author_id,conversation_id,public_metrics,lang',
        'expansions': 'author_id',
        'user.fields': 'id,name,username',
    }
    try:
        r = httpx.get(url, headers={'Authorization': _oauth('GET', url, params)}, params=params, timeout=20)
    except httpx.HTTPError:
        return []
    if r.is_error:
        return []
    payload = r.json()
    users = {str(item.get('id')): item for item in ((payload.get('includes') or {}).get('users') or [])}
    items = []
    for tweet in payload.get('data') or []:
        author = users.get(str(tweet.get('author_id') or '')) or {}
        items.append({
            **tweet,
            'author_name': author.get('name') or author.get('username') or tweet.get('author_id'),
            'author_username': author.get('username'),
        })
    return items
