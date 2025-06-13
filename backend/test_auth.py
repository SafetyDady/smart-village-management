import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

from src.main import app
from src.database import get_db, Base
from src.models import models
from src.utils import auth

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(app)

@pytest.fixture(scope="module")
def setup_database():
    """Setup test database"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def test_user_data():
    """Test user data"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "phone": "0812345678",
        "password": "TestPassword123",
        "village_id": "550e8400-e29b-41d4-a716-446655440000"
    }

@pytest.fixture
def test_db():
    """Get test database session"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

class TestUserRegistration:
    """Test user registration functionality"""
    
    def test_register_new_user(self, setup_database, test_user_data):
        """Test successful user registration"""
        response = client.post("/auth/register", json=test_user_data)
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "User registered successfully"
        assert "user" in data
        assert data["user"]["username"] == test_user_data["username"]
        assert data["user"]["email"] == test_user_data["email"]
    
    def test_register_duplicate_username(self, setup_database, test_user_data):
        """Test registration with duplicate username"""
        # First registration
        client.post("/auth/register", json=test_user_data)
        
        # Second registration with same username
        duplicate_data = test_user_data.copy()
        duplicate_data["email"] = "different@example.com"
        response = client.post("/auth/register", json=duplicate_data)
        assert response.status_code == 400
        assert "username" in response.json()["detail"].lower()
    
    def test_register_duplicate_email(self, setup_database, test_user_data):
        """Test registration with duplicate email"""
        # First registration
        client.post("/auth/register", json=test_user_data)
        
        # Second registration with same email
        duplicate_data = test_user_data.copy()
        duplicate_data["username"] = "differentuser"
        response = client.post("/auth/register", json=duplicate_data)
        assert response.status_code == 400
        assert "email" in response.json()["detail"].lower()
    
    def test_register_invalid_email(self, setup_database, test_user_data):
        """Test registration with invalid email"""
        invalid_data = test_user_data.copy()
        invalid_data["email"] = "invalid-email"
        response = client.post("/auth/register", json=invalid_data)
        assert response.status_code == 422
    
    def test_register_weak_password(self, setup_database, test_user_data):
        """Test registration with weak password"""
        weak_data = test_user_data.copy()
        weak_data["password"] = "123"
        response = client.post("/auth/register", json=weak_data)
        assert response.status_code == 400
        assert "password" in response.json()["detail"].lower()

class TestUserLogin:
    """Test user login functionality"""
    
    def test_login_success(self, setup_database, test_user_data, test_db):
        """Test successful login"""
        # Register user first
        client.post("/auth/register", json=test_user_data)
        
        # Verify email (simulate)
        user = test_db.query(models.User).filter(models.User.email == test_user_data["email"]).first()
        user.email_verified = True
        test_db.commit()
        
        # Login
        login_data = {
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        }
        response = client.post("/auth/token", data=login_data)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_invalid_credentials(self, setup_database, test_user_data):
        """Test login with invalid credentials"""
        # Register user first
        client.post("/auth/register", json=test_user_data)
        
        # Login with wrong password
        login_data = {
            "username": test_user_data["username"],
            "password": "wrongpassword"
        }
        response = client.post("/auth/token", data=login_data)
        assert response.status_code == 401
    
    def test_login_unverified_email(self, setup_database, test_user_data):
        """Test login with unverified email"""
        # Register user first
        client.post("/auth/register", json=test_user_data)
        
        # Login without email verification
        login_data = {
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        }
        response = client.post("/auth/token", data=login_data)
        assert response.status_code == 401
        assert "verify" in response.json()["detail"].lower()
    
    def test_brute_force_protection(self, setup_database, test_user_data, test_db):
        """Test brute force protection"""
        # Register user first
        client.post("/auth/register", json=test_user_data)
        
        # Verify email
        user = test_db.query(models.User).filter(models.User.email == test_user_data["email"]).first()
        user.email_verified = True
        test_db.commit()
        
        # Try to login with wrong password 5 times
        login_data = {
            "username": test_user_data["username"],
            "password": "wrongpassword"
        }
        
        for i in range(5):
            response = client.post("/auth/token", data=login_data)
            assert response.status_code == 401
        
        # 6th attempt should result in account lock
        response = client.post("/auth/token", data=login_data)
        assert response.status_code == 423  # HTTP_423_LOCKED

class TestPasswordReset:
    """Test password reset functionality"""
    
    def test_forgot_password_request(self, setup_database, test_user_data):
        """Test forgot password request"""
        # Register user first
        client.post("/auth/register", json=test_user_data)
        
        # Request password reset
        response = client.post("/auth/forgot-password", json={"email": test_user_data["email"]})
        assert response.status_code == 200
        assert "message" in response.json()
    
    def test_forgot_password_nonexistent_email(self, setup_database):
        """Test forgot password with non-existent email"""
        response = client.post("/auth/forgot-password", json={"email": "nonexistent@example.com"})
        # Should still return success for security
        assert response.status_code == 200
    
    def test_reset_password_invalid_token(self, setup_database):
        """Test password reset with invalid token"""
        reset_data = {
            "token": "invalid-token",
            "new_password": "NewPassword123"
        }
        response = client.post("/auth/reset-password", json=reset_data)
        assert response.status_code == 400

class TestEmailVerification:
    """Test email verification functionality"""
    
    def test_send_verification_email(self, setup_database, test_user_data):
        """Test sending verification email"""
        # Register user first
        client.post("/auth/register", json=test_user_data)
        
        # Send verification email
        response = client.post("/auth/send-verification-email", json={"email": test_user_data["email"]})
        assert response.status_code == 200
    
    def test_verify_email_invalid_token(self, setup_database):
        """Test email verification with invalid token"""
        response = client.post("/auth/verify-email", json={"token": "invalid-token"})
        assert response.status_code == 400

class TestPasswordStrength:
    """Test password strength checking"""
    
    def test_strong_password(self, setup_database):
        """Test strong password check"""
        response = client.post("/auth/check-password-strength", json={"password": "StrongPassword123!"})
        assert response.status_code == 200
        data = response.json()
        assert data["strength"] == "strong"
        assert data["is_acceptable"] == True
    
    def test_weak_password(self, setup_database):
        """Test weak password check"""
        response = client.post("/auth/check-password-strength", json={"password": "123"})
        assert response.status_code == 200
        data = response.json()
        assert data["strength"] == "weak"
        assert data["is_acceptable"] == False
    
    def test_medium_password(self, setup_database):
        """Test medium password check"""
        response = client.post("/auth/check-password-strength", json={"password": "Password123"})
        assert response.status_code == 200
        data = response.json()
        assert data["strength"] in ["medium", "strong"]

class TestUsernameEmailAvailability:
    """Test username and email availability checking"""
    
    def test_check_available_username(self, setup_database):
        """Test checking available username"""
        response = client.get("/auth/check-username/availableuser")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] == True
    
    def test_check_unavailable_username(self, setup_database, test_user_data):
        """Test checking unavailable username"""
        # Register user first
        client.post("/auth/register", json=test_user_data)
        
        # Check username availability
        response = client.get(f"/auth/check-username/{test_user_data['username']}")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] == False
    
    def test_check_available_email(self, setup_database):
        """Test checking available email"""
        response = client.get("/auth/check-email/available@example.com")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] == True
    
    def test_check_unavailable_email(self, setup_database, test_user_data):
        """Test checking unavailable email"""
        # Register user first
        client.post("/auth/register", json=test_user_data)
        
        # Check email availability
        response = client.get(f"/auth/check-email/{test_user_data['email']}")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] == False

if __name__ == "__main__":
    pytest.main([__file__])

