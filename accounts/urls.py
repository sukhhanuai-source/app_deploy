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
    path('dashboard/admin/home/', views.admin_home_view, name='admin_home'),
    path('dashboard/admin/verify-users/', views.admin_verify_users_view, name='admin_verify_users'),
    path('dashboard/admin/create-project/', views.admin_create_project_view, name='admin_create_project'),
    path('dashboard/admin/create-labels/', views.admin_create_labels_view, name='admin_create_labels'),
    path('dashboard/admin/assign-tasks/', views.admin_assign_tasks_view, name='admin_assign_tasks'),
    path('dashboard/admin/anotated-data/', views.admin_annotated_data_view, name='admin_annotated_data'),
    path('assigner/home/', views.assigner_home_view, name='assigner_home'),
    path('assigner/create-project/', views.assigner_create_project_view, name='assigner_create_project'),
    path('assigner/create-labels/', views.assigner_create_labels_view, name='assigner_create_labels'),
    path('assigner/assign-tasks/', views.assigner_assign_tasks_view, name='assigner_assign_tasks'),
    path('annotator/home/', views.annotator_home_view, name='annotator_home'),
    path('annotator/assigned-tasks/', views.annotator_assigned_tasks_view, name='annotator_assigned_tasks'),
    path('reviewer/home/', views.reviewer_home_view, name='reviewer_home'),
    path('reviewer/anotated-data/', views.reviewer_annotated_data_view, name='reviewer_annotated_data'),

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
