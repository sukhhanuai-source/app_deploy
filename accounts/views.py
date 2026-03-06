import json
import secrets

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .forms import ForgotPasswordForm, LoginForm, ResetPasswordForm, SignUpForm
from .models import Annotation, CustomUser, ImageFrame, Job, Label, Organization, Project, Task


def _serialize_custom_user(user, custom_profile):
    assigned_project = custom_profile.assigned_project
    return {
        "id": custom_profile.id,
        "django_user_id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": custom_profile.role,
        "user_type": custom_profile.user_type,
        "phone_number": custom_profile.phone_number,
        "assigned_s3_path": custom_profile.assigned_s3_path,
        "assigned_project_id": custom_profile.assigned_project_id,
        "assigned_project": _serialize_project(assigned_project) if assigned_project else None,
        "assigned_project_labels": [
            label.name for label in assigned_project.labels.order_by('name')
        ] if assigned_project else [],
        "is_verified": custom_profile.is_verified,
        "created_date": custom_profile.created_date.isoformat() if custom_profile.created_date else None,
        "updated_date": custom_profile.updated_date.isoformat() if custom_profile.updated_date else None,
    }


def _get_custom_profile_or_none(request):
    if not request.user.is_authenticated:
        return None
    try:
        return request.user.custom_profile
    except CustomUser.DoesNotExist:
        return None


def _json_error(message, status=400):
    return JsonResponse({"success": False, "message": message}, status=status)


def _parse_json_body(request):
    try:
        return json.loads(request.body.decode("utf-8")) if request.body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _api_authenticate_request(request):
    if not request.user.is_authenticated:
        return None, _json_error("Authentication required.", status=401)
    profile = _get_custom_profile_or_none(request)
    if not profile:
        return None, _json_error("User profile not found.", status=403)
    return profile, None


def _api_require_roles(profile, allowed_roles):
    if profile.role not in allowed_roles:
        return _json_error("Permission denied.", status=403)
    return None


def _serialize_organization(obj):
    return {
        "id": obj.id,
        "name": obj.name,
        "owner_id": obj.owner_id,
        "created_date": obj.created_date.isoformat() if obj.created_date else None,
    }


def _serialize_project(obj):
    return {
        "id": obj.id,
        "name": obj.name,
        "description": obj.description,
        "owner_id": obj.owner_id,
        "organization_id": obj.organization_id,
        "created_date": obj.created_date.isoformat() if obj.created_date else None,
    }


def _serialize_task(obj):
    return {
        "id": obj.id,
        "name": obj.name,
        "project_id": obj.project_id,
        "owner_id": obj.owner_id,
        "status": obj.status,
        "created_date": obj.created_date.isoformat() if obj.created_date else None,
    }


def _serialize_job(obj):
    return {
        "id": obj.id,
        "task_id": obj.task_id,
        "assignee_id": obj.assignee_id,
        "start_frame": obj.start_frame,
        "stop_frame": obj.stop_frame,
        "created_date": obj.created_date.isoformat() if obj.created_date else None,
    }


def _serialize_image(obj):
    return {
        "id": obj.id,
        "task_id": obj.task_id,
        "frame": obj.frame,
        "path": obj.path,
        "width": obj.width,
        "height": obj.height,
    }


def _serialize_label(obj):
    return {
        "id": obj.id,
        "name": obj.name,
        "project_id": obj.project_id,
        "color": obj.color,
    }


def _serialize_annotation(obj):
    return {
        "id": obj.id,
        "job_id": obj.job_id,
        "label_id": obj.label_id,
        "type": obj.type,
        "frame": obj.frame,
        "coordinates": obj.coordinates,
    }


def _get_or_create_assigner_organization(custom_user):
    organization = Organization.objects.filter(owner=custom_user).order_by('id').first()
    if organization:
        return organization

    base_name = f"{custom_user.django_user.username}-workspace"
    name = base_name
    suffix = 1
    while Organization.objects.filter(name=name).exists():
        suffix += 1
        name = f"{base_name}-{suffix}"

    organization = Organization.objects.create(name=name, owner=custom_user)
    organization.members.add(custom_user)
    return organization


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created successfully! Awaiting admin verification before you can login.')
            return redirect('login')
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
    else:
        form = SignUpForm()

    return render(request, 'accounts/signup.html', {'form': form})


