import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from src.models.user import db, User, Village, House
from src.routes.auth import auth_bp
from src.routes.user_management import user_bp
from src.routes.admin_homeowner_village import admin_bp, homeowner_bp, village_house_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# Configuration from environment variables
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-jwt-secret-key-change-in-production')

# Database configuration
database_url = os.getenv('DATABASE_URL', 'sqlite:///social_auth.db')
if database_url.startswith('sqlite:///') and not database_url.startswith('sqlite:////'):
    # Convert relative path to absolute path for SQLite
    db_path = database_url.replace('sqlite:///', '')
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(__file__), 'database', db_path)
        database_url = f'sqlite:///{db_path}'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
jwt = JWTManager(app)

# CORS configuration
cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:8080').split(',')
CORS(app, origins=cors_origins)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(user_bp, url_prefix='/api/user')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(homeowner_bp, url_prefix='/api/homeowner')
app.register_blueprint(village_house_bp, url_prefix='/api/village-house')

# Create database tables
with app.app_context():
    # Create database directory if it doesn't exist
    db_dir = os.path.dirname(database_url.replace('sqlite:///', ''))
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    db.create_all()
    
    # Create super admin if not exists
    super_admin_email = os.getenv('SUPER_ADMIN_EMAIL')
    if super_admin_email:
        existing_super_admin = User.query.filter_by(email=super_admin_email).first()
        if not existing_super_admin:
            super_admin = User(
                email=super_admin_email,
                first_name='Super',
                last_name='Admin',
                role='super_admin',
                status='active'
            )
            db.session.add(super_admin)
            db.session.commit()
            print(f"Super admin created with email: {super_admin_email}")

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
