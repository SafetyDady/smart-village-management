# Database Schema Design for Smart Village Management System

## Overview

This document outlines the database schema design for the Smart Village Management System. The schema is designed to support both multi-tenant and standalone deployment models, with appropriate separation of concerns and data isolation.

## Entity Relationship Diagram

```
+----------------+       +----------------+       +----------------+
| Village        |       | User           |       | Property       |
+----------------+       +----------------+       +----------------+
| id             |<----->| id             |<----->| id             |
| name           |       | village_id     |       | village_id     |
| address        |       | role           |       | address        |
| contact_info   |       | username       |       | owner_id       |
| settings       |       | password_hash  |       | resident_ids   |
| created_at     |       | email          |       | status         |
| updated_at     |       | phone          |       | created_at     |
+----------------+       | status         |       | updated_at     |
                         | created_at     |       +----------------+
                         | updated_at     |               |
                         +----------------+               |
                                 |                        |
                                 |                        |
+----------------+       +----------------+       +----------------+
| Invoice        |       | Payment        |       | AccessLog      |
+----------------+       +----------------+       +----------------+
| id             |<----->| id             |       | id             |
| village_id     |       | invoice_id     |       | village_id     |
| property_id    |       | amount         |       | property_id    |
| amount         |       | payment_date   |       | user_id        |
| due_date       |       | payment_method |       | timestamp      |
| status         |       | status         |       | direction      |
| items          |       | verification   |       | access_method  |
| created_at     |       | slip_url       |       | status         |
| updated_at     |       | created_at     |       | created_at     |
+----------------+       | updated_at     |       +----------------+
                         +----------------+
                                 |
                                 |
+----------------+       +----------------+       +----------------+
| Expense        |       | ExpenseCategory|       | Visitor        |
+----------------+       +----------------+       +----------------+
| id             |<----->| id             |       | id             |
| village_id     |       | village_id     |       | village_id     |
| category_id    |       | name           |       | property_id    |
| amount         |       | description    |       | name           |
| description    |       | status         |       | phone          |
| receipt_url    |       | created_at     |       | purpose        |
| payment_date   |       | updated_at     |       | entry_code     |
| created_at     |       +----------------+       | valid_until    |
| updated_at     |                                | status         |
+----------------+                                | created_at     |
                                                  | updated_at     |
                                                  +----------------+
```

## Tables Description

### Village

Stores information about each village or residential community.

| Column       | Type         | Description                                   |
|--------------|--------------|-----------------------------------------------|
| id           | UUID         | Primary key                                   |
| name         | VARCHAR(100) | Village name                                  |
| address      | TEXT         | Physical address                              |
| contact_info | JSONB        | Contact information (phone, email, etc.)      |
| settings     | JSONB        | Village-specific settings and configurations  |
| created_at   | TIMESTAMP    | Record creation timestamp                     |
| updated_at   | TIMESTAMP    | Record last update timestamp                  |

### User

Stores user information for all system users (admins, staff, residents).

| Column        | Type         | Description                                   |
|---------------|--------------|-----------------------------------------------|
| id            | UUID         | Primary key                                   |
| village_id    | UUID         | Foreign key to Village                        |
| role          | VARCHAR(20)  | User role (admin, staff, resident)            |
| username      | VARCHAR(50)  | Unique username                               |
| password_hash | VARCHAR(255) | Hashed password                               |
| email         | VARCHAR(100) | Email address                                 |
| phone         | VARCHAR(20)  | Phone number                                  |
| status        | VARCHAR(20)  | Account status (active, inactive, suspended)  |
| created_at    | TIMESTAMP    | Record creation timestamp                     |
| updated_at    | TIMESTAMP    | Record last update timestamp                  |

### Property

Represents individual properties (houses) within a village.

| Column       | Type         | Description                                   |
|--------------|--------------|-----------------------------------------------|
| id           | UUID         | Primary key                                   |
| village_id   | UUID         | Foreign key to Village                        |
| address      | VARCHAR(255) | Property address or identifier                |
| owner_id     | UUID         | Foreign key to User (owner)                   |
| resident_ids | JSONB        | Array of User IDs (residents)                 |
| status       | VARCHAR(20)  | Property status (occupied, vacant, etc.)      |
| created_at   | TIMESTAMP    | Record creation timestamp                     |
| updated_at   | TIMESTAMP    | Record last update timestamp                  |

### Invoice

Stores invoices generated for properties.

| Column       | Type         | Description                                   |
|--------------|--------------|-----------------------------------------------|
| id           | UUID         | Primary key                                   |
| village_id   | UUID         | Foreign key to Village                        |
| property_id  | UUID         | Foreign key to Property                       |
| amount       | DECIMAL      | Total invoice amount                          |
| due_date     | DATE         | Payment due date                              |
| status       | VARCHAR(20)  | Invoice status (pending, paid, overdue)       |
| items        | JSONB        | Invoice line items                            |
| created_at   | TIMESTAMP    | Record creation timestamp                     |
| updated_at   | TIMESTAMP    | Record last update timestamp                  |