def root_login_view(request):
    """Always serve login page at root without auto-redirecting authenticated users."""
    if request.method == 'POST':
        return login_view(request)
    return render(request, 'accounts/login.html', {'form': LoginForm()})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            if user is None:
                messages.error(request, 'Invalid username or password.')
                return render(request, 'accounts/login.html', {'form': form})

            try:
                custom_profile = user.custom_profile
            except CustomUser.DoesNotExist:
                messages.error(request, 'User profile not found. Contact administrator.')
                return redirect('login')

            if not custom_profile.is_verified:
                messages.error(request, 'Your account is not verified by an administrator yet.')
                return redirect('login')

            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('dashboard')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')


@login_required(login_url='login')
def dashboard_view(request):
    custom_user = _get_custom_profile_or_none(request)
    if not custom_user:
        messages.error(request, 'User profile not found.')
        return redirect('logout')

    if custom_user.role == CustomUser.ROLE_ADMIN:
        return redirect('admin_dash')
    if custom_user.role == CustomUser.ROLE_ASSIGNER:
        return redirect('assigner_dash')
    if custom_user.role == CustomUser.ROLE_REVIEWER:
        return redirect('reviewer_dash')
    return redirect('anotater_dash')


@login_required(login_url='login')
def admin_dashboard_view(request):
    custom_user = _get_custom_profile_or_none(request)
    if not custom_user or custom_user.role != CustomUser.ROLE_ADMIN:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')

    if request.method == 'POST':
        target_user_id = request.POST.get('target_user_id')
        role = request.POST.get('role')
        is_verified = request.POST.get('is_verified') == 'on'

        if not target_user_id or not role:
            messages.error(request, 'target_user_id and role are required.')
            return redirect('admin_dash')

        valid_roles = {choice[0] for choice in CustomUser.ROLE_CHOICES}
        if role not in valid_roles:
            messages.error(request, 'Invalid role selected.')
            return redirect('admin_dash')

        try:
            target_user = CustomUser.objects.select_related('django_user').get(id=target_user_id)
        except CustomUser.DoesNotExist:
            messages.error(request, 'User profile not found.')
            return redirect('admin_dash')

        if target_user.id == custom_user.id and role != CustomUser.ROLE_ADMIN:
            messages.error(request, 'You cannot remove your own admin role from this dashboard.')
            return redirect('admin_dash')

        target_user.role = role
        target_user.is_verified = is_verified
        target_user.save(update_fields=['role', 'is_verified', 'updated_date'])
        messages.success(
            request,
            f"Updated {target_user.django_user.username}: role={target_user.get_role_display()}, verified={target_user.is_verified}.",
        )
        return redirect('admin_dash')

    role_count_map = {item['role']: item['count'] for item in CustomUser.objects.values('role').annotate(count=Count('id'))}
    table_cards = [
        {'name': 'Users', 'count': CustomUser.objects.count(), 'url': '/admin/accounts/customuser/', 'desc': 'Manage user roles and verification.'},
        {'name': 'Organizations', 'count': Organization.objects.count(), 'url': '/admin/accounts/organization/', 'desc': 'Manage organizations and memberships.'},
        {'name': 'Projects', 'count': Project.objects.count(), 'url': '/admin/accounts/project/', 'desc': 'Manage projects under organizations.'},
        {'name': 'Tasks', 'count': Task.objects.count(), 'url': '/admin/accounts/task/', 'desc': 'Manage annotation tasks and status.'},
        {'name': 'Jobs', 'count': Job.objects.count(), 'url': '/admin/accounts/job/', 'desc': 'Manage task splits and assignees.'},
        {'name': 'Images', 'count': ImageFrame.objects.count(), 'url': '/admin/accounts/imageframe/', 'desc': 'Manage frames/images in tasks.'},
        {'name': 'Labels', 'count': Label.objects.count(), 'url': '/admin/accounts/label/', 'desc': 'Manage project label classes.'},
        {'name': 'Annotations', 'count': Annotation.objects.count(), 'url': '/admin/accounts/annotation/', 'desc': 'Manage annotation objects.'},
    ]
    users = CustomUser.objects.select_related('django_user').order_by('django_user__username')

    return render(
        request,
        'accounts/admin_dashboard.html',
        {
            'custom_user': custom_user,
            'user_type': custom_user.user_type,
            'table_cards': table_cards,
            'users': users,
            'role_choices': CustomUser.ROLE_CHOICES,
            'role_counts': {
                'admin': role_count_map.get(CustomUser.ROLE_ADMIN, 0),
                'assigner': role_count_map.get(CustomUser.ROLE_ASSIGNER, 0),
                'annotator': role_count_map.get(CustomUser.ROLE_ANNOTATOR, 0),
                'reviewer': role_count_map.get(CustomUser.ROLE_REVIEWER, 0),
            },
        },
    )


