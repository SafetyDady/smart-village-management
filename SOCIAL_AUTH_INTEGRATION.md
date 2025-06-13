# Social Auth Service Integration

## Overview
Social Auth Service ได้ถูกเพิ่มเข้ามาในโปรเจค Smart Village Management เป็น microservice สำหรับจัดการระบบ authentication และ user management

## Location
```
smart-village-management/
└── social_auth_service/          # Social Authentication Microservice
    ├── src/                      # Source code
    ├── tests/                    # Unit tests
    ├── API_DOCUMENTATION.md      # API documentation
    ├── README.md                 # Service documentation
    └── requirements.txt          # Python dependencies
```

## Features Added
- 🔐 Social Login integration (LINE, Google, Facebook)
- 👥 Multi-role user management (Super Admin, Admin, Homeowner, Household Member)
- 🛡️ JWT authentication and role-based access control
- 📋 Multi-step approval workflow
- 🏘️ Village and house management
- 🧪 Complete unit tests and API documentation

## Integration with Main System
Social Auth Service ทำงานเป็น independent microservice ที่สามารถ:
- รันแยกจากระบบหลักบน port 5001
- ให้บริการ authentication APIs สำหรับ frontend และ mobile app
- จัดการ user roles และ permissions แยกจากระบบหลัก

## Quick Start
```bash
cd social_auth_service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Configure environment variables
python src/main.py
```

## API Endpoints
- Authentication: `/auth/*`
- User Management: `/user/*`
- Admin Functions: `/admin/*`
- Homeowner Functions: `/homeowner/*`
- Village Management: `/village_house/*`

See `social_auth_service/API_DOCUMENTATION.md` for complete API reference.

## Architecture Integration
```
Smart Village Management System
├── Backend (FastAPI) - Port 8000
├── Frontend (React) - Port 3000
├── Mobile App (React Native)
└── Social Auth Service (Flask) - Port 5001  ← NEW
```

## Next Steps
1. Configure environment variables in `social_auth_service/.env`
2. Set up social login providers (LINE, Google, Facebook)
3. Integrate authentication APIs with frontend and mobile app
4. Deploy as separate microservice in production