### Payment

Records payments made against invoices.

| Column         | Type         | Description                                   |
|----------------|--------------|-----------------------------------------------|
| id             | UUID         | Primary key                                   |
| invoice_id     | UUID         | Foreign key to Invoice                        |
| amount         | DECIMAL      | Payment amount                                |
| payment_date   | DATE         | Date of payment                               |
| payment_method | VARCHAR(50)  | Method of payment                             |
| status         | VARCHAR(20)  | Payment status (pending, verified, rejected)  |
| verification   | JSONB        | Verification details                          |
| slip_url       | VARCHAR(255) | URL to payment slip image                     |
| created_at     | TIMESTAMP    | Record creation timestamp                     |
| updated_at     | TIMESTAMP    | Record last update timestamp                  |

### AccessLog

Logs all access control events.

| Column        | Type         | Description                                   |
|---------------|--------------|-----------------------------------------------|
| id            | UUID         | Primary key                                   |
| village_id    | UUID         | Foreign key to Village                        |
| property_id   | UUID         | Foreign key to Property                       |
| user_id       | UUID         | Foreign key to User                           |
| timestamp     | TIMESTAMP    | Event timestamp                               |
| direction     | VARCHAR(10)  | Entry or exit                                 |
| access_method | VARCHAR(50)  | Method used (app, card, code, etc.)           |
| status        | VARCHAR(20)  | Access status (granted, denied)               |
| created_at    | TIMESTAMP    | Record creation timestamp                     |

### Expense

Records village expenses.

| Column       | Type         | Description                                   |
|--------------|--------------|-----------------------------------------------|
| id           | UUID         | Primary key                                   |
| village_id   | UUID         | Foreign key to Village                        |
| category_id  | UUID         | Foreign key to ExpenseCategory                |
| amount       | DECIMAL      | Expense amount                                |
| description  | TEXT         | Expense description                           |
| receipt_url  | VARCHAR(255) | URL to receipt image                          |
| payment_date | DATE         | Date of payment                               |
| created_at   | TIMESTAMP    | Record creation timestamp                     |
| updated_at   | TIMESTAMP    | Record last update timestamp                  |

### ExpenseCategory

Categories for village expenses.

| Column       | Type         | Description                                   |
|--------------|--------------|-----------------------------------------------|
| id           | UUID         | Primary key                                   |
| village_id   | UUID         | Foreign key to Village                        |
| name         | VARCHAR(100) | Category name                                 |
| description  | TEXT         | Category description                          |
| status       | VARCHAR(20)  | Category status (active, inactive)            |
| created_at   | TIMESTAMP    | Record creation timestamp                     |
| updated_at   | TIMESTAMP    | Record last update timestamp                  |

### Visitor

Records visitor information.

| Column       | Type         | Description                                   |
|--------------|--------------|-----------------------------------------------|
| id           | UUID         | Primary key                                   |
| village_id   | UUID         | Foreign key to Village                        |
| property_id  | UUID         | Foreign key to Property being visited         |
| name         | VARCHAR(100) | Visitor name                                  |
| phone        | VARCHAR(20)  | Visitor phone number                          |
| purpose      | TEXT         | Purpose of visit                              |
| entry_code   | VARCHAR(20)  | Unique entry code                             |
| valid_until  | TIMESTAMP    | Code expiration timestamp                     |
| status       | VARCHAR(20)  | Status (pending, used, expired)               |
| created_at   | TIMESTAMP    | Record creation timestamp                     |
| updated_at   | TIMESTAMP    | Record last update timestamp                  |

## Multi-tenant Considerations

For the multi-tenant deployment model:

1. Every table includes a `village_id` field to ensure data isolation between villages
2. Database queries must always filter by `village_id` to maintain tenant separation
3. Indexes should be created on `village_id` columns to optimize query performance
4. Row-level security policies can be implemented in PostgreSQL for additional protection

## Data Migration and Versioning

The database schema will be managed using Alembic for migrations, allowing:

1. Version control of schema changes
2. Seamless upgrades and rollbacks
3. Consistent schema across all environments (development, staging, production)

## Security Considerations

1. All sensitive data (passwords, personal information) must be properly encrypted or hashed
2. Regular backups of the database should be configured
3. Access to the database should be restricted and monitored
4. Database connections should use TLS/SSL encryption

## Performance Optimization

1. Appropriate indexes will be created on frequently queried columns
2. Large tables (like AccessLog) should implement partitioning strategies
3. Regular database maintenance tasks should be scheduled
4. Query optimization should be performed for complex operations
