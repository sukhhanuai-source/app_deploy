"""
Script to populate initial data into the database.
Run this with: python manage.py shell < populate_data.py
"""

from accounts.models import Country, DashboardURL, CustomUser
from django.contrib.auth.models import User

# Create countries if they don't exist
countries_data = [
    "United States",
    "Canada",
    "United Kingdom",
    "India",
    "Australia",
    "Germany",
    "France",
    "Japan"
]

for country_name in countries_data:
    Country.objects.get_or_create(name=country_name)

print(f"✅ Created {len(countries_data)} countries")

# Create dashboard URLs if they don't exist
dashboard_urls = [
    {"name": "Worker Dashboard", "url": "/dashboard/"},
    {"name": "Admin Dashboard", "url": "/admin/"},
    {"name": "Reports", "url": "/reports/"},
    {"name": "Settings", "url": "/settings/"}
]

for url_data in dashboard_urls:
    DashboardURL.objects.get_or_create(
        name=url_data["name"],
        defaults={"url": url_data["url"]}
    )

print(f"✅ Created {len(dashboard_urls)} dashboard URLs")

# Create a test worker user if it doesn't exist
if not User.objects.filter(username='testworker').exists():
    worker = User.objects.create_user(
        username='testworker',
        email='worker@example.com',
        password='worker123',
        first_name='Test',
        last_name='Worker'
    )
    CustomUser.objects.create(
        django_user=worker,
        user_type='worker',
        phone_number='+1234567890',
        country=Country.objects.first()
    )
    print("✅ Created test worker user (username: testworker, password: worker123)")

# Create a test admin user if it doesn't exist (non-superuser admin)
if not User.objects.filter(username='testadmin').exists():
    admin = User.objects.create_user(
        username='testadmin',
        email='testadmin@example.com',
        password='admin123',
        first_name='Test',
        last_name='Admin'
    )
    CustomUser.objects.create(
        django_user=admin,
        user_type='admin',
        phone_number='+0987654321',
        country=Country.objects.first()
    )
    print("✅ Created test admin user (username: testadmin, password: admin123)")

print("\n✅ All initial data has been populated successfully!")
print("\nTest Credentials:")
print("  Worker: testworker / worker123")
print("  Admin (app): testadmin / admin123")
print("  Superuser: admin / admin")
