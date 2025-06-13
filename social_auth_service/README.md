# Social Auth Service

Social Login และ Multi-Role User Management System สำหรับ Smart Village Management

## Features

- 🔐 **Social Login Integration**: รองรับ LINE, Google, Facebook
- 👥 **Multi-Role Management**: Super Admin, Admin, Homeowner, Household Member
- 🛡️ **JWT Authentication**: ระบบยืนยันตัวตนที่ปลอดภัย
- 📋 **Approval Workflow**: ระบบอนุมัติผู้ใช้แบบหลายขั้นตอน
- 🏘️ **Village Management**: จัดการหมู่บ้านและบ้านเลขที่
- 🧪 **Complete Testing**: Unit Tests และ Integration Tests

## Quick Start

### 1. Installation
```bash
git clone <repository-url>
cd social_auth_service
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Setup
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Run Application
```bash
python src/main.py
```

Server จะรันที่ `http://localhost:5001`

## API Documentation

ดูเอกสาร API ครบถ้วนที่ [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

## Architecture

```
src/
├── main.py                 # Flask Application Entry Point
├── models/
│   └── user.py            # Database Models
├── routes/
│   ├── auth.py            # Authentication Endpoints
│   ├── user_management.py # User Management
│   └── admin_homeowner_village.py # Admin/Homeowner Functions
└── utils/
    ├── social_login.py    # Social Login Integration
    └── jwt_handler.py     # JWT Token Management
```

## User Roles & Workflow

### Roles
- **Super Admin**: ผู้ดูแลระบบสูงสุด
- **Admin**: ผู้ดูแลหมู่บ้าน
- **Homeowner**: เจ้าของบ้าน
- **Household Member**: สมาชิกในครัวเรือน

### Approval Flow
1. **Household Member**: Social Login → Complete Profile → Homeowner Approval → Admin Approval → Active
2. **Homeowner**: Social Login → Complete Profile → Admin Approval → Active

## Environment Variables

```bash
# Database
DATABASE_URL=sqlite:///social_auth.db

# JWT
JWT_SECRET_KEY=your_jwt_secret_key

# Super Admin
SUPER_ADMIN_EMAIL=admin@smartvillage.com
SUPER_ADMIN_GOOGLE_ID=your_google_id
SUPER_ADMIN_LINE_ID=your_line_id
SUPER_ADMIN_FACEBOOK_ID=your_facebook_id

# Social Login
GOOGLE_CLIENT_ID=your_google_client_id
FACEBOOK_APP_ID=your_facebook_app_id
LINE_CHANNEL_ID=your_line_channel_id
```

## Testing

```bash
# Run Unit Tests
python -m pytest tests/ -v

# Run Integration Tests
python -c "from src.main import app; ..."
```

## Production Deployment

1. เปลี่ยน Database จาก SQLite เป็น PostgreSQL/MySQL
2. ตั้งค่า SSL Certificate
3. ตั้งค่า Environment Variables ใน Production
4. ตั้งค่า Social Login Apps (LINE, Google, Facebook)
5. Deploy ด้วย Docker หรือ Cloud Platform

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

This project is licensed under the MIT License.

## Support

สำหรับคำถามหรือปัญหา กรุณาสร้าง Issue ใน GitHub repository