@login_required(login_url='login')
def assigner_dashboard_view(request):
    custom_user = _get_custom_profile_or_none(request)
    if not custom_user or custom_user.role != CustomUser.ROLE_ASSIGNER:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_project':
            name = (request.POST.get('project_name') or '').strip()
            description = (request.POST.get('project_description') or '').strip()
            if not name:
                messages.error(request, 'Project name is required.')
                return redirect('assigner_dash')

            organization = _get_or_create_assigner_organization(custom_user)
            try:
                Project.objects.create(
                    name=name,
                    description=description,
                    owner=custom_user,
                    organization=organization,
                )
            except IntegrityError:
                messages.error(request, f'Project "{name}" already exists in your workspace.')
                return redirect('assigner_dash')

            messages.success(request, f'Project "{name}" created successfully.')
            return redirect('assigner_dash')

        if action == 'create_label':
            project_id = request.POST.get('project_id')
            label_name = (request.POST.get('label_name') or '').strip()
            color = (request.POST.get('label_color') or '#FF5733').strip() or '#FF5733'
            if not project_id or not label_name:
                messages.error(request, 'Project and label name are required.')
                return redirect('assigner_dash')

            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                messages.error(request, 'Project not found.')
                return redirect('assigner_dash')

            try:
                Label.objects.create(project=project, name=label_name, color=color)
            except IntegrityError:
                messages.error(request, f'Label "{label_name}" already exists in project "{project.name}".')
                return redirect('assigner_dash')

            messages.success(request, f'Label "{label_name}" added to project "{project.name}".')
            return redirect('assigner_dash')

        annotator_id = request.POST.get('annotator_id')
        assigned_s3_path = (request.POST.get('assigned_s3_path') or '').strip()
        project_id = request.POST.get('assigned_project_id')

        if not annotator_id:
            messages.error(request, 'Select an annotator to assign bucket path and project.')
            return redirect('assigner_dash')

        try:
            annotator = CustomUser.objects.select_related('django_user').get(
                id=annotator_id,
                role=CustomUser.ROLE_ANNOTATOR,
            )
        except CustomUser.DoesNotExist:
            messages.error(request, 'Annotator not found.')
            return redirect('assigner_dash')

        assigned_project = None
        if project_id:
            try:
                assigned_project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                messages.error(request, 'Assigned project not found.')
                return redirect('assigner_dash')

        annotator.assigned_s3_path = assigned_s3_path
        annotator.assigned_project = assigned_project
        annotator.save(update_fields=['assigned_s3_path', 'assigned_project', 'updated_date'])
        project_message = assigned_project.name if assigned_project else 'No project'
        messages.success(
            request,
            f"Updated {annotator.django_user.username}: path={assigned_s3_path or 'cleared'}, project={project_message}.",
        )
        return redirect('assigner_dash')

    annotators = CustomUser.objects.filter(role=CustomUser.ROLE_ANNOTATOR).select_related(
        'django_user',
        'assigned_project',
    ).prefetch_related('assigned_project__labels')
    projects = Project.objects.filter(owner=custom_user).select_related('organization').prefetch_related('labels').order_by('name')
    return render(
        request,
        'accounts/worker_dashboard.html',
        {
            'custom_user': custom_user,
            'user_type': custom_user.user_type,
            'dashboard_title': 'Assigner Dashboard',
            'annotators': annotators,
            'projects': projects,
        },
    )


