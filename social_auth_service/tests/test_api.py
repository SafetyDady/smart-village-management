"""
Test suite for Social Auth Service
"""

import pytest
import json
from src.main import app
from src.models.user import db, User, Village, House


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()


@pytest.fixture
def sample_village(client):
    """Create sample village for testing"""
    with app.app_context():
        village = Village(name="Test Village", description="A test village")
        db.session.add(village)
        db.session.commit()
        return village


@pytest.fixture
def sample_house(client, sample_village):
    """Create sample house for testing"""
    with app.app_context():
        house = House(
            village_id=sample_village.id,
            house_number="001",
            address="123 Test Street"
        )
        db.session.add(house)
        db.session.commit()
        return house


@pytest.fixture
def super_admin_user(client):
    """Create super admin user for testing"""
    with app.app_context():
        user = User(
            email="admin@smartvillage.com",
            social_id="super_admin_123",
            social_provider="google",
            first_name="Super",
            last_name="Admin",
            role="super_admin",
            status="active"
        )
        db.session.add(user)
        db.session.commit()
        return user


class TestAuth:
    """Test authentication endpoints"""
    
    def test_social_login_new_user(self, client):
        """Test social login with new user"""
        # Mock social login data
        login_data = {
            "token": "mock_token_123",
            "provider": "google"
        }
        
        # Note: This will fail without actual token verification
        # In real tests, we would mock the SocialLoginHandler
        response = client.post('/auth/social-login', 
                             data=json.dumps(login_data),
                             content_type='application/json')
        
        # Should return 401 due to invalid token (expected in test)
        assert response.status_code == 401
    
    def test_email_login_nonexistent_user(self, client):
        """Test email login with non-existent user"""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "password123"
        }
        
        response = client.post('/auth/email-login',
                             data=json.dumps(login_data),
                             content_type='application/json')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['message'] == "Invalid credentials"


class TestUserManagement:
    """Test user management endpoints"""
    
    def test_get_villages(self, client, sample_village):
        """Test getting list of villages"""
        response = client.get('/user/villages')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'villages' in data
        assert len(data['villages']) == 1
        assert data['villages'][0]['name'] == "Test Village"
    
    def test_get_village_houses(self, client, sample_village, sample_house):
        """Test getting houses in a village"""
        response = client.get(f'/user/villages/{sample_village.id}/houses')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'village' in data
        assert 'houses' in data
        assert len(data['houses']) == 1
        assert data['houses'][0]['house_number'] == "001"


class TestAdminFunctions:
    """Test admin functionality"""
    
    def test_get_villages_endpoint(self, client, sample_village):
        """Test admin village management"""
        response = client.get('/village_house/villages')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'villages' in data
        assert len(data['villages']) == 1


class TestDatabase:
    """Test database models and relationships"""
    
    def test_user_model(self, client):
        """Test User model creation and methods"""
        with app.app_context():
            user = User(
                email="test@example.com",
                social_id="test_123",
                social_provider="google",
                first_name="Test",
                last_name="User",
                role="household_member",
                status="pending_details"
            )
            
            db.session.add(user)
            db.session.commit()
            
            # Test to_dict method
            user_dict = user.to_dict()
            assert user_dict['email'] == "test@example.com"
            assert user_dict['role'] == "household_member"
            assert user_dict['status'] == "pending_details"
    
    def test_village_house_relationship(self, client, sample_village):
        """Test Village and House relationship"""
        with app.app_context():
            house = House(
                village_id=sample_village.id,
                house_number="002",
                address="456 Test Avenue"
            )
            
            db.session.add(house)
            db.session.commit()
            
            # Test relationship
            houses = House.query.filter_by(village_id=sample_village.id).all()
            assert len(houses) == 1
            assert houses[0].house_number == "002"


if __name__ == '__main__':
    pytest.main([__file__])

