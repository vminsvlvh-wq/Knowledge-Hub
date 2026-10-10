import os
import tempfile
import unittest
from fastapi.testclient import TestClient
from app.config import settings
from app.db import init_db
from app.main import app

class DecisionImpactTests(unittest.TestCase):
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
        self.url=f'/api/v1/workspaces/{self.ws}/decisions'
    def tearDown(self):
        os.unlink(self.temp.name)
    def register(self,email):
        r=self.client.post('/api/v1/auth/register',json={'email':email,'full_name':'Test Person','password':'Password123'})
        self.assertEqual(r.status_code,201,r.text)
        return {'Authorization':'Bearer '+r.json()['access_token']}
    def test_decision_and_measured_impact(self):
        r=self.client.post(self.url,json={'title':'خفض زمن الرد','problem':'تأخر الرد','rationale':'تحسين العمليات'},headers=self.owner)
        self.assertEqual(r.status_code,201,r.text)
        d=r.json()['id']
        m=self.client.post(f'{self.url}/{d}/metrics',json={'metric_name':'زمن الرد','unit':'دقيقة','direction':'decrease','baseline':20,'target':10},headers=self.owner)
        self.assertEqual(m.status_code,201,m.text)
        mid=m.json()['id']
        self.assertEqual(self.client.get(f'{self.url}/{d}/impact',headers=self.viewer).json()['metrics'][0]['latest_value'],None)
        measure=self.client.post(f'{self.url}/{d}/metrics/{mid}/measurements',json={'value':8,'note':'الأسبوع الأول'},headers=self.owner)
        self.assertEqual(measure.status_code,201,measure.text)
        impact=self.client.get(f'{self.url}/{d}/impact',headers=self.viewer)
        self.assertEqual(impact.status_code,200)
        metric=impact.json()['metrics'][0]
        self.assertEqual(metric['absolute_change'],-12)
        self.assertEqual(metric['percent_change'],-60)
        self.assertTrue(metric['target_met'])
    def test_permission_isolation(self):
        self.assertEqual(self.client.get(self.url,headers=self.other).status_code,403)
        self.assertEqual(self.client.post(self.url,json={'title':'Decision','problem':'Problem','rationale':'Reason'},headers=self.viewer).status_code,403)
        self.assertEqual(self.client.get(self.url).status_code,401)
    def test_cross_workspace_and_missing_metric(self):
        d=self.client.post(self.url,json={'title':'Decision','problem':'Problem','rationale':'Reason'},headers=self.owner).json()['id']
        self.assertEqual(self.client.get(f'{self.url}/{d}/impact',headers=self.other).status_code,403)
        self.assertEqual(self.client.post(f'{self.url}/{d}/metrics/fake/measurements',json={'value':1},headers=self.owner).status_code,404)

if __name__=='__main__':unittest.main()
