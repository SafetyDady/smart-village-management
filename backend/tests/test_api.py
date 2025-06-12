import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import uuid
from datetime import datetime, timedelta

from ..src.database import Base, get_db
from ..src.main import app
from ..src.models import models
from ..src.utils import auth

# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the get_db dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(app)

# Setup test data
@pytest.fixture(scope="function")
def setup_test_db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create test data
    db = TestingSessionLocal()
    
    # Create test village
    village_id = uuid.uuid4()
    test_village = models.Village(
        id=village_id,
        name="Test Village",
        address="123 Test Street",
        contact_info={"phone": "123-456-7890", "email": "test@example.com"},
        settings={}
    )
    db.add(test_village)
    
    # Create admin user
    admin_id = uuid.uuid4()
    admin_password_hash = auth.get_password_hash("adminpassword")
    admin_user = models.User(
        id=admin_id,
        village_id=village_id,
        role="admin",
        username="admin",
        password_hash=admin_password_hash,
        email="admin@example.com",
        phone="123-456-7890",
        status="active"
    )
    db.add(admin_user)
    
    # Create resident user
    resident_id = uuid.uuid4()
    resident_password_hash = auth.get_password_hash("residentpassword")
    resident_user = models.User(
        id=resident_id,
        village_id=village_id,
        role="resident",
        username="resident",
        password_hash=resident_password_hash,
        email="resident@example.com",
        phone="123-456-7891",
        status="active"
    )
    db.add(resident_user)
    
    # Create property
    property_id = uuid.uuid4()
    test_property = models.Property(
        id=property_id,
        village_id=village_id,
        address="Unit 101",
        owner_id=resident_id,
        resident_ids=[str(resident_id)],
        status="occupied"
    )
    db.add(test_property)
    
    # Create invoice
    invoice_id = uuid.uuid4()
    test_invoice = models.Invoice(
        id=invoice_id,
        village_id=village_id,
        property_id=property_id,
        amount=600.0,
        due_date=datetime.now() + timedelta(days=30),
        status="pending",
        items=[{"description": "Monthly maintenance fee", "amount": 600.0}]
    )
    db.add(test_invoice)
    
    # Create expense category
    category_id = uuid.uuid4()
    test_category = models.ExpenseCategory(
        id=category_id,
        village_id=village_id,
        name="Maintenance",
        description="General maintenance expenses",
        status="active"
    )
    db.add(test_category)
    
    db.commit()
    db.close()
    
    # Return test data IDs for use in tests
    return {
        "village_id": village_id,
        "admin_id": admin_id,
        "resident_id": resident_id,
        "property_id": property_id,
        "invoice_id": invoice_id,
        "category_id": category_id
    }

# Clean up after tests
@pytest.fixture(scope="function", autouse=True)
def cleanup():
    yield
    Base.metadata.drop_all(bind=engine)

