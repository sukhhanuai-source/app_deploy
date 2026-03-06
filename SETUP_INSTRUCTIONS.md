# Django Authentication System with Role-Based Dashboards

A complete Django project with user authentication, role-based dashboards (Worker/Admin), and a comprehensive database structure.

## Features

- ✅ **User Authentication**: Signup, Login, Logout
- ✅ **Password Recovery**: Forgot Password & Reset Password
- ✅ **Role-Based Access**: Two user types - Worker and Admin
- ✅ **Different Dashboards**: Unique dashboards for Worker (Hello Family) and Admin (Hi Admin)
- ✅ **Database Models**:
  - **User**: Custom user profile with name, password, email, phone, user type
  - **Country**: Country master data
  - **Data**: Data entries linked to countries
  - **DashboardURL**: URLs for different dashboards
- ✅ **Django Admin Panel**: Full management interface
- ✅ **Responsive UI**: Bootstrap 5 styled templates

## Database Structure

### Tables

1. **CustomUser**
   - django_user (OneToOne with Django User)
   - user_type (worker/admin)
   - phone_number
   - country (FK to Country)
   - dashboard_url (FK to DashboardURL)

2. **Country**
   - name
   - created_at

3. **Data**
   - name
   - country (FK to Country)
   - data_type
   - created_at
   - updated_at

4. **DashboardURL**
   - name
   - url
   - created_at

## Installation

### 1. Clone the repository and navigate to the project
```bash
cd "c:\Users\Anand\Desktop\New folder"
```

### 2. Create a virtual environment (optional but recommended)
```bash
python -m venv venv
venv\Scripts\activate  # On Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run migrations
```bash
python manage.py migrate
```

### 5. Create a superuser (admin)
```bash
python manage.py createsuperuser
```

### 6. Populate initial data (optional)
```bash
python manage.py shell
```

Then in the Python shell:
```python
from accounts.models import Country, DashboardURL

# Create countries
Country.objects.create(name="United States")
Country.objects.create(name="Canada")
Country.objects.create(name="UK")

# Create dashboard URLs
DashboardURL.objects.create(name="Worker Dashboard", url="/dashboard/")
DashboardURL.objects.create(name="Admin Dashboard", url="/admin/")
exit()
```

### 7. Run the development server
```bash
python manage.py runserver
```

The application will be available at: `http://localhost:8000`

## Usage

### URLs

- **Home/Dashboard**: `http://localhost:8000/`
- **Login**: `http://localhost:8000/login/`
- **Sign Up**: `http://localhost:8000/signup/`
- **Forgot Password**: `http://localhost:8000/forgot-password/`
- **Profile**: `http://localhost:8000/profile/`
- **Admin Panel**: `http://localhost:8000/admin/`

### User Types and Dashboards

1. **Worker Dashboard**
   - Shows: "Hello Family" greeting
   - Can view their profile and security settings

2. **Admin Dashboard**
   - Shows: "Hi Admin" greeting
   - Can access Django admin panel
   - Can manage all users, countries, data, and dashboard URLs

## Project Structure

```
myproject/
├── myproject/
│   ├── __init__.py
│   ├── settings.py       # Django settings
│   ├── urls.py           # Main URL configuration
│   └── wsgi.py           # WSGI application
├── accounts/
│   ├── migrations/       # Database migrations
│   ├── __init__.py
│   ├── admin.py          # Django admin configuration
│   ├── apps.py           # App configuration
│   ├── forms.py          # Authentication forms
│   ├── models.py         # Database models
│   ├── tests.py          # Unit tests
│   ├── urls.py           # App URL configuration
│   └── views.py          # View functions
├── templates/
│   ├── base.html         # Base template
│   └── accounts/
│       ├── login.html
│       ├── signup.html
│       ├── forgot_password.html
│       ├── reset_password.html
│       ├── profile.html
│       ├── worker_dashboard.html
│       ├── admin_dashboard.html
│       └── dashboard.html
├── manage.py             # Django management script
├── db.sqlite3            # SQLite database (created after migration)
└── requirements.txt      # Python dependencies
```

## Creating Test Users

### Worker User
1. Go to `http://localhost:8000/signup/`
2. Fill in the form and select **Worker** as user type
3. Complete signup and login

### Admin User
1. Use the superuser created with `createsuperuser`
2. Or create a new user in Django admin and set user_type to "admin"

## Customization

### Modify Dashboard Messages

- **Worker Dashboard**: Edit [templates/accounts/worker_dashboard.html](templates/accounts/worker_dashboard.html)
- **Admin Dashboard**: Edit [templates/accounts/admin_dashboard.html](templates/accounts/admin_dashboard.html)

### Add More Fields to User Profile

Edit the `CustomUser` model in [accounts/models.py](accounts/models.py) and create a new migration:
```bash
python manage.py makemigrations
python manage.py migrate
```

## Security Notes

⚠️ **For Production**:
- Change `SECRET_KEY` in settings.py
- Set `DEBUG = False`
- Configure `ALLOWED_HOSTS`
- Use a production-grade database (PostgreSQL, MySQL)
- Implement proper email backend for password reset
- Set up HTTPS
- Use environment variables for sensitive data

## Troubleshooting

### Port Already in Use
```bash
python manage.py runserver 8001  # Use different port
```

### Database Lock Issues
```bash
rm db.sqlite3
python manage.py migrate
```

### Static Files Not Loading
```bash
python manage.py collectstatic
```

## Future Enhancements

- [ ] Email-based password reset
- [ ] Two-factor authentication
- [ ] User profile image upload
- [ ] Activity logging
- [ ] API endpoints with Django REST Framework
- [ ] Email notifications
- [ ] Better password reset token management

## License

This project is open source and available under the MIT License.

## Support

For issues or questions, refer to [Django Documentation](https://docs.djangoproject.com/)
