"""
Integration tests for the projects API.

These tests use a real PostgreSQL database (agentforge_test) and a real
FastAPI test client.  The orchestrator is mocked to avoid LLM calls and
long-running background tasks.
"""
import uuid
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import ProjectStatus, RunStatus
from app.models.auth import User, UserRole
from tests.auth_fixtures import create_authenticated_user, get_jwt_headers


# ─── Project CRUD ─────────────────────────────────────────────────────────────

class TestProjectCRUD:
    @pytest.mark.asyncio
    async def test_create_project_success(
        self, client: AsyncClient, sample_project_data: dict, db_session: AsyncSession
    ):
        # Create authenticated user
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        response = await client.post("/api/v1/projects/", json=sample_project_data, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"]            == sample_project_data["name"]
        assert data["description"]     == sample_project_data["description"]
        assert data["target_language"] == sample_project_data["target_language"]
        assert data["status"]          == "pending"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_create_project_requires_auth(self, client: AsyncClient, sample_project_data: dict):
        """Test that creating projects requires authentication."""
        response = await client.post("/api/v1/projects/", json=sample_project_data)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_project_rejects_short_requirements(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        response = await client.post(
            "/api/v1/projects/",
            json={
                "name":             "Short",
                "description":      "A valid description",
                "requirements":     "Too short",
                "target_language":  "Python",
            },
            headers=headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_project_rejects_missing_fields(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        response = await client.post("/api/v1/projects/", json={"name": "Only name"}, headers=headers)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_projects_returns_user_projects_only(
        self, client: AsyncClient, sample_project_data: dict, db_session: AsyncSession
    ):
        # Create two users
        user1 = await create_authenticated_user(db_session, email="user1@test.com", username="user1")
        user2 = await create_authenticated_user(db_session, email="user2@test.com", username="user2")
        
        headers1 = await get_jwt_headers(user1)
        headers2 = await get_jwt_headers(user2)
        
        # Create projects for each user
        await client.post("/api/v1/projects/", json=sample_project_data, headers=headers1)
        await client.post(
            "/api/v1/projects/",
            json={**sample_project_data, "name": "Second Project"},
            headers=headers2,
        )

        # User1 should only see their project
        response = await client.get("/api/v1/projects/", headers=headers1)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == sample_project_data["name"]

    @pytest.mark.asyncio
    async def test_list_projects_requires_auth(self, client: AsyncClient):
        """Test that listing projects requires authentication."""
        response = await client.get("/api/v1/projects/")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_projects_pagination(
        self, client: AsyncClient, sample_project_data: dict, db_session: AsyncSession
    ):
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        # Create 3 projects
        for i in range(3):
            await client.post(
                "/api/v1/projects/",
                json={**sample_project_data, "name": f"Pagination Test {i}"},
                headers=headers,
            )

        response = await client.get("/api/v1/projects/?limit=2", headers=headers)
        assert response.status_code == 200
        assert len(response.json()) <= 2

    @pytest.mark.asyncio
    async def test_get_project_success(
        self, client: AsyncClient, sample_project_data: dict, db_session: AsyncSession
    ):
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        create = await client.post("/api/v1/projects/", json=sample_project_data, headers=headers)
        project_id = create.json()["id"]

        response = await client.get(f"/api/v1/projects/{project_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["id"] == project_id

    @pytest.mark.asyncio
    async def test_get_project_access_denied_different_user(
        self, client: AsyncClient, sample_project_data: dict, db_session: AsyncSession
    ):
        """Test that users cannot access other users' projects."""
        user1 = await create_authenticated_user(db_session, email="user1@test.com", username="user1")
        user2 = await create_authenticated_user(db_session, email="user2@test.com", username="user2")
        
        headers1 = await get_jwt_headers(user1)
        headers2 = await get_jwt_headers(user2)
        
        # Create project as user1
        create = await client.post("/api/v1/projects/", json=sample_project_data, headers=headers1)
        project_id = create.json()["id"]

        # User2 should not be able to access it
        response = await client.get(f"/api/v1/projects/{project_id}", headers=headers2)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_project_requires_auth(self, client: AsyncClient):
        """Test that getting a project requires authentication."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/projects/{fake_id}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, client: AsyncClient, db_session: AsyncSession):
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/projects/{fake_id}", headers=headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_project_invalid_uuid(self, client: AsyncClient, db_session: AsyncSession):
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        response = await client.get("/api/v1/projects/not-a-uuid", headers=headers)
        assert response.status_code == 422


# ─── Run Management ────────────────────────────────────────────────────────────

class TestRunManagement:
    @pytest.mark.asyncio
    async def test_start_run_creates_running_run(
        self, client: AsyncClient, sample_project_data: dict, mock_orchestrator, db_session: AsyncSession
    ):
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        create = await client.post("/api/v1/projects/", json=sample_project_data, headers=headers)
        project_id = create.json()["id"]

        with patch(
            "app.api.routes.projects.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            response = await client.post(f"/api/v1/projects/{project_id}/runs", headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data["status"]     == "running"
        assert data["project_id"] == project_id
        assert "thread_id" in data
        assert "id" in data

    @pytest.mark.asyncio
    async def test_start_run_requires_auth(self, client: AsyncClient):
        """Test that starting runs requires authentication."""
        fake_id = str(uuid.uuid4())
        response = await client.post(f"/api/v1/projects/{fake_id}/runs")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_start_run_on_nonexistent_project(self, client: AsyncClient, db_session: AsyncSession):
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        fake_id = str(uuid.uuid4())
        response = await client.post(f"/api/v1/projects/{fake_id}/runs", headers=headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_start_run_access_denied_different_user(
        self, client: AsyncClient, sample_project_data: dict, db_session: AsyncSession
    ):
        """Test that users cannot start runs on other users' projects."""
        user1 = await create_authenticated_user(db_session, email="user1@test.com", username="user1")
        user2 = await create_authenticated_user(db_session, email="user2@test.com", username="user2")
        
        headers1 = await get_jwt_headers(user1)
        headers2 = await get_jwt_headers(user2)
        
        # Create project as user1
        create = await client.post("/api/v1/projects/", json=sample_project_data, headers=headers1)
        project_id = create.json()["id"]

        # User2 should not be able to start a run
        response = await client.post(f"/api/v1/projects/{project_id}/runs", headers=headers2)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_runs_for_project(
        self, client: AsyncClient, sample_project_data: dict, mock_orchestrator, db_session: AsyncSession
    ):
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        create = await client.post("/api/v1/projects/", json=sample_project_data, headers=headers)
        project_id = create.json()["id"]

        with patch(
            "app.api.routes.projects.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            await client.post(f"/api/v1/projects/{project_id}/runs", headers=headers)

        response = await client.get(f"/api/v1/projects/{project_id}/runs", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1

    @pytest.mark.asyncio
    async def test_list_runs_requires_auth(self, client: AsyncClient):
        """Test that listing runs requires authentication."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/projects/{fake_id}/runs")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_run_with_events(
        self, client: AsyncClient, sample_project_data: dict, mock_orchestrator, db_session: AsyncSession
    ):
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        create = await client.post("/api/v1/projects/", json=sample_project_data, headers=headers)
        project_id = create.json()["id"]

        with patch(
            "app.api.routes.projects.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            run_resp = await client.post(f"/api/v1/projects/{project_id}/runs", headers=headers)
            run_id = run_resp.json()["id"]

        response = await client.get(f"/api/v1/projects/{project_id}/runs/{run_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"]         == run_id
        assert data["project_id"] == project_id
        assert "events" in data

    @pytest.mark.asyncio
    async def test_get_run_requires_auth(self, client: AsyncClient):
        """Test that getting runs requires authentication."""
        fake_project_id = str(uuid.uuid4())
        fake_run_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/projects/{fake_project_id}/runs/{fake_run_id}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_nonexistent_run(
        self, client: AsyncClient, sample_project_data: dict, db_session: AsyncSession
    ):
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        create = await client.post("/api/v1/projects/", json=sample_project_data, headers=headers)
        project_id = create.json()["id"]
        fake_run_id = str(uuid.uuid4())

        response = await client.get(
            f"/api/v1/projects/{project_id}/runs/{fake_run_id}", headers=headers
        )
        assert response.status_code == 404


# ─── Human Feedback ────────────────────────────────────────────────────────────

class TestHumanFeedback:
    @pytest.mark.asyncio
    async def test_submit_feedback_to_non_waiting_run_returns_400(
        self, client: AsyncClient, sample_project_data: dict, mock_orchestrator, db_session: AsyncSession
    ):
        """Submitting feedback to a RUNNING run should be rejected."""
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        create = await client.post("/api/v1/projects/", json=sample_project_data, headers=headers)
        project_id = create.json()["id"]

        with patch(
            "app.api.routes.projects.get_orchestrator",
            return_value=mock_orchestrator,
        ):
            run_resp = await client.post(f"/api/v1/projects/{project_id}/runs", headers=headers)
            run_id   = run_resp.json()["id"]

        # Run is in "running" status — feedback should be rejected
        feedback_resp = await client.post(
            f"/api/v1/projects/{project_id}/runs/{run_id}/feedback",
            json={"action": "approve"},
            headers=headers,
        )
        assert feedback_resp.status_code == 400
        assert "not waiting for review" in feedback_resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_submit_feedback_requires_auth(self, client: AsyncClient):
        """Test that submitting feedback requires authentication."""
        fake_project_id = str(uuid.uuid4())
        fake_run_id = str(uuid.uuid4())
        response = await client.post(
            f"/api/v1/projects/{fake_project_id}/runs/{fake_run_id}/feedback",
            json={"action": "approve"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_feedback_action_validation(
        self, client: AsyncClient, sample_project_data: dict, db_session: AsyncSession
    ):
        """Feedback action must be one of approve/modify/reject."""
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        create = await client.post("/api/v1/projects/", json=sample_project_data, headers=headers)
        project_id = create.json()["id"]
        fake_run_id = str(uuid.uuid4())

        response = await client.post(
            f"/api/v1/projects/{project_id}/runs/{fake_run_id}/feedback",
            json={"action": "invalid_action"},
            headers=headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_feedback_on_nonexistent_run(
        self, client: AsyncClient, sample_project_data: dict, db_session: AsyncSession
    ):
        user = await create_authenticated_user(db_session)
        headers = await get_jwt_headers(user)
        
        create = await client.post("/api/v1/projects/", json=sample_project_data, headers=headers)
        project_id = create.json()["id"]
        fake_run_id = str(uuid.uuid4())

        response = await client.post(
            f"/api/v1/projects/{project_id}/runs/{fake_run_id}/feedback",
            json={"action": "approve"},
            headers=headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_feedback_access_denied_different_user(
        self, client: AsyncClient, sample_project_data: dict, mock_orchestrator, db_session: AsyncSession
    ):
        """Test that users cannot submit feedback on other users' projects."""
        user1 = await create_authenticated_user(db_session, email="user1@test.com", username="user1")
        user2 = await create_authenticated_user(db_session, email="user2@test.com", username="user2")
        
        headers1 = await get_jwt_headers(user1)
        headers2 = await get_jwt_headers(user2)
        
        # Create project and run as user1
        create = await client.post("/api/v1/projects/", json=sample_project_data, headers=headers1)
        project_id = create.json()["id"]

        with patch("app.api.routes.projects.get_orchestrator", return_value=mock_orchestrator):
            run_resp = await client.post(f"/api/v1/projects/{project_id}/runs", headers=headers1)
            run_id = run_resp.json()["id"]

        # User2 should not be able to submit feedback
        response = await client.post(
            f"/api/v1/projects/{project_id}/runs/{run_id}/feedback",
            json={"action": "approve"},
            headers=headers2,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_cancel_run_requires_auth(self, client: AsyncClient):
        """Test that cancelling runs requires authentication."""
        fake_project_id = str(uuid.uuid4())
        fake_run_id = str(uuid.uuid4())
        response = await client.post(f"/api/v1/projects/{fake_project_id}/runs/{fake_run_id}/cancel")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_cancel_run_access_denied_different_user(
        self, client: AsyncClient, sample_project_data: dict, mock_orchestrator, db_session: AsyncSession
    ):
        """Test that users cannot cancel other users' runs."""
        user1 = await create_authenticated_user(db_session, email="user1@test.com", username="user1")
        user2 = await create_authenticated_user(db_session, email="user2@test.com", username="user2")
        
        headers1 = await get_jwt_headers(user1)
        headers2 = await get_jwt_headers(user2)
        
        # Create project and run as user1
        create = await client.post("/api/v1/projects/", json=sample_project_data, headers=headers1)
        project_id = create.json()["id"]

        with patch("app.api.routes.projects.get_orchestrator", return_value=mock_orchestrator):
            run_resp = await client.post(f"/api/v1/projects/{project_id}/runs", headers=headers1)
            run_id = run_resp.json()["id"]

        # User2 should not be able to cancel the run
        response = await client.post(
            f"/api/v1/projects/{project_id}/runs/{run_id}/cancel",
            headers=headers2,
        )
        assert response.status_code == 403


# ─── Health Check ─────────────────────────────────────────────────────────────

class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_endpoint_returns_200(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"]  == "healthy"
        assert data["service"] == "agentforge-api"

    @pytest.mark.asyncio
    async def test_health_endpoint_includes_env(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert "env" in response.json()


# ─── Apply Result Helper ──────────────────────────────────────────────────────

class TestApplyResultToRun:
    """Unit tests for the _apply_result_to_run helper function."""

    def _make_run(self):
        from app.models.project import ProjectRun
        run = ProjectRun()
        run.id = uuid.uuid4()
        run.status = RunStatus.RUNNING
        run.interrupt_payload = None
        run.error_message = None
        run.completed_at = None
        return run

    def _make_project(self):
        from app.models.project import Project
        project = Project()
        project.id = uuid.uuid4()
        project.status = ProjectStatus.RUNNING
        return project

    def test_apply_interrupted_result(self):
        from app.api.routes.projects import _apply_result_to_run
        run = self._make_run()
        project = self._make_project()
        _apply_result_to_run(
            run, project,
            {
                "status":           "interrupted",
                "interrupt_payload": {"step": "requirements_analysis"},
            },
        )
        assert run.status            == RunStatus.WAITING_REVIEW
        assert run.interrupt_payload == {"step": "requirements_analysis"}
        assert project.status        == ProjectStatus.WAITING_REVIEW

    def test_apply_completed_result(self):
        from app.api.routes.projects import _apply_result_to_run
        run     = self._make_run()
        project = self._make_project()
        _apply_result_to_run(run, project, {"status": "completed", "interrupt_payload": None})
        assert run.status     == RunStatus.COMPLETED
        assert run.completed_at is not None
        assert project.status == ProjectStatus.COMPLETED

    def test_apply_cancelled_result(self):
        from app.api.routes.projects import _apply_result_to_run
        run     = self._make_run()
        project = self._make_project()
        _apply_result_to_run(
            run, project,
            {"status": "cancelled", "interrupt_payload": None, "error": "Rejected"},
        )
        assert run.status        == RunStatus.CANCELLED
        assert run.error_message == "Rejected"
        assert project.status    == ProjectStatus.CANCELLED

    def test_apply_failed_result(self):
        from app.api.routes.projects import _apply_result_to_run
        run     = self._make_run()
        project = self._make_project()
        _apply_result_to_run(
            run, project,
            {"status": "failed", "interrupt_payload": None, "error": "LLM error"},
        )
        assert run.status        == RunStatus.FAILED
        assert run.error_message == "LLM error"
        assert project.status    == ProjectStatus.FAILED

    def test_apply_result_with_no_project(self):
        """Should not raise when project is None."""
        from app.api.routes.projects import _apply_result_to_run
        run = self._make_run()
        _apply_result_to_run(run, None, {"status": "completed", "interrupt_payload": None})
        assert run.status == RunStatus.COMPLETED
