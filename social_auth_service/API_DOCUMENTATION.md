# Social Auth Service API Documentation

## Overview

Social Auth Service เป็น Backend API สำหรับระบบ Smart Village Management ที่รองรับการเข้าสู่ระบบผ่าน Social Login (LINE, Google, Facebook) และระบบจัดการผู้ใช้แบบหลายบทบาท

## Base URL
```
http://localhost:5000
```

## Authentication

API ใช้ JWT (JSON Web Token) สำหรับการยืนยันตัวตน โดยจะส่ง Access Token และ Refresh Token กลับมาหลังจากเข้าสู่ระบบสำเร็จ

### Headers
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

## User Roles

- **super_admin**: ผู้ดูแลระบบสูงสุด
- **admin**: ผู้ดูแลหมู่บ้าน
- **homeowner**: เจ้าของบ้าน
- **household_member**: สมาชิกในครัวเรือน

## User Status

- **pending_details**: รอกรอกข้อมูลส่วนตัว
- **pending_homeowner_approval**: รออนุมัติจากเจ้าของบ้าน
- **pending_admin_approval**: รออนุมัติจากผู้ดูแลหมู่บ้าน
- **active**: ใช้งานได้
- **rejected**: ถูกปฏิเสธ

## API Endpoints

### Authentication

#### POST /auth/social-login
เข้าสู่ระบบผ่าน Social Login

**Request Body:**
```json
{
  "token": "access_token_from_social_provider",
  "provider": "line|google|facebook"
}
```

**Response:**
```json
{
  "message": "Login successful",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "household_member",
    "status": "active"
  },
  "redirect_to": "/dashboard",
  "tokens": {
    "access_token": "jwt_access_token",
    "refresh_token": "jwt_refresh_token"
  }
}
```

#### POST /auth/email-login
เข้าสู่ระบบด้วย Email/Password

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

#### POST /auth/logout
ออกจากระบบ

#### POST /auth/refresh-token
รีเฟรช Access Token

### User Management

