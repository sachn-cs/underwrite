"""Locust load test for ULU API endpoints.

Item 70 from production roadmap.

Usage:
    locust -f locustfile.py --host http://localhost:8000
"""

from locust import HttpUser, between, task


class UluUser(HttpUser):
    """Simulates borrowers and sponsors interacting with the ULU API."""

    wait_time = between(1, 5)

    def on_start(self) -> None:
        """Seeds the system before each simulated user starts."""
        self.client.post("/seed", json={"user": "seed", "base_budget": 1000.0})
        self.client.post("/user", json={"sponsor": "seed", "user": "lsp", "delegation_amount": 500.0})
        self.client.post("/user", json={"sponsor": "lsp", "user": "borrower", "delegation_amount": 200.0})

    @task(3)
    def get_health(self) -> None:
        self.client.get("/health")

    @task(2)
    def get_ready(self) -> None:
        self.client.get("/ready")

    @task(2)
    def get_quote(self) -> None:
        self.client.post(
            "/quote",
            json={
                "borrower": "borrower",
                "principal": 5.0,
                "term": 1.0,
                "default_probability": 0.2,
                "protocol_rate": 0.3,
                "max_delegation_rate": 0.1,
            },
        )

    @task(1)
    def originate_loan(self) -> None:
        self.client.post(
            "/originate",
            json={
                "borrower": "borrower",
                "principal": 5.0,
                "term": 1.0,
                "default_probability": 0.2,
                "protocol_rate": 0.3,
                "max_delegation_rate": 0.1,
            },
        )

    @task(1)
    def repay(self) -> None:
        self.client.post("/repay", json={"user": "borrower", "delta_earned": 1.0})

    @task(1)
    def get_ledger(self) -> None:
        self.client.get("/ledger")

    @task(1)
    def get_metrics(self) -> None:
        self.client.get("/metrics")
