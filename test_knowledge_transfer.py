import os
import tempfile
import unittest
from fastapi.testclient import TestClient
from app.config import settings
from app.db import init_db
from app.main import app

class KnowledgeTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.NamedTemporaryFile(suffix='.db',delete=False)
        self.temp.close()
        settings.DB_PATH=self.temp.name
        init_db()
        self.client=TestClient(app)
        self.owner=self.register('owner@example.com')
        self.other=self.register('other@example.com')
        self.viewer=self.register('viewer@example.com')
        w=self.client.post('/api/v1/workspaces',json={'name':'Team','slug':'team','description':''},headers=self.owner)
        self.assertEqual(w.status_code,201,w.text)
        self.ws=w.json()['id']
        self.client.post(f'/api/v1/workspaces/{self.ws}/members',json={'email':'viewer@example.com','role':'viewer'},headers=self.owner)
        self.url=f'/api/v1/workspaces/{self.ws}/knowledge-transfers'
        from app.db import get_db
        with get_db() as conn:
            self.viewer_id=conn.execute('SELECT id FROM users WHERE email=?',('viewer@example.com',)).fetchone()['id']
    def tearDown(self):
        os.unlink(self.temp.name)
    def register(self,email):
        r=self.client.post('/api/v1/auth/register',json={'email':email,'full_name':'Test Person','password':'Password123'})
        self.assertEqual(r.status_code,201,r.text)
        return {'Authorization':'Bearer '+r.json()['access_token']}
    def sample(self,**changes):
        d={'title':'تشغيل النظام المالي','knowledge_area':'المالية','procedure':'خطوات التشغيل والتأكد من سلامة البيانات اليومية','criticality':'high'}
        d.update(changes)
        return d
    def test_transfer_lifecycle_and_risk(self):
        r=self.client.post(self.url,json=self.sample(),headers=self.owner)
        self.assertEqual(r.status_code,201,r.text)
        tid=r.json()['id']
        self.assertEqual(self.client.get(self.url+'/risk-summary',headers=self.viewer).json()['high_priority_unapproved'],1)
        r=self.client.patch(f'{self.url}/{tid}/review',json={'status':'approved'},headers=self.owner)
        self.assertEqual(r.status_code,400)
        r=self.client.post(self.url,json=self.sample(successor_id=self.viewer_id),headers=self.owner)
        self.assertEqual(r.status_code,201,r.text)
        tid2=r.json()['id']
        self.assertEqual(self.client.patch(f'{self.url}/{tid2}/review',json={'status':'approved'},headers=self.viewer).status_code,403)
        self.assertEqual(self.client.patch(f'{self.url}/{tid2}/review',json={'status':'approved','review_note':'تم التحقق'},headers=self.owner).status_code,200)
        self.assertEqual(self.client.get(self.url+'/risk-summary',headers=self.owner).json()['approved'],1)
        self.assertEqual(self.client.patch(f'{self.url}/{tid2}/review',json={'status':'draft'},headers=self.viewer).status_code,403)
        self.assertEqual(self.client.patch(f'{self.url}/{tid2}/review',json={'status':'draft'},headers=self.owner).status_code,409)
    def test_isolation_and_invalid_references(self):
        self.assertEqual(self.client.get(self.url,headers=self.other).status_code,403)
        self.assertEqual(self.client.post(self.url,json=self.sample(),headers=self.viewer).status_code,403)
        self.assertEqual(self.client.post(self.url,json=self.sample(successor_id='outsider'),headers=self.owner).status_code,400)
        self.assertEqual(self.client.post(self.url,json=self.sample(source_document_id='wrong'),headers=self.owner).status_code,400)
        self.assertEqual(self.client.get(self.url+'/not-real',headers=self.owner).status_code,404)
