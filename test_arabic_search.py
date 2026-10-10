import unittest
import numpy as np
from app.db import normalize_arabic, get_embedding

class ArabicSearchTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(normalize_arabic('الإِجازَة'), 'الاجازة')
        self.assertEqual(normalize_arabic('مسؤوليات'), 'مسووليات')
    def test_embedding_variants(self):
        a = get_embedding('إجازة الموظف')
        b = get_embedding('اجازة الموظف')
        self.assertTrue(np.array_equal(a,b))
    def test_distinct_topics(self):
        a=get_embedding('إجراءات الإجازة السنوية')
        b=get_embedding('سياسة أمن المعلومات')
        self.assertLess(float(np.dot(a,b)),0.8)

if __name__ == '__main__':unittest.main()
