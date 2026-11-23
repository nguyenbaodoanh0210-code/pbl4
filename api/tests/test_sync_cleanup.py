import hashlib
import json
import unittest
from tests import support
from fastapi.testclient import TestClient
from app.main import app
from app.ai.disease import MODEL_PATH, METADATA_PATH
from app.services.multimodal_service import _lookup_disease


class SyncCleanupTests(unittest.TestCase):
    def test_removed_fertilizer_endpoint(self):
        with TestClient(app) as client:
            self.assertEqual(client.post('/api/ai/fertilizer/predict').status_code, 410)
            self.assertNotIn('/api/ai/fertilizer/predict', client.get('/openapi.json').json()['paths'])

    def test_current_model_and_label_mapping(self):
        metadata = json.loads(METADATA_PATH.read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest(), metadata['model_sha256'])
        self.assertEqual(_lookup_disease('ot_dom_vi_khuan')['profile'], 'bacterial')
        self.assertEqual(_lookup_disease('Bacterial')['profile'], 'bacterial')
        self.assertEqual(_lookup_disease('ot_khoe_manh')['profile'], 'healthy')
