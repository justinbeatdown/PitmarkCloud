import os
os.environ.setdefault('ENVIRONMENT','development')
os.environ.setdefault('PITMARK_ADMIN_KEY','dev-admin-key-that-is-long-enough')
from fastapi.testclient import TestClient
from main import app
with TestClient(app) as c:
    h={'X-Pitmark-Admin-Key':os.environ['PITMARK_ADMIN_KEY']}
    assert c.get('/health').status_code==200
    assert c.get('/control').status_code==200
    assert c.get('/api/control/status',headers=h).status_code==200
    r=c.post('/api/control/autopilot/composer/generate',headers=h,json={'platform':'facebook','prompt':'home track roll call','goal':'community'})
    assert r.status_code==200 and r.json().get('body')
    r=c.post('/api/control/shield/ingest',headers=h,json={'source_message_id':'smoke-spam','sender':'sales@example.com','subject':'Store growth question','body':'Your store has potential. We can increase traffic and conversions with our marketing agency SEO services and grow your sales.'})
    assert r.status_code==200 and r.json()['classification']=='Spam'
    r=c.post('/api/control/shield/ingest',headers=h,json={'source_message_id':'smoke-customer','sender':'customer@example.com','subject':'Question about my order','body':'Hi, I placed an order and wanted to know when I should expect tracking.'})
    assert r.status_code==200 and r.json()['classification'] in ('Review','Legit')
print('Pitmark Control Center smoke test: PASS')