# Test authentication
def test_login(setup_test_db):
    # Test admin login
    response = client.post(
        "/auth/token",
        data={"username": "admin", "password": "adminpassword"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"
    
    # Test resident login
    response = client.post(
        "/auth/token",
        data={"username": "resident", "password": "residentpassword"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    
    # Test invalid login
    response = client.post(
        "/auth/token",
        data={"username": "admin", "password": "wrongpassword"}
    )
    assert response.status_code == 401

# Helper function to get auth token
def get_auth_token(username, password):
    response = client.post(
        "/auth/token",
        data={"username": username, "password": password}
    )
    return response.json()["access_token"]

# Test user endpoints
def test_users_endpoints(setup_test_db):
    # Get admin token
    admin_token = get_auth_token("admin", "adminpassword")
    
    # Get resident token
    resident_token = get_auth_token("resident", "residentpassword")
    
    # Test get all users (admin only)
    response = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert len(response.json()) == 2
    
    # Test resident cannot get all users
    response = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {resident_token}"}
    )
    assert response.status_code == 403
    
    # Test create new user (admin only)
    new_user_data = {
        "village_id": str(setup_test_db["village_id"]),
        "role": "staff",
        "username": "staff1",
        "password": "staffpassword",
        "email": "staff@example.com",
        "phone": "123-456-7892",
        "status": "active"
    }
    
    response = client.post(
        "/users/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=new_user_data
    )
    assert response.status_code == 201
    assert response.json()["username"] == "staff1"
    
    # Test resident cannot create user
    response = client.post(
        "/users/",
        headers={"Authorization": f"Bearer {resident_token}"},
        json=new_user_data
    )
    assert response.status_code == 403

# Test property endpoints
def test_property_endpoints(setup_test_db):
    # Get admin token
    admin_token = get_auth_token("admin", "adminpassword")
    
    # Test get all properties
    response = client.get(
        "/properties/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    
    # Test get property by ID
    response = client.get(
        f"/properties/{setup_test_db['property_id']}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["address"] == "Unit 101"
    
    # Test create new property
    new_property_data = {
        "village_id": str(setup_test_db["village_id"]),
        "address": "Unit 102",
        "status": "vacant"
    }
    
    response = client.post(
        "/properties/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=new_property_data
    )
    assert response.status_code == 201
    assert response.json()["address"] == "Unit 102"

# Test invoice endpoints
def test_invoice_endpoints(setup_test_db):
    # Get admin token
    admin_token = get_auth_token("admin", "adminpassword")
    
    # Test get all invoices
    response = client.get(
        "/invoices/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    
    # Test get invoice by ID
    response = client.get(
        f"/invoices/{setup_test_db['invoice_id']}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["amount"] == 600.0
    
    # Test create new invoice
    new_invoice_data = {
        "village_id": str(setup_test_db["village_id"]),
        "property_id": str(setup_test_db["property_id"]),
        "amount": 800.0,
        "due_date": (datetime.now() + timedelta(days=60)).isoformat(),
        "status": "pending",
        "items": [{"description": "Special assessment", "amount": 800.0}]
    }
    
    response = client.post(
        "/invoices/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=new_invoice_data
    )
    assert response.status_code == 201
    assert response.json()["amount"] == 800.0

# Test payment endpoints
def test_payment_endpoints(setup_test_db):
    # Get admin token
    admin_token = get_auth_token("admin", "adminpassword")
    
    # Test create new payment
    new_payment_data = {
        "invoice_id": str(setup_test_db["invoice_id"]),
        "amount": 600.0,
        "payment_date": datetime.now().isoformat(),
        "payment_method": "bank_transfer",
        "verification": {"notes": "Payment received"}
    }
    
    response = client.post(
        "/payments/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=new_payment_data
    )
    assert response.status_code == 201
    assert response.json()["amount"] == 600.0
    
    # Get payment ID from response
    payment_id = response.json()["id"]
    
    # Test verify payment
    verification_data = {
        "status": "verified",
        "notes": "Payment verified by admin"
    }
    
    response = client.put(
        f"/payments/{payment_id}/verify",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=verification_data
    )
    assert response.status_code == 200
    assert response.json()["status"] == "verified"
    
    # Test get all payments
    response = client.get(
        "/payments/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1

# Test access log endpoints
def test_access_log_endpoints(setup_test_db):
    # Get admin token
    admin_token = get_auth_token("admin", "adminpassword")
    
    # Test create new access log
    new_access_log_data = {
        "village_id": str(setup_test_db["village_id"]),
        "property_id": str(setup_test_db["property_id"]),
        "user_id": str(setup_test_db["resident_id"]),
        "timestamp": datetime.now().isoformat(),
        "direction": "entry",
        "access_method": "mobile_app",
        "status": "granted"
    }
    
    response = client.post(
        "/access/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=new_access_log_data
    )
    assert response.status_code == 201
    assert response.json()["direction"] == "entry"
    
    # Test get all access logs
    response = client.get(
        "/access/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    
    # Test gate access
    gate_access_data = {
        "direction": "entry",
        "property_id": str(setup_test_db["property_id"])
    }
    
    response = client.post(
        "/access/gate-access",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=gate_access_data
    )
    assert response.status_code == 200
    assert response.json()["direction"] == "entry"

# Test expense endpoints
def test_expense_endpoints(setup_test_db):
    # Get admin token
    admin_token = get_auth_token("admin", "adminpassword")
    
    # Test create new expense
    new_expense_data = {
        "village_id": str(setup_test_db["village_id"]),
        "category_id": str(setup_test_db["category_id"]),
        "amount": 500.0,
        "description": "Plumbing repairs",
        "payment_date": datetime.now().isoformat()
    }
    
    response = client.post(
        "/expenses/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=new_expense_data
    )
    assert response.status_code == 201
    assert response.json()["amount"] == 500.0
    
    # Test get all expenses
    response = client.get(
        "/expenses/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    
    # Test get expense categories
    response = client.get(
        "/expenses/categories/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Maintenance"

# Test visitor endpoints
def test_visitor_endpoints(setup_test_db):
    # Get admin token
    admin_token = get_auth_token("admin", "adminpassword")
    
    # Test create new visitor
    new_visitor_data = {
        "village_id": str(setup_test_db["village_id"]),
        "property_id": str(setup_test_db["property_id"]),
        "name": "John Visitor",
        "phone": "123-456-7899",
        "purpose": "Delivery",
        "entry_code": "ABC123",
        "valid_until": (datetime.now() + timedelta(hours=2)).isoformat(),
        "status": "pending"
    }
    
    response = client.post(
        "/visitors/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=new_visitor_data
    )
    assert response.status_code == 201
    assert response.json()["name"] == "John Visitor"
    
    # Test get all visitors
    response = client.get(
        "/visitors/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    
    # Test verify visitor code
    verify_code_data = {
        "entry_code": "ABC123"
    }
    
    response = client.post(
        "/visitors/verify-code",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=verify_code_data
    )
    assert response.status_code == 200
    assert response.json()["valid"] == True
