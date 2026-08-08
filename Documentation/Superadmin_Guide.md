# Superadmin & Account Configuration Guide

This document explains the automatic account initialization and how to manage the Superadmin account for the Migration Intelligence Platform.

## 🚀 Automatic Initialization

The platform is designed to be "ready-to-use" immediately after deployment. Every time the backend server starts, it checks the database for a `superadmin` role.

If no superadmin is found (e.g., first-time run), the system will **automatically create one** with the following default credentials:

| Field | Default Value | Environment Variable |
| :--- | :--- | :--- |
| **Username** | `superadmin` | `ADMIN_USERNAME` |
| **Email** | `admin@migrationintelligence.com` | `ADMIN_EMAIL` |
| **Password** | `admin123456` | `ADMIN_PASSWORD` |

## ⚙️ Configuration via `.env`

You can customize the initial superadmin credentials by adding these lines to your `backend/.env` file **before** the first run:

```env
ADMIN_USERNAME=my_super_admin
ADMIN_EMAIL=my_email@example.com
ADMIN_PASSWORD=my_secure_password_123
```

## 🔐 Security Best Practices

1. **Change Default Password**: After your first login, please change the superadmin password through the profile settings.
2. **Environment Protection**: Never share your `.env` file or commit it to Version Control (Git).
3. **SMTP for Recovery**: Ensure `SMTP_USER` and `SMTP_PASSWORD` are configured in `.env` so you can use the "Forgot Password" feature if you lose access.

## 🛠️ Technical Implementation

The initialization logic is located in:

- `backend/services/admin_init.py`: Contains the creation logic.
- `backend/main.py`: Triggers the check during the FastAPI `lifespan` event.

---
*&copy; 2026 Interlace Data Analyst - Migration Intelligence Platform*
