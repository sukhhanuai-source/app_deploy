# API & URL Structure

## Main URLs

### Authentication URLs
```
GET  /login/                    → Login page
POST /login/                    → Process login
GET  /signup/                   → Signup page
POST /signup/                   → Process signup
GET  /logout/                   → Logout user

GET  /forgot-password/          → Forgot password page
POST /forgot-password/          → Process forgot password
GET  /reset-password/<token>/   → Reset password page
POST /reset-password/<token>/   → Process reset password
```

### User URLs
```
GET  /                          → Dashboard (redirects based on user type)
GET  /profile/                  → User profile page
```

### Admin URLs
```
GET  /admin/                    → Django admin interface
GET  /admin/accounts/customuser/     → Manage users
GET  /admin/accounts/country/        → Manage countries
GET  /admin/accounts/data/           → Manage data
GET  /admin/accounts/dashboardurl/   → Manage dashboard URLs
```

---

## View Functions (Backend)

### Authentication Views
```python
signup_view(request)           # Handle user registration
login_view(request)            # Handle user authentication
logout_view(request)           # Handle user logout
forgot_password_view(request)  # Initiate password reset
reset_password_view(request, token)  # Complete password reset
```

### User Views
```python
dashboard_view(request)        # Main dashboard (role-based routing)
profile_view(request)          # User profile display
```

---

## Form Classes

### Authentication Forms
```python
SignUpForm                      # Registration form with validation
LoginForm                       # Login form
ForgotPasswordForm              # Password recovery form
ResetPasswordForm               # New password form
```

---

## Model Structure

### CustomUser
```python
django_user = OneToOneField(User)
user_type = CharField(choices=[('worker', 'Worker'), ('admin', 'Admin')])
phone_number = CharField(optional)
country = ForeignKey(Country)
dashboard_url = ForeignKey(DashboardURL)
created_at = DateTimeField
updated_at = DateTimeField
```

### Country
```python
name = CharField(unique=True)
created_at = DateTimeField
```

### Data
```python
name = CharField
country = ForeignKey(Country)
data_type = CharField
created_at = DateTimeField
updated_at = DateTimeField
```

### DashboardURL
```python
name = CharField(unique=True)
url = CharField
created_at = DateTimeField
```

---

## Template Files

### Base Templates
```
templates/base.html             # Main layout template
```

### Authentication Templates
```
templates/accounts/login.html           # Login page
templates/accounts/signup.html          # Signup page
templates/accounts/forgot_password.html # Password recovery
templates/accounts/reset_password.html  # Password reset
```

### Dashboard Templates
```
templates/accounts/dashboard.html          # Generic dashboard
templates/accounts/worker_dashboard.html   # "Hello Family"
templates/accounts/admin_dashboard.html    # "Hi Admin"
```

### User Templates
```
templates/accounts/profile.html    # User profile page
```

---

## Request/Response Flow

### Signup Flow
```
GET /signup/
    ↓
Show signup form with fields:
  - username
  - email
  - password
  - user_type (radio button)
    ↓
POST /signup/
    ↓
Validate form
    ↓
Create Django User
    ↓
Create CustomUser with:
  - user_type (from form)
  - phone_number
  - country
    ↓
Auto-login user
    ↓
Redirect to /dashboard/
```

### Login Flow
```
GET /login/
    ↓
Show login form
    ↓
POST /login/
    ↓
Authenticate with username/password
    ↓
Create session
    ↓
Redirect to /dashboard/
```

### Dashboard Flow
```
GET /
    ↓
Check if user authenticated
    ↓
Get CustomUser profile
    ↓
Check user_type
    ↓
If 'worker':
  → Render worker_dashboard.html
     Shows: "Hello Family"
    ↓
If 'admin':
  → Render admin_dashboard.html
     Shows: "Hi Admin"
```

### Password Reset Flow
```
GET /forgot-password/
    ↓
Show forgot password form
    ↓
POST /forgot-password/
    ↓
Find user by email
    ↓
Generate reset token
    ↓
Store in session
    ↓
Show reset password form
    ↓
POST /reset-password/<token>/
    ↓
Validate token
    ↓
Hash new password
    ↓
Save to database
    ↓
Redirect to login
```

---

## HTTP Status Codes

```
200 OK              Successful request
301/302 REDIRECT    Redirect to another page
400 BAD REQUEST     Form validation failed
401 UNAUTHORIZED    Login required
403 FORBIDDEN       Access denied
404 NOT FOUND       Page not found
500 SERVER ERROR    Server issue
```

---

## Form Field Validation

