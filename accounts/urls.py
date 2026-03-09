from django.urls import path

from . import views

urlpatterns = [
    # Requested page URLs
    path('', views.root_login_view, name='root_login'),
    path('login/', views.login_view, name='login'),
    path('sign_up', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('admin_dash', views.admin_dashboard_view, name='admin_dash'),
    path('assigner_dash', views.assigner_dashboard_view, name='assigner_dash'),
    path('anotater_dash', views.annotater_dashboard_view, name='anotater_dash'),
    path('reviewer_dash', views.reviewer_dashboard_view, name='reviewer_dash'),

    # Existing pages
    path('signup/', views.signup_view, name='signup_legacy'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/<str:token>/', views.reset_password_view, name='reset_password'),
    path('profile/', views.profile_view, name='profile'),
    path('manage-workers/', views.manage_workers_view, name='manage_workers'),
    path('edit-worker/<int:worker_id>/', views.edit_worker_view, name='edit_worker'),

    # Auth API
    path('api/login/', views.api_login_view, name='api_login'),
    path('api/auth/login', views.api_login_view, name='api_auth_login'),
    path('api/auth/me', views.api_me_view, name='api_auth_me'),

    # CVAT-style core APIs
    path('api/organizations', views.api_organizations_view, name='api_organizations'),
    path('api/projects', views.api_projects_view, name='api_projects'),
    path('api/labels', views.api_labels_view, name='api_labels'),
]