@login_required(login_url='login')
def annotater_dashboard_view(request):
    custom_user = _get_custom_profile_or_none(request)
    if not custom_user or custom_user.role != CustomUser.ROLE_ANNOTATOR:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    return render(
        request,
        'accounts/worker_dashboard.html',
        {
            'custom_user': custom_user,
            'user_type': custom_user.user_type,
            'dashboard_title': 'Annotator Dashboard',
        },
    )


@login_required(login_url='login')
def reviewer_dashboard_view(request):
    custom_user = _get_custom_profile_or_none(request)
    if not custom_user or custom_user.role != CustomUser.ROLE_REVIEWER:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    return render(
        request,
        'accounts/worker_dashboard.html',
        {'custom_user': custom_user, 'user_type': custom_user.user_type, 'dashboard_title': 'Reviewer Dashboard'},
    )


def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
            except User.MultipleObjectsReturned:
                user = User.objects.filter(email=email).order_by('id').first()
            except User.DoesNotExist:
                messages.error(request, 'No user found with this email.')
                return render(request, 'accounts/forgot_password.html', {'form': form})

            reset_token = secrets.token_urlsafe(32)
            request.session[f'reset_token_{user.id}'] = reset_token
            request.session['reset_user_id'] = user.id

            messages.success(request, 'Check your email for password reset instructions.')
            return redirect('reset_password', token=reset_token)
    else:
        form = ForgotPasswordForm()

    return render(request, 'accounts/forgot_password.html', {'form': form})


def reset_password_view(request, token=None):
    if request.user.is_authenticated:
        return redirect('dashboard')

    user_id = request.session.get('reset_user_id')
    if not user_id or request.session.get(f'reset_token_{user_id}') != token:
        messages.error(request, 'Invalid reset link.')
        return redirect('login')

    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                messages.error(request, 'User not found.')
                return render(request, 'accounts/reset_password.html', {'form': form})

            user.set_password(form.cleaned_data['password1'])
            user.save()
            del request.session[f'reset_token_{user_id}']
            del request.session['reset_user_id']
            messages.success(request, 'Password reset successfully! You can now login.')
            return redirect('login')
    else:
        form = ResetPasswordForm()

    return render(request, 'accounts/reset_password.html', {'form': form})


@login_required(login_url='login')
def profile_view(request):
    custom_user = _get_custom_profile_or_none(request)
    if not custom_user:
        messages.error(request, 'User profile not found.')
        return redirect('logout')
    return render(request, 'accounts/profile.html', {'custom_user': custom_user})


@login_required(login_url='login')
def manage_workers_view(request):
    custom_user = _get_custom_profile_or_none(request)
    if not custom_user:
        messages.error(request, 'User profile not found.')
        return redirect('logout')

    if custom_user.role != CustomUser.ROLE_ADMIN:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')

    workers = CustomUser.objects.filter(role=CustomUser.ROLE_ANNOTATOR).select_related('django_user')
    return render(request, 'accounts/manage_workers.html', {'workers': workers})


