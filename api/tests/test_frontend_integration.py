"""Comprehensive Web Frontend MVC Integration & Contract Tests.

Stage 4D: Verifies static asset serving, router contract, ES module integrity,
and end-to-end data flow between the frontend views and backend controllers.
"""

import glob
import os
import unittest
from tests import support  # Configure isolated DB and disabled MQTT before app imports.
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models import User, Greenhouse, Device, ActuatorState, CameraLog


class TestFrontendStaticAssetServing(unittest.TestCase):
    """Verifies that FastAPI serves all static assets (HTML, CSS, JS) correctly."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_root_index_html_served(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers.get("content-type", ""))
        text = resp.text
        self.assertIn("<!doctype html>", text.lower())
        self.assertIn("Smart Garden", text)
        self.assertIn('type="module" src="/app.js"', text)
        self.assertIn("/styles/diagnosis.css", text)
        self.assertIn("/styles/editorial.css", text)

    def test_styles_served(self):
        styles = ["base.css", "workspace.css", "editorial.css", "auth.css", "diagnosis.css"]
        for sheet in styles:
            resp = self.client.get(f"/styles/{sheet}")
            self.assertEqual(resp.status_code, 200, f"Stylesheet {sheet} failed to load")
            self.assertIn("text/css", resp.headers.get("content-type", ""))

    def test_diagnosis_css_contains_viewfinder_and_hud(self):
        resp = self.client.get("/styles/diagnosis.css")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(".viewfinder-container", resp.text)
        self.assertIn(".hud-corner", resp.text)
        self.assertIn(".btn-esp32-scan", resp.text)
        self.assertIn(".laser-scanner-line", resp.text)

    def test_frontend_js_modules_served(self):
        js_files = [
            "/app.js",
            "/js/models/store.js",
            "/js/models/apiClient.js",
            "/js/controllers/router.js",
            "/js/controllers/appController.js",
            "/js/views/components.js",
            "/js/views/dashboardView.js",
            "/js/views/historyView.js",
            "/js/views/gardenView.js",
            "/js/views/diagnosisView.js",
            "/js/views/alertsView.js",
            "/js/views/authView.js",
        ]
        for js in js_files:
            resp = self.client.get(js)
            self.assertEqual(resp.status_code, 200, f"Script {js} failed to load")
            self.assertIn("javascript", resp.headers.get("content-type", "").lower())


class TestFrontendModuleSanity(unittest.TestCase):
    """Verifies that all 12 ES Module files in frontend have valid syntax, balanced brackets,
    and adhere to the strict PUMP-only constraint (no FAN / quạt)."""

    def test_bracket_balance_and_syntax(self):
        frontend_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
        )
        files = glob.glob(os.path.join(frontend_dir, "**", "*.js"), recursive=True)
        self.assertGreaterEqual(len(files), 12, "Should check at least 12 frontend JS files")

        pairs = {')': '(', '}': '{', ']': '['}
        for f in files:
            with open(f, "r", encoding="utf-8") as fp:
                content = fp.read()
            stack = []
            line = 1
            for char in content:
                if char == "\n":
                    line += 1
                elif char in "({[":
                    stack.append((char, line))
                elif char in ")}]":
                    self.assertTrue(
                        len(stack) > 0,
                        f"Unmatched closing '{char}' at {os.path.basename(f)}:{line}",
                    )
                    last, lline = stack.pop()
                    self.assertEqual(
                        pairs[char],
                        last,
                        f"Mismatched '{last}' (line {lline}) with '{char}' at {os.path.basename(f)}:{line}",
                    )
            self.assertEqual(
                len(stack),
                0,
                f"Unclosed '{stack[-1][0]}' from line {stack[-1][1]} in {os.path.basename(f)}" if stack else "",
            )

    def test_no_fan_actuator_references_in_views(self):
        frontend_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "js")
        )
        for root, _, filenames in os.walk(frontend_dir):
            for fname in filenames:
                if fname.endswith(".js"):
                    fpath = os.path.join(root, fname)
                    with open(fpath, "r", encoding="utf-8") as fp:
                        content = fp.read()
                    # FAN as an actuator is forbidden; FAN / Quạt should not be in store/views
                    self.assertNotIn("act-garden01-fan", content)
                    self.assertNotIn("ACTUATOR-FAN", content)


class TestFrontendE2EWorkflow(unittest.TestCase):
    """Simulates the entire user journey through the Web Frontend via REST API contracts."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Login with demo user
        login_resp = cls.client.post(
            "/api/auth/login",
            json={"email": "demo@smartgreenhouse.local", "password": "Demo@12345678"},
        )
        if login_resp.status_code == 200:
            cls.token = login_resp.json()["access_token"]
        else:
            cls.token = ""
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_01_auth_me(self):
        resp = self.client.get("/api/auth/me", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["email"], "demo@smartgreenhouse.local")

    def test_02_workspace_initial_load(self):
        """Validates all 5 endpoints called by loadWorkspaceData() in apiClient.js."""
        endpoints = [
            "/api/greenhouses",
            "/api/devices",
            "/api/recommendations?limit=100",
            "/api/notifications?limit=50",
            "/api/crops",
        ]
        for ep in endpoints:
            resp = self.client.get(ep, headers=self.headers)
            self.assertEqual(resp.status_code, 200, f"Endpoint {ep} failed")
            self.assertIsInstance(resp.json(), list)

    def test_03_dashboard_sensor_telemetry(self):
        """Validates that telemetry provides the 3 outdoor metrics (DHT22 + LDR)."""
        devs_resp = self.client.get("/api/devices", headers=self.headers)
        sensor_nodes = [d for d in devs_resp.json() if d.get("device_type") in ("SENSOR_NODE", "SENSOR")]
        if sensor_nodes:
            dev_id = sensor_nodes[0]["device_id"]
            resp = self.client.get(f"/api/sensors/{dev_id}?limit=10", headers=self.headers)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            if data:
                reading = data[0]
                self.assertIn("temperature", reading)
                self.assertIn("humidity", reading)
                self.assertIn("light_level", reading)

    def test_04_pump_actuator_controls(self):
        """Tests that pump control works and strictly rejects FAN."""
        gh_resp = self.client.get("/api/greenhouses", headers=self.headers)
        gh_id = gh_resp.json()[0]["greenhouse_id"]

        # Read pump state
        act_resp = self.client.get(f"/api/greenhouses/{gh_id}/actuators", headers=self.headers)
        self.assertEqual(act_resp.status_code, 200)
        actuators = act_resp.json().get("actuators", [])
        types = [a["actuator_type"] for a in actuators]
        self.assertNotIn("FAN", types, "FAN must not exist in actuator list")

        # Toggle pump mode to AUTO then MANUAL
        put_auto = self.client.put(
            f"/api/greenhouses/{gh_id}/actuators/PUMP",
            headers=self.headers,
            json={"control_mode": "AUTO"},
        )
        # AUTO without sensor binding/calibrated hardware must fail closed.
        self.assertEqual(put_auto.status_code, 422)

        put_manual = self.client.put(
            f"/api/greenhouses/{gh_id}/actuators/PUMP",
            headers=self.headers,
            json={"control_mode": "MANUAL", "is_on": False},
        )
        self.assertEqual(put_manual.status_code, 200)
        self.assertEqual(put_manual.json()["actuator"]["control_mode"], "MANUAL")
        self.assertFalse(put_manual.json()["actuator"]["is_on"])

    def test_05_garden_area_lifecycle_stage_4c(self):
        """Full lifecycle test for Outdoor Garden Areas and Agronomic Thresholds."""
        gh_resp = self.client.get("/api/greenhouses", headers=self.headers)
        gh_id = gh_resp.json()[0]["greenhouse_id"]

        # Create
        area_payload = {
            "name": "Luống Kiểm Thử 4D",
            "area_id": "area-test-4d",
            "area_sqm": 22.0,
            "crop_stage_id": "crop-lettuce-vegetative",
            "custom_min_temp": 16.0,
            "custom_max_temp": 27.0,
            "custom_fungal_humidity_threshold": 84.0,
        }
        create_resp = self.client.post(
            f"/api/greenhouses/{gh_id}/areas",
            headers=self.headers,
            json=area_payload,
        )
        self.assertEqual(create_resp.status_code, 201)
        created = create_resp.json()
        self.assertEqual(created["name"], "Luống Kiểm Thử 4D")
        self.assertIn("effective_thresholds", created)
        self.assertEqual(created["effective_thresholds"]["min_temp"], 16.0)

        # Update
        update_resp = self.client.put(
            f"/api/greenhouses/{gh_id}/areas/area-test-4d",
            headers=self.headers,
            json={"custom_min_temp": 17.5},
        )
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.json()["effective_thresholds"]["min_temp"], 17.5)

        # Delete
        del_resp = self.client.delete(
            f"/api/greenhouses/{gh_id}/areas/area-test-4d",
            headers=self.headers,
        )
        self.assertEqual(del_resp.status_code, 204)

    def test_06_esp32_cam_diagnosis_lifecycle_stage_4b(self):
        """Verifies ESP32-CAM trigger, camera log retrieval, and image serving."""
        gh_resp = self.client.get("/api/greenhouses", headers=self.headers)
        gh_id = gh_resp.json()[0]["greenhouse_id"]

        # Find actual camera device in the garden
        devs_resp = self.client.get("/api/devices", headers=self.headers)
        cam_devs = [d for d in devs_resp.json() if d.get("device_type") in ("CAMERA", "CAMERA_NODE")]
        cam_id = cam_devs[0]["device_id"] if cam_devs else "ESP32CAM-CHILI-01"

        # 1. Trigger capture command (MQTT)
        trigger_resp = self.client.post(
            "/api/camera/capture-trigger",
            headers=self.headers,
            json={"device_id": cam_id, "greenhouse_id": gh_id},
        )
        self.assertEqual(trigger_resp.status_code, 200)
        self.assertEqual(trigger_resp.json()["greenhouse_id"], gh_id)
        self.assertIn("message", trigger_resp.json())

        # 2. Query logs
        logs_resp = self.client.get(
            f"/api/camera/logs?greenhouse_id={gh_id}&limit=10",
            headers=self.headers,
        )
        self.assertEqual(logs_resp.status_code, 200)
        logs = logs_resp.json()
        self.assertIsInstance(logs, list)

        if logs:
            first_log = logs[0]
            log_id = first_log["log_id"]

            # 3. Patch log status
            patch_resp = self.client.patch(
                f"/api/camera/logs/{log_id}/status",
                headers=self.headers,
                json={"status": "REVIEWED"},
            )
            self.assertEqual(patch_resp.status_code, 200)
            self.assertEqual(patch_resp.json()["status"], "REVIEWED")


if __name__ == "__main__":
    unittest.main()
