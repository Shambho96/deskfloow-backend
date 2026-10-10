# 🏨 DeskFlow PMS — Backend Engine

DeskFlow is a high-performance, multi-tenant Hotel Property Management System (PMS) backend built with **FastAPI**, **Strawberry GraphQL**, **AsyncSQLAlchemy**, and **PostgreSQL (Neon Cloud DB)**.

It features a **Hybrid REST + GraphQL Architecture**:
- **REST API (`/api/v1/auth/`)**: Secure authentication, HttpOnly cookies, and session outlet switching.
- **GraphQL API (`/graphql`)**: High-performance operational data fetching for Team & Staff Management, Rooms, Bookings, and Front-Desk operations.

---

## 🛠️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **Language & Framework** | Python 3.10+ / FastAPI |
| **GraphQL Engine** | Strawberry GraphQL |
| **Database ORM** | AsyncSQLAlchemy + AsyncPG |
| **Database Host** | Neon Cloud PostgreSQL |
| **Schema Migrations** | Alembic |
| **Authentication** | RFC 7519 JWT + HttpOnly Cookies |
| **Security & Privacy** | Bcrypt + AES-256-GCM PII Encryption + HMAC Blind Indexing |
| **Testing** | Pytest + AsyncHTTPX (SQLite In-Memory) |

---

## 📋 Prerequisites & Requirements

- **Python**: `3.10` or higher (Python 3.14 compatible)
- **PostgreSQL**: Neon Cloud Database or local PostgreSQL database
- **Git**: Installed on system

---

## 🚀 Step-by-Step Local Setup & Installation

### 1. Clone Repository & Navigate
```bash
git clone <repository-url>
cd HRM-backend
```

### 2. Create & Activate Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**On Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Required Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## ⚙️ Environment Configuration (`.env`)

Create a `.env` file in the project root directory (`HRM-backend/.env`):

```env
# Application Settings
APP_NAME="DeskFlow Hotel PMS API"
ENVIRONMENT="development"
PORT=8000
SQL_ECHO=False

# Neon Cloud PostgreSQL Connection URL
DATABASE_URL="postgresql+asyncpg://neondb_owner:YOUR_PASSWORD@ep-odd-band-b43btyo0-pooler.c-6.us-east-2.aws.neon.tech/neondb?ssl=require"

# JWT Security Settings
JWT_SECRET="your-32-character-random-jwt-secret-key-here"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=60

# PII AES-256 Encryption Settings
PII_SECRET_KEY="your-32-character-random-pii-encryption-key-here"

# CORS Configuration
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
```

---

## 🗄️ Database Setup & Migrations (Alembic)


### 1. Apply Migrations to PostgreSQL
```bash
python -m alembic upgrade head
```

### 2. Check Current Migration Status
```bash
python -m alembic current
```

### 3. Creating New Database Revisions (After Model Changes)
```bash
python -m alembic revision --autogenerate -m "describe_your_changes"
python -m alembic upgrade head
```

---

## 🖥️ Running the Backend Server

Start the Uvicorn development server with live reload:

```bash
uvicorn app.main:app --reload --port 8000
```

Once started, access the interactive interfaces:
- **GraphiQL IDE (GraphQL Interface)**: [http://127.0.0.1:8000/graphql](http://127.0.0.1:8000/graphql)
- **Swagger UI (REST Auth Docs)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## 📖 API Architecture & Usage

### 1. REST Authentication (`/api/v1/auth/`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **`POST`** | `/api/v1/auth/login` | Authenticates credentials, checks Staff Login Guard, sets HttpOnly cookie. |
| **`GET`** | `/api/v1/auth/me` | Returns current user profile, active outlet, and allowed outlets. |
| **`POST`** | `/api/v1/auth/switch-outlet` | Switches active property session & re-issues JWT token. |
| **`POST`** | `/api/v1/auth/logout` | Clears HttpOnly authentication cookies. |

### 2. GraphQL Operations (`/graphql`)

#### **Query: List Team Members**
```graphql
query {
  teamMembers {
    status
    total
    users {
      id
      name
      email
      phone
      role
      canLogin
      isActive
      assignedOutletIds
      createdAt
    }
  }
}
```

#### **Mutation: Create Manager or Staff Member**
```graphql
mutation {
  createTeamMember(input: {
    name: "Sunil Frontdesk"
    email: "sunil.fd@tarahotel.com"
    phone: "+919876543299"
    role: "STAFF"
  }) {
    id
    name
    role
    canLogin
    assignedOutletIds
  }
}
```

#### **Mutation: Activate / Deactivate Staff Member**
```graphql
mutation {
  toggleTeamMemberStatus(userId: 2, isActive: false) {
    status
    message
  }
}
```

---

## 🧪 Running Unit Tests

Run automated test suite using SQLite in-memory database override:

```bash
python -m pytest tests/
```

---

## 📁 Project Directory Structure

```text
HRM-backend/
├── alembic/                      <-- Database Migration Scripts
├── alembic.ini                   <-- Alembic Configuration
├── README.md                     <-- Documentation
├── requirements.txt              <-- Python Dependency List
├── tests/                        <-- Automated Pytest Test Suite
└── app/
    ├── config.py                 <-- Pydantic Configuration Settings
    ├── main.py                   <-- Application Lifespan & Router Mounting
    ├── core/
    │   ├── context.py           <-- Typed UserContext Model
    │   ├── dependencies.py      <-- REST Authentication Dependency
    │   └── security.py          <-- Bcrypt, JWT, & AES-256 PII Helpers
    ├── db/
    │   ├── base.py              <-- SQLAlchemy Declarative Base
    │   └── session.py           <-- Async Database Session Factory
    ├── models/                  <-- ORM Database Models
    │   ├── client.py
    │   ├── outlet.py
    │   ├── user.py
    │   └── mapping.py
    ├── routers/
    │   └── auth_router.py       <-- REST Authentication Router
    ├── schemas/                 <-- Pydantic Schemas
    │   ├── auth_schemas.py
    │   └── user_schemas.py
    ├── services/                <-- Core Service Layer & Transactions
    │   ├── auth_service.py
    │   └── user_service.py
    └── graphql/                 <-- Strawberry GraphQL Layer
        ├── context.py           <-- GraphQL Context Getter
        ├── helpers.py           <-- Shared Mapping Helpers
        ├── schema.py            <-- Combined Root GraphQL Schema
        ├── logging_extension.py <-- Compact Terminal Logging Extension
        ├── types/
        │   └── user_types.py
        ├── queries/
        │   └── user_queries.py
        └── mutations/
            └── user_mutations.py
```

---

## 🚂 Railway CI/CD Deployment Rules

- **Development**: Push/tag to `dev` → Deploys to Railway Dev Environment.
- **Staging**: Push/tag to `stag` → Deploys to Railway Staging Environment.
- **Production**: Push/tag to `prod` → Deploys to Railway Production Environment.
