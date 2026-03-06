# 🚀 Quick Start Guide

## Getting Started in 5 Steps

### Step 1: Open Browser
Go to: **http://localhost:8000**

### Step 2: Login
Choose one of these test accounts:

**Worker Account:**
- Username: `testworker`
- Password: `worker123`
- Dashboard: Shows "Hello Family" ✨

**Admin Account:**
- Username: `testadmin`
- Password: `admin123`
- Dashboard: Shows "Hi Admin" 👨‍💼

### Step 3: Explore Dashboards
- **Worker**: See personal greeting and profile options
- **Admin**: See admin tools and management options

### Step 4: Test Features
- 📋 View Profile
- 🔐 Change Password
- 👤 Update Account Info
- 🌍 View Country Info

### Step 5: Test Signup
1. Click "Sign Up" 
2. Create new account
3. Select user type (Worker/Admin)
4. Login with new account

---

## 📍 Important Pages

| Name | URL | Purpose |
|------|-----|---------|
| Login | `http://localhost:8000/login/` | Sign in to account |
| Signup | `http://localhost:8000/signup/` | Create new account |
| Dashboard | `http://localhost:8000/` | Home page (auto-redirect) |
| Profile | `http://localhost:8000/profile/` | View user details |
| Forgot Password | `http://localhost:8000/forgot-password/` | Reset password |
| Admin Panel | `http://localhost:8000/admin/` | System administration |

---

## 💾 Database Information

**Database Type**: SQLite
**Database File**: `db.sqlite3`

**Tables Created**:
- ✅ CustomUser (user profiles with type: worker/admin)
- ✅ Country (country master data)
- ✅ Data (data entries by country)
- ✅ DashboardURL (dashboard links)

---

## 🛠️ Management Commands

### Run Server
```bash
python manage.py runserver
```

### Create New Admin
```bash
python manage.py createsuperuser
```

### Access Database Shell
```bash
python manage.py shell
```

### Create Migrations
```bash
python manage.py makemigrations
```

### Apply Migrations
```bash
python manage.py migrate
```

---

## 🔄 File Structure Summary

```
MyProject/
├── myproject/          ← Settings & config
├── accounts/           ← Auth app (models, views, forms)
├── templates/          ← HTML pages
├── static/             ← CSS, JS, images
├── manage.py           ← Control center
├── db.sqlite3          ← Database
└── requirements.txt    ← Dependencies
```

---

## ✨ Key Features

✅ **Two User Types**
- Worker: Regular users
- Admin: System administrators

✅ **Authentication**
- Secure signup and login
- Password hashing
- Session management
- Logout functionality

✅ **Password Recovery**
- Forgot password form
- Token-based reset
- New password confirmation

✅ **User Profile**
- Personal information
- Contact details
- Country selection
- User type display

✅ **Admin Features**
- Manage all users
- Manage countries
- Manage data
- View system info

---

## 📊 Dashboard Messages

**Worker Dashboard**: 
```
👋 Hello Family
Welcome to your personal dashboard!
```

**Admin Dashboard**:
```
👨‍💼 Hi Admin
Welcome to the admin dashboard!
```

---

## ❓ Need Help?

### Issue: Can't login
- Check username/password spelling
- Use `testworker` or `testadmin`
- Or create new account via signup

### Issue: Server won't start
- Port 8000 might be in use
- Try: `python manage.py runserver 8001`

### Issue: Database errors
- Run: `python manage.py migrate`
- Or reset: `python setup_data.py`

### Issue: Static files not loading
- Create `static/` folder
- Run: `python manage.py collectstatic`

---

## 🎯 What to Test

1. **Signup Flow**
   - Sign up as new worker
   - Sign up as new admin
   - Verify user type selection

2. **Login Flow**
   - Login with worker account
   - Logout
   - Login with admin account
   - Logout

3. **Dashboard Differences**
   - Compare worker vs admin dashboards
   - Check different messages
   - Verify access to different features

4. **Profile Page**
   - View account information
   - Check user type display
   - View country information

5. **Password Reset**
   - Go to forgot password
   - Enter email
   - Set new password
   - Login with new password

6. **Admin Panel**
   - Login as admin (superuser)
   - Access `/admin/`
   - View user list
   - View countries
   - View data entries

---

## 🚀 Next Steps

1. **Explore Code**
   - Read `accounts/models.py` for database structure
   - Read `accounts/views.py` for login logic
   - Read `templates/accounts/` for user interfaces

2. **Customize**
   - Change welcome messages in templates
   - Add new fields to user model
   - Add new pages/features

3. **Deploy** (Later)
   - Setup production database
   - Configure email service
   - Deploy to web server
   - Enable HTTPS

---

## 📝 Test Credentials Summary

```
╔════════════════╦═══════════════╦═══════════╦═══════════════╗
║ Account Type   ║ Username      ║ Password  ║ Dashboard     ║
╠════════════════╬═══════════════╬═══════════╬═══════════════╣
║ Worker         ║ testworker    ║ worker123 ║ Hello Family  ║
║ Admin (App)    ║ testadmin     ║ admin123  ║ Hi Admin      ║
║ Superuser      ║ admin         ║ admin     ║ /admin/       ║
╚════════════════╩═══════════════╩═══════════╩═══════════════╝
```

---

## ✅ Development Checklist

- [x] Project created
- [x] Database configured
- [x] Models created
- [x] Forms created
- [x] Views created
- [x] Templates created
- [x] URLs configured
- [x] Admin configured
- [x] Test data created
- [x] Server running
- [x] Ready to test

---

## 🎉 You're Ready!

Your Django authentication system is live at:
### **http://localhost:8000**

Login and start exploring! 🚀

---

**Dashboard Messages:**
- Workers see: **"Hello Family"** 👋
- Admins see: **"Hi Admin"** 👨‍💼

Enjoy! 😊
