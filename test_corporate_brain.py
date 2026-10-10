import os
import tempfile
import unittest
from fastapi.testclient import TestClient
from app.config import settings
from app.db import init_db
from app.main import app

class CorporateBrainTests(unittest.TestCase):
    def setUp(self):
        self.old_path = settings.DB_PATH
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self.path = path
        settings.DB_PATH = path
        init_db(path)
        self.client = TestClient(app)
        self.owner = self.client.post('/api/v1/auth/register', json={
            'email':'owner@brain.test','full_name':'Owner','password':'Password123'
        }).json()['access_token']
        self.outsider = self.client.post('/api/v1/auth/register', json={
            'email':'outsider@brain.test','full_name':'Outsider','password':'Password123'
        }).json()['access_token']
        self.ws = self.client.post('/api/v1/workspaces',headers=self.h(self.owner),json={
            'name':'Knowledge Lab','slug':'knowledge-lab','description':''
        }).json()['id']
        doc = self.client.post(f'/api/v1/workspaces/{self.ws}/documents',headers=self.h(self.owner),json={
            'title':'سياسة الإجازات','content':'يمكن للموظف تقديم طلب إجازة سنوية عبر بوابة الموارد البشرية.','content_type':'markdown'
        })
        assert doc.status_code == 201, doc.text

    @staticmethod
    def h(token): return {'Authorization':'Bearer '+token}

    def tearDown(self):
        settings.DB_PATH = self.old_path
        os.remove(self.path)

    def test_sourced_answer(self):
        r=self.client.post(f'/api/v1/workspaces/{self.ws}/ai/ask',headers=self.h(self.owner),json={'query':'طلب إجازة سنوية'})
        self.assertEqual(r.status_code,200,r.text)
        data=r.json()
        self.assertTrue(data['citations'],data)
        self.assertIn('سياسة الإجازات',data['answer'])
        self.assertIn('document_id',data['citations'][0])

    def test_outsider_denied(self):
        r=self.client.post(f'/api/v1/workspaces/{self.ws}/ai/ask',headers=self.h(self.outsider),json={'query':'طلب إجازة سنوية'})
        self.assertEqual(r.status_code,403)

    def test_unknown_question_abstains(self):
        r=self.client.post(f'/api/v1/workspaces/{self.ws}/ai/ask',headers=self.h(self.owner),json={'query':'الكواكب والمجرات الفلكية'})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['citations'],[])
        self.assertIn('لا توجد أدلة كافية',r.json()['answer'])

if __name__=='__main__':unittest.main()
