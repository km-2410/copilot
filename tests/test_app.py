import pytest
from fastapi.testclient import TestClient
from src.app import app, activities

# Create a test client
client = TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities to initial state before each test"""
    original_activities = {
        name: {
            "description": details["description"],
            "schedule": details["schedule"],
            "max_participants": details["max_participants"],
            "participants": details["participants"].copy()
        }
        for name, details in activities.items()
    }
    yield
    # Reset after test
    for name in activities:
        activities[name]["participants"] = original_activities[name]["participants"].copy()


class TestGetActivities:
    """Tests for GET /activities endpoint"""

    def test_get_activities_success(self):
        """Test successfully fetching all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "Chess Club" in data
        assert "Programming Class" in data

    def test_get_activities_has_required_fields(self):
        """Test that activities have all required fields"""
        response = client.get("/activities")
        data = response.json()
        activity = data["Chess Club"]
        
        assert "description" in activity
        assert "schedule" in activity
        assert "max_participants" in activity
        assert "participants" in activity

    def test_get_activities_participants_is_list(self):
        """Test that participants field is a list"""
        response = client.get("/activities")
        data = response.json()
        activity = data["Chess Club"]
        
        assert isinstance(activity["participants"], list)


class TestSignupForActivity:
    """Tests for POST /activities/{activity_name}/signup endpoint"""

    def test_signup_success(self, reset_activities):
        """Test successfully signing up for an activity"""
        response = client.post(
            "/activities/Chess%20Club/signup?email=newstudent@test.com"
        )
        assert response.status_code == 200
        data = response.json()
        assert "Signed up" in data["message"]
        assert "newstudent@test.com" in data["message"]

    def test_signup_adds_participant(self, reset_activities):
        """Test that signup actually adds participant to list"""
        response = client.post(
            "/activities/Chess%20Club/signup?email=newstudent@test.com"
        )
        assert response.status_code == 200
        
        # Verify participant was added
        activities_response = client.get("/activities")
        activity_data = activities_response.json()
        assert "newstudent@test.com" in activity_data["Chess Club"]["participants"]

    def test_signup_duplicate_email(self, reset_activities):
        """Test that duplicate signups are rejected"""
        # First signup
        client.post(
            "/activities/Chess%20Club/signup?email=duplicate@test.com"
        )
        
        # Attempt duplicate signup
        response = client.post(
            "/activities/Chess%20Club/signup?email=duplicate@test.com"
        )
        assert response.status_code == 400
        data = response.json()
        assert "already signed up" in data["detail"]

    def test_signup_nonexistent_activity(self, reset_activities):
        """Test signup for non-existent activity"""
        response = client.post(
            "/activities/FakeActivity/signup?email=test@test.com"
        )
        assert response.status_code == 404
        data = response.json()
        assert "Activity not found" in data["detail"]

    def test_signup_preserves_existing_participants(self, reset_activities):
        """Test that new signup doesn't overwrite existing participants"""
        # Get initial participant count for Chess Club
        activities_response = client.get("/activities")
        initial_participants = activities_response.json()["Chess Club"]["participants"].copy()
        
        # Sign up new student
        client.post("/activities/Chess%20Club/signup?email=newstudent@test.com")
        
        # Verify all participants are present
        activities_response = client.get("/activities")
        final_participants = activities_response.json()["Chess Club"]["participants"]
        
        for participant in initial_participants:
            assert participant in final_participants
        assert "newstudent@test.com" in final_participants


class TestUnregisterFromActivity:
    """Tests for DELETE /activities/{activity_name}/unregister endpoint"""

    def test_unregister_success(self, reset_activities):
        """Test successfully unregistering from an activity"""
        # First signup
        client.post(
            "/activities/Chess%20Club/signup?email=teststudent@test.com"
        )
        
        # Then unregister
        response = client.delete(
            "/activities/Chess%20Club/unregister?email=teststudent@test.com"
        )
        assert response.status_code == 200
        data = response.json()
        assert "Unregistered" in data["message"]

    def test_unregister_removes_participant(self, reset_activities):
        """Test that unregister actually removes participant"""
        # Signup
        client.post(
            "/activities/Chess%20Club/signup?email=teststudent@test.com"
        )
        
        # Unregister
        client.delete(
            "/activities/Chess%20Club/unregister?email=teststudent@test.com"
        )
        
        # Verify participant was removed
        activities_response = client.get("/activities")
        activity_data = activities_response.json()
        assert "teststudent@test.com" not in activity_data["Chess Club"]["participants"]

    def test_unregister_nonexistent_activity(self, reset_activities):
        """Test unregister from non-existent activity"""
        response = client.delete(
            "/activities/FakeActivity/unregister?email=test@test.com"
        )
        assert response.status_code == 404
        data = response.json()
        assert "Activity not found" in data["detail"]

    def test_unregister_not_signed_up(self, reset_activities):
        """Test unregistering when not signed up"""
        response = client.delete(
            "/activities/Chess%20Club/unregister?email=notsignedup@test.com"
        )
        assert response.status_code == 400
        data = response.json()
        assert "not signed up" in data["detail"]

    def test_unregister_existing_participant(self, reset_activities):
        """Test unregistering an existing participant"""
        # Get initial participants
        activities_response = client.get("/activities")
        initial_count = len(activities_response.json()["Chess Club"]["participants"])
        
        # Unregister an existing participant
        existing_email = activities_response.json()["Chess Club"]["participants"][0]
        response = client.delete(
            f"/activities/Chess%20Club/unregister?email={existing_email}"
        )
        
        assert response.status_code == 200
        
        # Verify count decreased
        activities_response = client.get("/activities")
        final_count = len(activities_response.json()["Chess Club"]["participants"])
        assert final_count == initial_count - 1


class TestRootEndpoint:
    """Tests for GET / endpoint"""

    def test_root_redirects(self):
        """Test that root endpoint redirects"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert "/static/index.html" in response.headers["location"]


class TestIntegrationScenarios:
    """Integration tests for complete user workflows"""

    def test_signup_unregister_signup_again(self, reset_activities):
        """Test signing up, unregistering, and signing up again"""
        email = "integration@test.com"
        activity = "Programming%20Class"
        
        # First signup
        response1 = client.post(f"/activities/{activity}/signup?email={email}")
        assert response1.status_code == 200
        
        # Verify participant was added
        activities_response = client.get("/activities")
        assert email in activities_response.json()["Programming Class"]["participants"]
        
        # Unregister
        response2 = client.delete(f"/activities/{activity}/unregister?email={email}")
        assert response2.status_code == 200
        
        # Verify participant was removed
        activities_response = client.get("/activities")
        assert email not in activities_response.json()["Programming Class"]["participants"]
        
        # Sign up again
        response3 = client.post(f"/activities/{activity}/signup?email={email}")
        assert response3.status_code == 200
        
        # Verify participant was added again
        activities_response = client.get("/activities")
        assert email in activities_response.json()["Programming Class"]["participants"]

    def test_multiple_signups_same_student_different_activities(self, reset_activities):
        """Test student can sign up for multiple activities"""
        email = "multiactivity@test.com"
        
        # Sign up for multiple activities
        response1 = client.post("/activities/Chess%20Club/signup?email=" + email)
        assert response1.status_code == 200
        
        response2 = client.post("/activities/Programming%20Class/signup?email=" + email)
        assert response2.status_code == 200
        
        # Verify student is in both activities
        activities_response = client.get("/activities")
        data = activities_response.json()
        assert email in data["Chess Club"]["participants"]
        assert email in data["Programming Class"]["participants"]
