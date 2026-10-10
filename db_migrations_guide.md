# DeskFlow Database Migrations Guide (Alembic)

This guide explains how database schema migrations work in `HRM-backend` using **Alembic** and **SQLAlchemy 2.0**.

Whenever you add, modify, or delete a column or table model inside `app/models/`, follow these exact steps to update your database schema safely.

---

## 🛠️ Prerequisites & Setup

Activate your virtual environment before running commands:

```powershell
# In PowerShell / Command Prompt
.\.venv\Scripts\activate
```

---

## 🚀 Step-by-Step Migration Workflow

### **Step 1: Make your changes in Python Models**
Modify or create SQLAlchemy models in `app/models/` (e.g. `user.py`, `client.py`, `outlet.py`, or new model files).

> ⚠️ **Important:** Whenever you add a new model file (e.g. `app/models/booking.py`), make sure to import it in `app/models/__init__.py` and `alembic/env.py` so Alembic detects it!

---

### **Step 2: Generate an Auto-Migration Script**
Run Alembic's `autogenerate` command to let Alembic inspect your Python models and compare them against your live PostgreSQL database:

```bash
python -m alembic revision --autogenerate -m "description_of_changes"
```

**Examples:**
```bash
# Example 1: Initial migration
python -m alembic revision --autogenerate -m "create initial auth tables"

# Example 2: Adding a new column to users table
python -m alembic revision --autogenerate -m "add is_verified column to users"
```

This creates a new migration file inside `alembic/versions/` (e.g. `alembic/versions/2026_10_10_0001_create_initial_auth_tables.py`).

---

### **Step 3: Review the Migration Script (Recommended)**
Open the newly created file inside `alembic/versions/` and inspect the `upgrade()` and `downgrade()` functions to make sure the generated SQL changes match your expectations.

---

### **Step 4: Apply Migration to Database (Upgrade Head)**
Apply the migration to your live database (e.g. Neon Cloud PostgreSQL):

```bash
python -m alembic upgrade head
```

You will see:
```text
INFO [alembic.runtime.migration] Running upgrade -> 2026_10_10_0001, create initial auth tables
```

Your database is now 100% updated with the latest schema changes! 🎉

---

## ↩️ Rollback / Downgrade Steps (If needed)

If you ever need to undo or rollback the last applied migration:

```bash
# Rollback 1 migration step backward
python -m alembic downgrade -1

# Rollback all migrations back to base
python -m alembic downgrade base
```

---

## 📊 Useful Alembic Commands Reference

| Action | Command |
| :--- | :--- |
| **Check Current Revision** | `python -m alembic current` |
| **View Migration History** | `python -m alembic history` |
| **Create Manual Script** | `python -m alembic revision -m "manual change"` |
| **Auto-Generate Script** | `python -m alembic revision --autogenerate -m "change name"` |
| **Apply All Migrations** | `python -m alembic upgrade head` |
| **Rollback 1 Migration** | `python -m alembic downgrade -1` |

---

## 🔒 Production & Team Best Practices

1. **Commit Migration Files to Git:** Always commit files in `alembic/versions/` so team members get the exact same schema upgrades.
2. **Never Edit Past Migrations:** Once a migration has been applied by team members or in production, do not edit its file. Create a new `revision --autogenerate` script instead!
3. **Environment Variables:** Alembic automatically reads `DATABASE_URL` from your `.env` file (configured in `alembic/env.py`).