#### POST /user/complete-profile
กรอกข้อมูลส่วนตัวหลังจากเข้าสู่ระบบครั้งแรก

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "phone": "0812345678",
  "line_id": "line_user_id",
  "email": "user@example.com",
  "role_selection": "homeowner|household_member",
  "village_id": "village_uuid",
  "house_number": "123"
}
```

#### GET /user/profile
ดูข้อมูลส่วนตัว

**Headers:** `Authorization: Bearer <token>`

#### PUT /user/profile
แก้ไขข้อมูลส่วนตัว

**Headers:** `Authorization: Bearer <token>`

#### GET /user/status
ดูสถานะการอนุมัติ

**Headers:** `Authorization: Bearer <token>`

#### GET /user/villages
ดูรายการหมู่บ้าน

#### GET /user/villages/{village_id}/houses
ดูรายการบ้านในหมู่บ้าน

### Admin Functions

#### GET /admin/pending-users
ดูรายการผู้ใช้ที่รออนุมัติ

**Headers:** `Authorization: Bearer <token>`
**Roles:** admin, super_admin

#### POST /admin/approve-user/{user_id}
อนุมัติผู้ใช้

**Headers:** `Authorization: Bearer <token>`
**Roles:** admin, super_admin

#### POST /admin/reject-user/{user_id}
ปฏิเสธผู้ใช้

**Headers:** `Authorization: Bearer <token>`
**Roles:** admin, super_admin

**Request Body:**
```json
{
  "reason": "เหตุผลในการปฏิเสธ"
}
```

#### POST /admin/assign-admin/{user_id}
แต่งตั้งผู้ใช้เป็น Admin

**Headers:** `Authorization: Bearer <token>`
**Roles:** super_admin

**Request Body:**
```json
{
  "village_ids": ["village_uuid1", "village_uuid2"]
}
```

#### GET /admin/users
ดูรายการผู้ใช้ทั้งหมด

**Headers:** `Authorization: Bearer <token>`
**Roles:** admin, super_admin

### Homeowner Functions

#### GET /homeowner/pending-members
ดูรายการสมาชิกที่รออนุมัติ

**Headers:** `Authorization: Bearer <token>`
**Roles:** homeowner

#### POST /homeowner/approve-member/{user_id}
อนุมัติสมาชิกในครัวเรือน

**Headers:** `Authorization: Bearer <token>`
**Roles:** homeowner

#### POST /homeowner/reject-member/{user_id}
ปฏิเสธสมาชิกในครัวเรือน

**Headers:** `Authorization: Bearer <token>`
**Roles:** homeowner

**Request Body:**
```json
{
  "reason": "เหตุผลในการปฏิเสธ"
}
```

#### GET /homeowner/household-members
ดูรายการสมาชิกในครัวเรือน

**Headers:** `Authorization: Bearer <token>`
**Roles:** homeowner

### Village & House Management

#### GET /village_house/villages
ดูรายการหมู่บ้านทั้งหมด

#### GET /village_house/villages/{village_id}/houses
ดูรายการบ้านในหมู่บ้าน

#### POST /village_house/villages
สร้างหมู่บ้านใหม่

**Headers:** `Authorization: Bearer <token>`
**Roles:** super_admin

**Request Body:**
```json
{
  "name": "ชื่อหมู่บ้าน",
  "description": "คำอธิบาย",
  "admin_id": "admin_uuid"
}
```

#### POST /village_house/houses
สร้างบ้านใหม่

**Headers:** `Authorization: Bearer <token>`
**Roles:** admin, super_admin

**Request Body:**
```json
{
  "village_id": "village_uuid",
  "house_number": "123",
  "address": "ที่อยู่"
}
```

## Error Responses

### 400 Bad Request
```json
{
  "message": "Invalid request data"
}
```

### 401 Unauthorized
```json
{
  "message": "Invalid credentials"
}
```

### 403 Forbidden
```json
{
  "message": "Access denied"
}
```

### 404 Not Found
```json
{
  "message": "Resource not found"
}
```

### 500 Internal Server Error
```json
{
  "message": "Internal server error"
}
```

## Environment Variables

```bash
# Database
DATABASE_URL=sqlite:///social_auth.db

# JWT
JWT_SECRET_KEY=your_jwt_secret_key

# Super Admin Configuration
SUPER_ADMIN_EMAIL=admin@smartvillage.com
SUPER_ADMIN_GOOGLE_ID=google_user_id
SUPER_ADMIN_LINE_ID=line_user_id
SUPER_ADMIN_FACEBOOK_ID=facebook_user_id

# Social Login Configuration
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret

LINE_CHANNEL_ID=your_line_channel_id
LINE_CHANNEL_SECRET=your_line_channel_secret
```

## User Flow

### 1. Social Login Flow
1. ผู้ใช้เข้าสู่ระบบผ่าน Social Provider
2. Frontend ส่ง Token มายัง `/auth/social-login`
3. ระบบตรวจสอบ Token และสร้างผู้ใช้ใหม่ (ถ้าไม่มี)
4. ส่ง JWT Token กลับไปพร้อมกับ redirect URL

### 2. Profile Completion Flow
1. ผู้ใช้ใหม่จะมีสถานะ `pending_details`
2. ผู้ใช้กรอกข้อมูลผ่าน `/user/complete-profile`
3. เลือกบทบาท: homeowner หรือ household_member
4. สถานะเปลี่ยนเป็น `pending_homeowner_approval` หรือ `pending_admin_approval`

### 3. Approval Flow
1. **Household Member**: รออนุมัติจาก Homeowner → รออนุมัติจาก Admin → Active
2. **Homeowner**: รออนุมัติจาก Admin → Active

### 4. Admin Assignment Flow
1. Super Admin แต่งตั้ง User เป็น Admin
2. กำหนดหมู่บ้านที่ Admin ดูแล
3. Admin สามารถอนุมัติผู้ใช้ในหมู่บ้านที่ตนดูแลได้

