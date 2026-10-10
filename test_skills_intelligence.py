import os
import tempfile
import unittest
from fastapi.testclient import TestClient
from app.config import settings
from app.db import init_db
from app.main import app


class SkillsIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.NamedTemporaryFile(suffix='.db',delete=False)
        self.temp.close()
        settings.DB_PATH = self.temp.name
        init_db()
        self.client = TestClient(app)
        self.owner = self.register('owner@test.com')
        self.staff = [self.register(f'worker{x}@test.com') for x in range(3)]
        self.outsider = self.register('outsider@test.com')
        r = self.client.post('/api/v1/workspaces',json={'name':'Finance','slug':'finance','description':''},headers=self.owner)
        self.assertEqual(r.status_code,201,r.text)
        self.ws = r.json()['id']
        self.api = f'/api/v1/workspaces/{self.ws}/skills'
        for x in range(3):
            r = self.client.post(f'/api/v1/workspaces/{self.ws}/members',
                                 json={'email':f'worker{x}@test.com','role':'viewer'},headers=self.owner)
            self.assertEqual(r.status_code,201,r.text)

    def tearDown(self):
        os.unlink(self.temp.name)

    def register(self,email):
        r=self.client.post('/api/v1/auth/register',json={
            'email':email,'full_name':'Test User','password':'Password123'})
        self.assertEqual(r.status_code,201,r.text)
        return {'Authorization':'Bearer '+r.json()['access_token']}

    def requirement(self, name, level=3, user=None):
        return self.client.post(self.api+'/requirements',headers=user or self.owner,
                                json={'role_name':'محلل بيانات','skill_name':name,'target_level':level})

    def profile(self, user, skills=None, role='محلل بيانات'):
        return self.client.put(self.api+'/my-profile',headers=user,
                               json={'role_name':role,'skills':skills if skills is not None else [
                                   {'skill_name':'SQL','level':2,'evidence_note':'دورة تدريبية'}]})

    def test_staff_self_profile_and_gap(self):
        self.assertEqual(self.requirement('SQL',4).status_code,201)
        self.assertEqual(self.requirement('Power BI',3).status_code,201)
        r = self.profile(self.staff[0]); self.assertEqual(r.status_code,200,r.text)
        gap = self.client.get(self.api+'/my-gap',headers=self.staff[0]).json()
        self.assertEqual(gap['source'],'self_reported')
        byskill={x['skill_name']:x for x in gap['gaps']}
        self.assertEqual(byskill['SQL']['gap'],2)
        self.assertEqual(byskill['Power BI']['status'],'unassessed')
        self.assertIsNone(byskill['Power BI']['current_level'])
        self.assertEqual(self.client.get(self.api+'/my-profile',headers=self.staff[1]).json()['skills'],[])

    def test_admin_privacy_threshold_and_aggregate(self):
        self.requirement('SQL',3)
        self.requirement('Excel',3)
        self.profile(self.staff[0], [{'skill_name':'SQL','level':1}])
        self.profile(self.staff[1], [{'skill_name':'SQL','level':4}])
        r=self.client.get(self.api+'/gap-summary',headers=self.owner)
        self.assertEqual(r.status_code,200)
        self.assertTrue(r.json()['groups'][0]['suppressed'])
        self.profile(self.staff[2], [{'skill_name':'SQL','level':2}])
        group=self.client.get(self.api+'/gap-summary',headers=self.owner).json()['groups'][0]
        self.assertFalse(group['suppressed'])
        byskill={x['skill_name']:x for x in group['skills']}
        self.assertEqual(byskill['SQL']['below_target'],2)
        self.assertEqual(byskill['SQL']['meets_target'],1)
        self.assertTrue(byskill['Excel']['suppressed'])
        self.assertNotIn('user_id',str(group))
        self.assertEqual(self.client.get(self.api+'/gap-summary',headers=self.staff[0]).status_code,403)

    def test_role_and_workspace_isolation(self):
        self.assertEqual(self.requirement('SQL',user=self.staff[0]).status_code,403)
        self.assertEqual(self.client.get(self.api+'/requirements',headers=self.outsider).status_code,403)
        self.assertEqual(self.client.get(self.api+'/my-profile',headers=self.outsider).status_code,403)
        self.assertEqual(self.profile(self.outsider).status_code,403)
        self.assertEqual(self.client.get(self.api+'/gap-summary').status_code,401)
        self.assertEqual(self.client.get(self.api+'/requirements',headers=self.staff[0]).status_code,200)

    def test_validation_and_updates(self):
        r=self.requirement('SQL',3);self.assertEqual(r.status_code,201)
        rid=r.json()['id']
        self.assertEqual(self.requirement('SQL',5).json()['id'],rid)
        self.assertEqual(self.client.get(self.api+'/requirements',headers=self.owner).json()[0]['target_level'],5)
        self.assertEqual(self.requirement('Python',7).status_code,422)
        self.assertEqual(self.profile(self.staff[0], [{'skill_name':'SQL','level':2},{'skill_name':'sql','level':3}]).status_code,400)
        self.assertEqual(self.profile(self.staff[0], [{'skill_name':'SQL','level':7}]).status_code,422)
        self.assertEqual(self.client.delete(self.api+'/requirements/'+rid,headers=self.staff[0]).status_code,403)
        self.assertEqual(self.client.delete(self.api+'/requirements/'+rid,headers=self.owner).status_code,204)
        self.assertEqual(self.client.delete(self.api+'/requirements/'+rid,headers=self.owner).status_code,404)

    def test_frontend_contains_accessible_sections(self):
        response=self.client.get('/')
        self.assertEqual(response.status_code,200)
        self.assertIn('id="transfer"',response.text)
        self.assertIn('id="skills"',response.text)
        self.assertIn('async function loadTransfers()',response.text)
        self.assertIn('async function loadSkills()',response.text)


if __name__=='__main__':unittest.main()