@login_required(login_url='login')
def edit_worker_view(request, worker_id):
    admin_user = _get_custom_profile_or_none(request)
    if not admin_user:
        messages.error(request, 'User profile not found.')
        return redirect('logout')

    if admin_user.role != CustomUser.ROLE_ADMIN:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')

    try:
        worker = CustomUser.objects.get(id=worker_id, role=CustomUser.ROLE_ANNOTATOR)
    except CustomUser.DoesNotExist:
        messages.error(request, 'Worker not found.')
        return redirect('manage_workers')

    if request.method == 'POST':
        worker.is_verified = request.POST.get('is_verified') == 'on'
        worker.save()
        messages.success(request, f'Worker {worker.django_user.username} updated successfully!')
        return redirect('manage_workers')

    context = {
        'worker': worker,
        'countries': [],
        'data_list': [],
        'dashboard_urls': [],
    }
    return render(request, 'accounts/edit_worker.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def api_login_view(request):
    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("Invalid JSON body.", status=400)

    username = payload.get("username") or request.POST.get("username")
    password = payload.get("password") or request.POST.get("password")
    if not username or not password:
        return _json_error("username and password are required.", status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return _json_error("Invalid credentials.", status=401)

    try:
        profile = user.custom_profile
    except CustomUser.DoesNotExist:
        return _json_error("User profile not found. Contact administrator.", status=403)

    if not profile.is_verified:
        return _json_error("Account is not verified by an administrator yet.", status=403)

    login(request, user)
    return JsonResponse(
        {
            "success": True,
            "message": "Login successful.",
            "session_key": request.session.session_key,
            "user": _serialize_custom_user(user, profile),
        }
    )


@require_http_methods(["GET"])
def api_me_view(request):
    profile, error = _api_authenticate_request(request)
    if error:
        return error
    return JsonResponse({"success": True, "user": _serialize_custom_user(request.user, profile)})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_organizations_view(request):
    profile, error = _api_authenticate_request(request)
    if error:
        return error

    if request.method == 'GET':
        qs = Organization.objects.all().select_related('owner__django_user')
        return JsonResponse({"success": True, "results": [_serialize_organization(o) for o in qs]})

    denied = _api_require_roles(profile, {CustomUser.ROLE_ADMIN, CustomUser.ROLE_ASSIGNER})
    if denied:
        return denied

    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("Invalid JSON body.")

    name = payload.get('name')
    if not name:
        return _json_error("name is required.")

    obj = Organization.objects.create(name=name, owner=profile)
    obj.members.add(profile)
    return JsonResponse({"success": True, "organization": _serialize_organization(obj)}, status=201)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_projects_view(request):
    profile, error = _api_authenticate_request(request)
    if error:
        return error

    if request.method == 'GET':
        qs = Project.objects.all().select_related('organization', 'owner__django_user')
        org_id = request.GET.get('organization_id')
        if org_id:
            qs = qs.filter(organization_id=org_id)
        return JsonResponse({"success": True, "results": [_serialize_project(p) for p in qs]})

    denied = _api_require_roles(profile, {CustomUser.ROLE_ADMIN, CustomUser.ROLE_ASSIGNER})
    if denied:
        return denied

    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("Invalid JSON body.")

    name = payload.get('name')
    organization_id = payload.get('organization_id')
    if not name or not organization_id:
        return _json_error("name and organization_id are required.")

    try:
        organization = Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        return _json_error("organization not found.", status=404)

    obj = Project.objects.create(
        name=name,
        description=payload.get('description', ''),
        owner=profile,
        organization=organization,
    )
    return JsonResponse({"success": True, "project": _serialize_project(obj)}, status=201)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_tasks_view(request):
    profile, error = _api_authenticate_request(request)
    if error:
        return error

    if request.method == 'GET':
        qs = Task.objects.all().select_related('project', 'owner__django_user')
        project_id = request.GET.get('project_id')
        if project_id:
            qs = qs.filter(project_id=project_id)
        return JsonResponse({"success": True, "results": [_serialize_task(t) for t in qs]})

    denied = _api_require_roles(profile, {CustomUser.ROLE_ADMIN, CustomUser.ROLE_ASSIGNER})
    if denied:
        return denied

    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("Invalid JSON body.")

    name = payload.get('name')
    project_id = payload.get('project_id')
    if not name or not project_id:
        return _json_error("name and project_id are required.")

    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return _json_error("project not found.", status=404)

    status_value = payload.get('status', Task.STATUS_CREATED)
    if status_value not in {Task.STATUS_CREATED, Task.STATUS_IN_PROGRESS, Task.STATUS_COMPLETED}:
        return _json_error("invalid status.")

    obj = Task.objects.create(name=name, project=project, owner=profile, status=status_value)
    return JsonResponse({"success": True, "task": _serialize_task(obj)}, status=201)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_jobs_view(request):
    profile, error = _api_authenticate_request(request)
    if error:
        return error

    if request.method == 'GET':
        qs = Job.objects.all().select_related('task', 'assignee__django_user')
        task_id = request.GET.get('task_id')
        if task_id:
            qs = qs.filter(task_id=task_id)
        return JsonResponse({"success": True, "results": [_serialize_job(j) for j in qs]})

    denied = _api_require_roles(profile, {CustomUser.ROLE_ADMIN, CustomUser.ROLE_ASSIGNER})
    if denied:
        return denied

    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("Invalid JSON body.")

    task_id = payload.get('task_id')
    start_frame = payload.get('start_frame', 0)
    stop_frame = payload.get('stop_frame')
    assignee_id = payload.get('assignee_id')
    if task_id is None or stop_frame is None:
        return _json_error("task_id and stop_frame are required.")

    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return _json_error("task not found.", status=404)

    assignee = None
    if assignee_id is not None:
        try:
            assignee = CustomUser.objects.get(id=assignee_id)
        except CustomUser.DoesNotExist:
            return _json_error("assignee not found.", status=404)

    obj = Job.objects.create(task=task, assignee=assignee, start_frame=start_frame, stop_frame=stop_frame)
    return JsonResponse({"success": True, "job": _serialize_job(obj)}, status=201)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_images_view(request):
    profile, error = _api_authenticate_request(request)
    if error:
        return error

    if request.method == 'GET':
        qs = ImageFrame.objects.all().select_related('task')
        task_id = request.GET.get('task_id')
        if task_id:
            qs = qs.filter(task_id=task_id)
        return JsonResponse({"success": True, "results": [_serialize_image(i) for i in qs]})

    denied = _api_require_roles(profile, {CustomUser.ROLE_ADMIN, CustomUser.ROLE_ASSIGNER})
    if denied:
        return denied

    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("Invalid JSON body.")

    required = ['task_id', 'frame', 'path', 'width', 'height']
    if any(payload.get(key) in (None, '') for key in required):
        return _json_error("task_id, frame, path, width, and height are required.")

    try:
        task = Task.objects.get(id=payload['task_id'])
    except Task.DoesNotExist:
        return _json_error("task not found.", status=404)

    obj = ImageFrame.objects.create(
        task=task,
        frame=payload['frame'],
        path=payload['path'],
        width=payload['width'],
        height=payload['height'],
    )
    return JsonResponse({"success": True, "image": _serialize_image(obj)}, status=201)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_labels_view(request):
    profile, error = _api_authenticate_request(request)
    if error:
        return error

    if request.method == 'GET':
        qs = Label.objects.all().select_related('project')
        project_id = request.GET.get('project_id')
        if project_id:
            qs = qs.filter(project_id=project_id)
        return JsonResponse({"success": True, "results": [_serialize_label(l) for l in qs]})

    denied = _api_require_roles(profile, {CustomUser.ROLE_ADMIN, CustomUser.ROLE_ASSIGNER})
    if denied:
        return denied

    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("Invalid JSON body.")

    if not payload.get('name') or not payload.get('project_id'):
        return _json_error("name and project_id are required.")

    try:
        project = Project.objects.get(id=payload['project_id'])
    except Project.DoesNotExist:
        return _json_error("project not found.", status=404)

    obj = Label.objects.create(name=payload['name'], project=project, color=payload.get('color', '#FF5733'))
    return JsonResponse({"success": True, "label": _serialize_label(obj)}, status=201)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_annotations_view(request):
    profile, error = _api_authenticate_request(request)
    if error:
        return error

    if request.method == 'GET':
        qs = Annotation.objects.all().select_related('job', 'label')
        job_id = request.GET.get('job_id')
        if job_id:
            qs = qs.filter(job_id=job_id)
        return JsonResponse({"success": True, "results": [_serialize_annotation(a) for a in qs]})

    denied = _api_require_roles(
        profile,
        {CustomUser.ROLE_ADMIN, CustomUser.ROLE_ASSIGNER, CustomUser.ROLE_ANNOTATOR, CustomUser.ROLE_REVIEWER},
    )
    if denied:
        return denied

    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("Invalid JSON body.")

    required = ['job_id', 'label_id', 'type', 'frame', 'coordinates']
    if any(payload.get(key) is None for key in required):
        return _json_error("job_id, label_id, type, frame, and coordinates are required.")

    try:
        job = Job.objects.get(id=payload['job_id'])
    except Job.DoesNotExist:
        return _json_error("job not found.", status=404)

    try:
        label = Label.objects.get(id=payload['label_id'])
    except Label.DoesNotExist:
        return _json_error("label not found.", status=404)

    valid_types = {choice[0] for choice in Annotation.TYPE_CHOICES}
    if payload['type'] not in valid_types:
        return _json_error("invalid annotation type.")

    obj = Annotation.objects.create(
        job=job,
        label=label,
        type=payload['type'],
        frame=payload['frame'],
        coordinates=payload['coordinates'],
    )
    return JsonResponse({"success": True, "annotation": _serialize_annotation(obj)}, status=201)