### Signup Form
```
username     → Required, 150 chars max, unique
email        → Required, valid email format, unique
password1    → Required, min 8 chars, not common
password2    → Required, must match password1
first_name   → Optional, 100 chars max
last_name    → Optional, 100 chars max
user_type    → Required, choose worker/admin
phone_number → Optional, valid phone format
country      → Optional, must exist in database
```

### Login Form
```
username → Required
password → Required
```

### Forgot Password Form
```
email → Required, must exist in database
```

### Reset Password Form
```
password1 → Required, min 8 chars
password2 → Required, must match password1
```

---

## Database Relationships

```
Django User (built-in)
    ↓ OneToOne
    ↓
CustomUser
    ├─ ForeignKey → Country
    └─ ForeignKey → DashboardURL

Country
    ↓ ForeignKey (reverse)
    ↓
Data (data_entries)
```

---

## Authentication Flow Diagram

```
User Request
    ↓
Check Session
    ├→ No Session: Redirect to login
    └→ Has Session: Get CustomUser profile
        ↓
        Get user_type
        ├→ 'worker': Show worker dashboard ("Hello Family")
        └→ 'admin': Show admin dashboard ("Hi Admin")
```

---

## Admin Interface Structure

### Users Management
```
- List all CustomUsers
- Filter by user_type, country, date
- Search by username, email, phone
- View relationships (country, dashboard_url)
- Edit user details
- Delete users
```

### Countries Management
```
- List all countries
- Add new countries
- Edit country names
- Delete countries
- Related data entries shown
```

### Data Management
```
- List all data entries
- Filter by country, data_type
- Search by name, type
- View country relationships
- Add/edit/delete entries
```

### Dashboard URL Management
```
- List all dashboard URLs
- Add new URLs
- Edit URL names/paths
- Delete URLs
- View users assigned to each URL
```

---

## Session Management

```
Settings:
  SESSION_ENGINE = 'django.contrib.sessions.backends.db'
  SESSION_COOKIE_AGE = 1209600 (2 weeks)
  SESSION_COOKIE_SECURE = False (set True in production)
  SESSION_COOKIE_HTTPONLY = True
  SESSION_EXPIRE_AT_BROWSER_CLOSE = False
```

---

## Error Handling

### Common Errors
```
401 Unauthorized     → Not logged in, redirect to login
403 Forbidden        → Don't have permission
404 Not Found        → Page doesn't exist
ValidationError      → Form field invalid
IntegrityError       → Database constraint violated
```

### Error Messages
```
"Invalid username or password."        → Login failed
"Account created successfully!"        → Signup success
"You have been logged out."            → Logout success
"User profile not found."              → CustomUser missing
"Invalid reset link."                  → Bad token
"Passwords do not match."              → Password mismatch
```

---

## Response Types

```
HTML         → Rendered templates
JSON         → Future API expansion
Redirect     → After form submission
Message      → Success/error notifications
```

---

## Security Features

```
✓ CSRF Protection     On all POST requests
✓ SQL Injection       ORM prevents it
✓ XSS Protection      Template escaping
✓ Password Hashing    PBKDF2WithSHA256
✓ Session Security    Secure cookies
✓ Input Validation    Form validation
✓ Access Control      @login_required decorator
```

---

## Extensibility Points

```
Models
  → Add more fields to CustomUser
  → Create new models
  → Add relationships

Views
  → Add new views
  → Add permissions checking
  → Add API endpoints

Templates
  → Modify styling
  → Add new pages
  → Customize messages

Forms
  → Add form fields
  → Add custom validation
  → Add custom widgets
```

---

## Performance Considerations

```
Database Queries
  ✓ OneToOne relationships optimized
  ✓ ForeignKey indexed automatically
  ✓ Basic caching can be added

Static Files
  ✓ Bootstrap CDN used (no downloads needed)
  ✓ Static folder for custom CSS/JS

Session Storage
  ✓ Database-backed sessions (scalable)
  ✓ Can switch to cache (faster)
```

---

## Future API Endpoints (Optional)

```
POST   /api/auth/signup/          Create new user
POST   /api/auth/login/           Authenticate user
POST   /api/auth/logout/          Logout user
POST   /api/auth/forgot-password/ Recovery request
POST   /api/auth/reset-password/  Reset password

GET    /api/users/<id>/           Get user details
PUT    /api/users/<id>/           Update user
DELETE /api/users/<id>/           Delete user

GET    /api/countries/            List countries
GET    /api/data/                 List data entries
GET    /api/dashboard-urls/       List dashboard URLs
```

---

This is a scalable, well-structured authentication system ready for expansion! 🚀
