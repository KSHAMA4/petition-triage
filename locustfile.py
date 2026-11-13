from locust import HttpUser, task, between
import json

class StudentPetitionUser(HttpUser):
    # Simulates realistic human arrival delay between 1 and 3 seconds
    wait_time = between(1, 3)

    @task(3)
    def submit_standard_petition(self):
        """Submit the difficult 4.1 scenario (attendance 68%, medical)."""
        payload = {
            "petition_id": "LOCUST_4_1",
            "student_ref": "SYN0001",
            "petition_type": "attendance",
            "semester": 3,
            "attendance_percentage": 68.0,
            "has_medical_documentation": True,
            "description": "I was hospitalised during the semester and my attendance is 68 percent. My medical certificate is attached."
        }
        with self.client.post("/petitions", json=payload, catch_response=True) as resp:
            if resp.status_code == 202:
                run_id = resp.json().get("run_id")
                # Poll for completion
                if run_id:
                    self.client.get(f"/runs/{run_id}", name="/runs/[id]")
                resp.success()
            else:
                resp.failure(f"Expected 202, got {resp.status_code}")

    @task(1)
    def submit_malformed_petition(self):
        """Submit an invalid petition to test ingestion quarantine under load (D1)."""
        bad_payload = {
            "petition_id": "BAD_SEMESTER",
            "student_ref": "SYN9999",
            "petition_type": "attendance",
            "semester": 14,
            "description": "Invalid petition testing boundary quarantine."
        }
        with self.client.post("/petitions", json=bad_payload, catch_response=True) as resp:
            if resp.status_code == 422:
                resp.success()
            else:
                resp.failure(f"Expected 422 quarantine, got {resp.status_code}")

    @task(1)
    def check_health_and_metrics(self):
        """Monitor API health and queue metrics."""
        self.client.get("/health", name="/health")
        self.client.get("/metrics", name="/metrics")
