import base64
import io
import json
import os
import secrets
from datetime import datetime
from urllib.parse import parse_qs, quote, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from PIL import Image, ImageDraw, ImageFont

try:
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:  # pragma: no cover - botocore is optional at import time
    BotoCoreError = Exception
    ClientError = Exception

from .forms import ForgotPasswordForm, LoginForm, ResetPasswordForm, SignUpForm
from .models import (
    AnnotatorBucketAssignment,
    CustomUser,
    Label,
    Organization,
    Project,
)


ASSIGNMENT_PROGRESS_FILE = 'annotation_progress.json'
ASSIGNMENT_IMAGE_EXTENSIONS = {
    '.jpg',
    '.jpeg',
    '.png',
    '.bmp',
    '.webp',
    '.tif',
    '.tiff',
}
ASSIGNMENT_STATUS_QUEUE = 'queue'
ASSIGNMENT_STATUS_IN_PROGRESS = 'in_progress'
ASSIGNMENT_STATUS_COMPLETE = 'complete'
ASSIGNMENT_STATUS_UNAVAILABLE = 'unavailable'


def _serialize_bucket_assignment(obj):
    return {
        "id": obj.id,
        "display_name": obj.display_name,
        "s3_path": obj.s3_path,
        "project_id": obj.project_id,
        "project_name": obj.project.name if obj.project_id else "",
        "project_labels": [label.name for label in obj.project.labels.order_by('name')] if obj.project_id else [],
    }


def _serialize_custom_user(user, custom_profile):
    assigned_project = custom_profile.assigned_project
    bucket_assignments = list(custom_profile.bucket_assignments.select_related('project').prefetch_related('project__labels'))
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
        "bucket_assignments": [_serialize_bucket_assignment(item) for item in bucket_assignments],
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


def _serialize_label(obj):
    return {
        "id": obj.id,
        "name": obj.name,
        "project_id": obj.project_id,
        "color": obj.color,
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


def _load_key_value_env_file(env_path):
    values = {}
    if not os.path.exists(env_path):
        return values
    with open(env_path, encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def _get_review_s3_config():
    env_file_values = _load_key_value_env_file(settings.BASE_DIR.parent / 'labelme' / '.env')

    def pick(*keys, default=''):
        for key in keys:
            if os.environ.get(key):
                return os.environ[key]
            if env_file_values.get(key):
                return env_file_values[key]
        return default

    return {
        'aws_access_key_id': pick('AWS_ACCESS_KEY_ID', 'AWS_ACCESS_KEY'),
        'aws_secret_access_key': pick('AWS_SECRET_ACCESS_KEY', 'AWS_SECRET_KEY'),
        'aws_session_token': pick('AWS_SESSION_TOKEN'),
        'region_name': pick('AWS_REGION', 'AWS_DEFAULT_REGION', 'AWS_S3_REGION_NAME', default='ap-south-1'),
        'bucket': pick('S3_BUCKET', 'AWS_S3_BUCKET', 'AWS_STORAGE_BUCKET_NAME', default='raiotransection'),
        'root_prefix': pick('S3_ROOT_PREFIX', default='sukh'),
        'endpoint_url': pick('S3_ENDPOINT_URL', 'AWS_S3_ENDPOINT_URL'),
    }


def _get_review_s3_client():
    config = _get_review_s3_config()
    if not config['aws_access_key_id'] or not config['aws_secret_access_key']:
        return None

    try:
        import boto3
    except Exception:
        return None

    client_kwargs = {
        'aws_access_key_id': config['aws_access_key_id'],
        'aws_secret_access_key': config['aws_secret_access_key'],
        'region_name': config['region_name'],
    }
    if config['aws_session_token']:
        client_kwargs['aws_session_token'] = config['aws_session_token']
    if config['endpoint_url']:
        client_kwargs['endpoint_url'] = config['endpoint_url']
    return boto3.client('s3', **client_kwargs)


def _utc_now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _parse_assignment_s3_path(raw_path):
    value = (raw_path or '').strip()
    if not value:
        return '', ''

    if value.startswith('http://') or value.startswith('https://'):
        parsed = urlparse(value)
        path_parts = [part for part in parsed.path.split('/') if part]
        query = parse_qs(parsed.query)
        if len(path_parts) >= 3 and path_parts[0] == 's3' and path_parts[1] == 'buckets':
            bucket = path_parts[2].strip()
            prefix = (query.get('prefix') or [''])[0].strip().lstrip('/')
            return bucket, prefix.rstrip('/')

    if value.startswith('s3://'):
        parsed = urlparse(value)
        return parsed.netloc.strip(), parsed.path.lstrip('/').rstrip('/')

    normalized = value.lstrip('/')
    if '/' in normalized:
        bucket, prefix = normalized.split('/', 1)
        return bucket.strip(), prefix.strip().rstrip('/')

    return normalized.strip(), ''


def _assignment_progress_key(prefix):
    normalized = (prefix or '').strip('/')
    if not normalized:
        return ASSIGNMENT_PROGRESS_FILE
    return f'{normalized}/{ASSIGNMENT_PROGRESS_FILE}'


def _assignment_list_prefix(prefix):
    normalized = (prefix or '').strip('/')
    if not normalized:
        return ''
    extension = os.path.splitext(normalized)[1].lower()
    if extension in ASSIGNMENT_IMAGE_EXTENSIONS:
        return normalized
    return f'{normalized}/'


def _normalize_annotation_entries(raw_entries):
    normalized_entries = {}

    if isinstance(raw_entries, dict):
        items = raw_entries.items()
    elif isinstance(raw_entries, list):
        items = [
            (
                item.get('image_key') if isinstance(item, dict) else '',
                item,
            )
            for item in raw_entries
        ]
    else:
        items = []

    for image_key, raw_entry in items:
        if not isinstance(raw_entry, dict):
            continue

        resolved_image_key = str(raw_entry.get('image_key') or image_key or '').strip().lstrip('/')
        if not resolved_image_key:
            continue

        annotation_key = str(raw_entry.get('annotation_key') or '').strip().lstrip('/')
        normalized_entry = dict(raw_entry)
        normalized_entry.update(
            {
                'image_bucket': str(raw_entry.get('image_bucket') or '').strip(),
                'image_key': resolved_image_key,
                'image_name': str(raw_entry.get('image_name') or os.path.basename(resolved_image_key)).strip(),
                'annotation_bucket': str(raw_entry.get('annotation_bucket') or '').strip(),
                'annotation_key': annotation_key,
                'annotation_name': str(
                    raw_entry.get('annotation_name') or os.path.basename(annotation_key)
                ).strip(),
                'annotated_by': str(raw_entry.get('annotated_by') or '').strip(),
                'annotated_at_utc': str(raw_entry.get('annotated_at_utc') or '').strip(),
            }
        )
        normalized_entries[resolved_image_key] = normalized_entry

    return normalized_entries


def _read_assignment_progress_json(s3_client, bucket, key):
    if s3_client is None or not bucket or not key:
        return {}

    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        raw_bytes = response['Body'].read()
    except ClientError as exc:
        error_code = (exc.response.get('Error') or {}).get('Code')
        if error_code in {'404', 'NoSuchKey', 'NotFound'}:
            return {}
        return {}
    except BotoCoreError:
        return {}
    except Exception:
        return {}

    try:
        payload = json.loads(raw_bytes.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}

    return payload if isinstance(payload, dict) else {}


def _write_assignment_progress_json(s3_client, bucket, key, payload):
    if s3_client is None or not bucket or not key:
        return False

    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(payload, indent=2, sort_keys=True).encode('utf-8'),
            ContentType='application/json',
        )
    except (BotoCoreError, ClientError, TypeError, ValueError):
        return False
    except Exception:
        return False
    return True


def _list_assignment_image_keys(s3_client, bucket, prefix):
    if s3_client is None or not bucket:
        return None

    request_kwargs = {'Bucket': bucket}
    list_prefix = _assignment_list_prefix(prefix)
    if list_prefix:
        request_kwargs['Prefix'] = list_prefix

    image_keys = set()
    progress_key = _assignment_progress_key(prefix)

    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(**request_kwargs):
            for item in page.get('Contents', []):
                key = item.get('Key', '')
                if not key or key.endswith('/') or key == progress_key:
                    continue
                if os.path.splitext(key)[1].lower() not in ASSIGNMENT_IMAGE_EXTENSIONS:
                    continue
                image_keys.add(key)
    except (BotoCoreError, ClientError):
        return None
    except Exception:
        return None

    return sorted(image_keys)


def _assignment_progress_percent(total_frames, annotated_frames):
    if total_frames <= 0:
        return 0.0
    return round(min(annotated_frames, total_frames) * 100.0 / total_frames, 2)


def _assignment_progress_status(annotated_frames, manual_complete):
    if manual_complete:
        return ASSIGNMENT_STATUS_COMPLETE
    if annotated_frames <= 0:
        return ASSIGNMENT_STATUS_QUEUE
    return ASSIGNMENT_STATUS_IN_PROGRESS


def _assignment_progress_status_label(status):
    return {
        ASSIGNMENT_STATUS_QUEUE: 'Queue',
        ASSIGNMENT_STATUS_IN_PROGRESS: 'In Progress',
        ASSIGNMENT_STATUS_COMPLETE: 'Complete',
        ASSIGNMENT_STATUS_UNAVAILABLE: 'Unavailable',
    }.get(status, 'Queue')


def _assignment_progress_badge_class(status):
    return {
        ASSIGNMENT_STATUS_QUEUE: 'bg-secondary',
        ASSIGNMENT_STATUS_IN_PROGRESS: 'bg-warning text-dark',
        ASSIGNMENT_STATUS_COMPLETE: 'bg-success',
        ASSIGNMENT_STATUS_UNAVAILABLE: 'bg-dark',
    }.get(status, 'bg-secondary')


def _assignment_progress_bar_class(status):
    return {
        ASSIGNMENT_STATUS_QUEUE: 'bg-secondary',
        ASSIGNMENT_STATUS_IN_PROGRESS: 'bg-warning',
        ASSIGNMENT_STATUS_COMPLETE: 'bg-success',
        ASSIGNMENT_STATUS_UNAVAILABLE: 'bg-dark',
    }.get(status, 'bg-secondary')


def _decorate_assignment_progress_payload(payload):
    decorated = dict(payload or {})
    status = decorated.get('status') or ASSIGNMENT_STATUS_QUEUE
    bucket = decorated.get('progress_json_bucket') or decorated.get('input_bucket') or ''
    key = decorated.get('progress_json_key') or ''
    decorated['status_label'] = _assignment_progress_status_label(status)
    decorated['status_badge_class'] = _assignment_progress_badge_class(status)
    decorated['status_bar_class'] = _assignment_progress_bar_class(status)
    decorated['progress_json_s3_uri'] = f's3://{bucket}/{key}' if bucket and key else ''
    return decorated


def _base_assignment_progress_payload(assignment, bucket='', prefix=''):
    progress_key = _assignment_progress_key(prefix)
    return {
        'version': 1,
        'display_name': assignment.display_name or assignment.s3_path,
        's3_path': assignment.s3_path,
        'project_name': assignment.project.name if assignment.project_id else '',
        'annotator_username': assignment.annotator.django_user.username,
        'input_bucket': bucket,
        'input_prefix': prefix,
        'progress_json_bucket': bucket,
        'progress_json_key': progress_key,
        'total_frames': 0,
        'annotated_frames': 0,
        'pending_frames': 0,
        'progress_percent': 0.0,
        'status': ASSIGNMENT_STATUS_QUEUE,
        'manual_complete': False,
        'manual_complete_by': '',
        'manual_complete_at_utc': '',
        'updated_at_utc': '',
        'annotation_entries': {},
        'sync_error': '',
    }


def _sync_assignment_progress(assignment, manual_complete_override=None, manual_actor=''):
    bucket, prefix = _parse_assignment_s3_path(assignment.s3_path)
    payload = _base_assignment_progress_payload(assignment, bucket=bucket, prefix=prefix)

    if not bucket:
        payload['status'] = ASSIGNMENT_STATUS_UNAVAILABLE
        payload['sync_error'] = 'Bucket path is not a valid S3 location.'
        return _decorate_assignment_progress_payload(payload)

    s3_client = _get_review_s3_client()
    if s3_client is None:
        payload['status'] = ASSIGNMENT_STATUS_UNAVAILABLE
        payload['sync_error'] = 'S3 client is not configured.'
        return _decorate_assignment_progress_payload(payload)

    existing_payload = _read_assignment_progress_json(
        s3_client=s3_client,
        bucket=bucket,
        key=payload['progress_json_key'],
    )
    payload.update(existing_payload)
    payload.update(
        {
            'version': 1,
            'display_name': assignment.display_name or assignment.s3_path,
            's3_path': assignment.s3_path,
            'project_name': assignment.project.name if assignment.project_id else '',
            'annotator_username': assignment.annotator.django_user.username,
            'input_bucket': bucket,
            'input_prefix': prefix,
            'progress_json_bucket': bucket,
            'progress_json_key': payload['progress_json_key'],
        }
    )

    annotation_entries = _normalize_annotation_entries(payload.get('annotation_entries'))
    image_keys = _list_assignment_image_keys(s3_client=s3_client, bucket=bucket, prefix=prefix)

    if image_keys is None:
        total_frames = int(payload.get('total_frames') or len(annotation_entries) or 0)
        payload['sync_error'] = 'Could not list S3 objects for this bucket path.'
    else:
        valid_image_keys = set(image_keys)
        annotation_entries = {
            image_key: annotation_entries[image_key]
            for image_key in sorted(annotation_entries)
            if image_key in valid_image_keys
        }
        total_frames = len(image_keys)
        payload['sync_error'] = ''

    manual_complete = bool(payload.get('manual_complete'))
    manual_complete_by = str(payload.get('manual_complete_by') or '').strip()
    manual_complete_at_utc = str(payload.get('manual_complete_at_utc') or '').strip()

    if manual_complete_override is not None:
        manual_complete = bool(manual_complete_override)
        if manual_complete:
            manual_complete_by = (manual_actor or payload.get('annotator_username') or '').strip()
            manual_complete_at_utc = _utc_now_iso()
        else:
            manual_complete_by = ''
            manual_complete_at_utc = ''

    annotated_frames = len(annotation_entries)
    pending_frames = max(total_frames - annotated_frames, 0)
    progress_percent = _assignment_progress_percent(total_frames, annotated_frames)
    status = _assignment_progress_status(annotated_frames, manual_complete)

    payload.update(
        {
            'total_frames': total_frames,
            'annotated_frames': annotated_frames,
            'pending_frames': pending_frames,
            'progress_percent': progress_percent,
            'status': status,
            'manual_complete': manual_complete,
            'manual_complete_by': manual_complete_by,
            'manual_complete_at_utc': manual_complete_at_utc,
            'updated_at_utc': _utc_now_iso(),
            'annotation_entries': annotation_entries,
        }
    )

    _write_assignment_progress_json(
        s3_client=s3_client,
        bucket=bucket,
        key=payload['progress_json_key'],
        payload=payload,
    )
    return _decorate_assignment_progress_payload(payload)


def _attach_assignment_progress(assignments):
    enriched_assignments = list(assignments)
    for assignment in enriched_assignments:
        assignment.bucket_progress = _sync_assignment_progress(assignment)
    return enriched_assignments


def _annotation_color(label_name):
    palette = [
        '#e63946',
        '#1d3557',
        '#2a9d8f',
        '#f4a261',
        '#6a4c93',
        '#1982c4',
        '#ff595e',
    ]
    return palette[hash(label_name) % len(palette)]


def _render_labelme_json_preview(json_bytes):
    payload = json.loads(json_bytes.decode('utf-8'))
    width = int(payload.get('imageWidth') or 1280)
    height = int(payload.get('imageHeight') or 720)

    image_data = payload.get('imageData')
    if image_data:
        image = Image.open(io.BytesIO(base64.b64decode(image_data))).convert('RGB')
    else:
        image = Image.new('RGB', (width, height), color='white')

    draw = ImageDraw.Draw(image, 'RGBA')
    font = ImageFont.load_default()
    legend_labels = []
    for shape in payload.get('shapes', []):
        points = [tuple(point) for point in shape.get('points', [])]
        label = shape.get('label', 'label')
        color = _annotation_color(label)
        fill_color = color + '40'
        if not points:
            continue
        if shape.get('shape_type') == 'rectangle' and len(points) >= 2:
            draw.rectangle([points[0], points[1]], outline=color, fill=fill_color, width=5)
        elif shape.get('shape_type') in {'polygon', 'mask'} and len(points) >= 2:
            draw.polygon(points, outline=color, fill=fill_color, width=4)
        elif shape.get('shape_type') in {'line', 'linestrip', 'polyline'} and len(points) >= 2:
            draw.line(points, fill=color, width=5)
        else:
            x, y = points[0]
            draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=color)
        x, y = points[0]
        text = label or 'label'
        text_box = draw.textbbox((x + 8, y + 8), text, font=font)
        padded_box = (
            text_box[0] - 4,
            text_box[1] - 3,
            text_box[2] + 4,
            text_box[3] + 3,
        )
        draw.rounded_rectangle(padded_box, radius=4, fill=color)
        draw.text((x + 8, y + 8), text, fill='white', font=font)
        if text not in legend_labels:
            legend_labels.append(text)

    if legend_labels:
        legend_height = 26 + (len(legend_labels) * 22)
        draw.rounded_rectangle((12, 12, min(width - 12, 280), min(height - 12, legend_height)), radius=8, fill=(15, 23, 42, 190))
        legend_y = 22
        for label in legend_labels:
            color = _annotation_color(label)
            draw.rectangle((24, legend_y + 2, 38, legend_y + 16), fill=color)
            draw.text((46, legend_y), label, fill='white', font=font)
            legend_y += 22

    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=85)
    return buffer.getvalue()


def _review_json_prefix(project_name, annotator_name, review_date):
    config = _get_review_s3_config()
    return f"{config['root_prefix']}/{project_name}/date_{review_date.strftime('%d%m%Y')}/{annotator_name}/"


def _review_json_objects(project_name, annotator_name, review_date):
    client = _get_review_s3_client()
    if client is None:
        return []

    config = _get_review_s3_config()
    prefix = _review_json_prefix(project_name, annotator_name, review_date)
    paginator = client.get_paginator('list_objects_v2')
    results = []
    for page in paginator.paginate(Bucket=config['bucket'], Prefix=prefix):
        for item in page.get('Contents', []):
            key = item.get('Key', '')
            if not key.endswith('.json'):
                continue
            results.append(
                {
                    'key': key,
                    'file_name': os.path.basename(key),
                }
            )
    return results


def _review_json_preview_bytes(key):
    client = _get_review_s3_client()
    if client is None:
        return None
    config = _get_review_s3_config()
    try:
        body = client.get_object(Bucket=config['bucket'], Key=key)['Body'].read()
    except Exception:
        return None
    return _render_labelme_json_preview(body)


def _delete_review_json_object(key):
    client = _get_review_s3_client()
    if client is None:
        return False, 'S3 client is not configured.'
    config = _get_review_s3_config()
    try:
        client.delete_object(Bucket=config['bucket'], Key=key)
    except ClientError as exc:
        error = exc.response.get('Error', {})
        code = error.get('Code') or 'S3Error'
        message = error.get('Message') or str(exc)
        return False, f'{code}: {message}'
    except BotoCoreError as exc:
        return False, str(exc)
    return True, ''


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

    if request.method == 'GET' and request.GET.get('action') == 'preview_review_image':
        review_key = request.GET.get('review_key') or ''
        if not review_key:
            return HttpResponse(status=400)
        preview_bytes = _review_json_preview_bytes(review_key)
        if preview_bytes is None:
            return HttpResponse(status=404)
        return HttpResponse(preview_bytes, content_type='image/jpeg')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create_project':
            name = (request.POST.get('project_name') or '').strip()
            description = (request.POST.get('project_description') or '').strip()
            if not name:
                messages.error(request, 'Project name is required.')
                return redirect('admin_dash')

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
                return redirect('admin_dash')

            messages.success(request, f'Project "{name}" created successfully.')
            return redirect('admin_dash')

        if action == 'create_label':
            project_id = request.POST.get('project_id')
            label_name = (request.POST.get('label_name') or '').strip()
            color = (request.POST.get('label_color') or '#FF5733').strip() or '#FF5733'
            if not project_id or not label_name:
                messages.error(request, 'Project and label name are required.')
                return redirect('admin_dash')

            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                messages.error(request, 'Project not found.')
                return redirect('admin_dash')

            try:
                Label.objects.create(project=project, name=label_name, color=color)
            except IntegrityError:
                messages.error(request, f'Label "{label_name}" already exists in project "{project.name}".')
                return redirect('admin_dash')

            messages.success(request, f'Label "{label_name}" added to project "{project.name}".')
            return redirect('admin_dash')

        if action == 'delete_bucket_assignment':
            assignment_id = request.POST.get('assignment_id')
            try:
                assignment = AnnotatorBucketAssignment.objects.select_related('annotator__django_user').get(id=assignment_id)
            except AnnotatorBucketAssignment.DoesNotExist:
                messages.error(request, 'Bucket assignment not found.')
                return redirect('admin_dash')

            annotator_name = assignment.annotator.django_user.username
            assignment.delete()
            messages.success(request, f'Removed bucket assignment for {annotator_name}.')
            return redirect('admin_dash')

        if action == 'add_bucket_assignment':
            annotator_id = request.POST.get('annotator_id')
            assigned_s3_path = (request.POST.get('assigned_s3_path') or '').strip()
            project_id = request.POST.get('assigned_project_id')
            display_name = (request.POST.get('display_name') or '').strip()

            if not annotator_id or not assigned_s3_path:
                messages.error(request, 'Select an annotator and provide a bucket path.')
                return redirect('admin_dash')

            try:
                annotator = CustomUser.objects.select_related('django_user').get(
                    id=annotator_id,
                    role=CustomUser.ROLE_ANNOTATOR,
                )
            except CustomUser.DoesNotExist:
                messages.error(request, 'Annotator not found.')
                return redirect('admin_dash')

            assigned_project = None
            if project_id:
                try:
                    assigned_project = Project.objects.get(id=project_id)
                except Project.DoesNotExist:
                    messages.error(request, 'Assigned project not found.')
                    return redirect('admin_dash')

            assignment = AnnotatorBucketAssignment.objects.create(
                annotator=annotator,
                project=assigned_project,
                s3_path=assigned_s3_path,
                display_name=display_name or assigned_s3_path,
            )

            if not annotator.assigned_project and assigned_project:
                annotator.assigned_project = assigned_project
                annotator.assigned_s3_path = assigned_s3_path
                annotator.save(update_fields=['assigned_project', 'assigned_s3_path', 'updated_date'])

            messages.success(
                request,
                f'Added bucket "{assignment.display_name}" for {annotator.django_user.username}.',
            )
            return redirect('admin_dash')

        if action == 'delete_review_json':
            review_key = request.POST.get('review_key') or ''
            if not review_key:
                messages.error(request, 'Review JSON key is required.')
                return redirect('admin_dash')
            deleted, delete_message = _delete_review_json_object(review_key)
            if deleted:
                messages.success(request, f'Deleted {os.path.basename(review_key)} from S3.')
            else:
                messages.error(request, f'Could not delete JSON from S3. {delete_message}')
            return redirect(
                f"{request.path}?project_id={request.POST.get('project_id','')}&annotator_id={request.POST.get('annotator_id','')}&review_date={request.POST.get('review_date','')}&page={request.POST.get('page','1')}"
            )

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
    authority_cards = [
        {
            'title': 'User Authority',
            'count': CustomUser.objects.count(),
            'subtitle': 'User profiles under control',
            'description': 'Admin can verify accounts, change roles, and control who becomes assigner, annotator, or reviewer.',
        },
        {
            'title': 'Assigner Authority',
            'count': AnnotatorBucketAssignment.objects.count(),
            'subtitle': 'Bucket assignments tracked',
            'description': 'Admin oversees project creation, label structures, and the path assignments managed by assigners.',
        },
        {
            'title': 'Reviewer Authority',
            'count': Project.objects.count(),
            'subtitle': 'Projects available for review',
            'description': 'Admin controls reviewer access and supervises review coverage across project, annotator, and date-based outputs.',
        },
        {
            'title': 'Annotation Output',
            'count': Label.objects.count(),
            'subtitle': 'Labels configured',
            'description': 'Admin retains top-level authority over label taxonomy and downstream annotation quality operations.',
        },
    ]
    users = CustomUser.objects.select_related('django_user').order_by('django_user__username')
    annotators = list(CustomUser.objects.filter(role=CustomUser.ROLE_ANNOTATOR).select_related(
        'django_user',
        'assigned_project',
    ).prefetch_related('assigned_project__labels', 'bucket_assignments__project__labels'))
    for annotator in annotators:
        annotator.bucket_assignment_list = _attach_assignment_progress(
            annotator.bucket_assignments.all()
        )
    projects = Project.objects.select_related('organization').prefetch_related('labels').order_by('name')

    selected_project_id = request.GET.get('project_id') or ''
    selected_annotator_id = request.GET.get('annotator_id') or ''
    selected_date = request.GET.get('review_date') or ''
    selected_page = request.GET.get('page') or '1'
    review_items = []
    review_page_obj = None

    if selected_project_id and selected_annotator_id and selected_date:
        try:
            project = Project.objects.get(id=selected_project_id)
            annotator = CustomUser.objects.select_related('django_user').get(
                id=selected_annotator_id,
                role=CustomUser.ROLE_ANNOTATOR,
            )
            review_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            review_items = _review_json_objects(
                project_name=project.name,
                annotator_name=annotator.django_user.username,
                review_date=review_date_obj,
            )
            paginator = Paginator(review_items, 10)
            review_page_obj = paginator.get_page(selected_page)
            for item in review_page_obj.object_list:
                item['preview_url'] = (
                    f"{request.path}?action=preview_review_image"
                    f"&review_key={quote(item['key'], safe='')}"
                    f"&project_id={selected_project_id}"
                    f"&annotator_id={selected_annotator_id}"
                    f"&review_date={selected_date}"
                    f"&page={review_page_obj.number}"
                )
            if not review_items:
                messages.info(request, 'No review JSON files found for the selected project, annotator, and date.')
        except (Project.DoesNotExist, CustomUser.DoesNotExist, ValueError):
            messages.error(request, 'Invalid reviewer filter values.')

    return render(
        request,
        'accounts/admin_dashboard.html',
        {
            'custom_user': custom_user,
            'user_type': custom_user.user_type,
            'authority_cards': authority_cards,
            'users': users,
            'annotators': annotators,
            'projects': projects,
            'role_choices': CustomUser.ROLE_CHOICES,
            'role_counts': {
                'admin': role_count_map.get(CustomUser.ROLE_ADMIN, 0),
                'assigner': role_count_map.get(CustomUser.ROLE_ASSIGNER, 0),
                'annotator': role_count_map.get(CustomUser.ROLE_ANNOTATOR, 0),
                'reviewer': role_count_map.get(CustomUser.ROLE_REVIEWER, 0),
            },
            'review_projects': projects,
            'review_annotators': annotators,
            'selected_project_id': selected_project_id,
            'selected_annotator_id': selected_annotator_id,
            'selected_review_date': selected_date,
            'review_items': review_page_obj.object_list if review_page_obj else [],
            'review_page_obj': review_page_obj,
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

        if action == 'delete_bucket_assignment':
            assignment_id = request.POST.get('assignment_id')
            try:
                assignment = AnnotatorBucketAssignment.objects.select_related('annotator__django_user').get(id=assignment_id)
            except AnnotatorBucketAssignment.DoesNotExist:
                messages.error(request, 'Bucket assignment not found.')
                return redirect('assigner_dash')

            annotator_name = assignment.annotator.django_user.username
            assignment.delete()
            messages.success(request, f'Removed bucket assignment for {annotator_name}.')
            return redirect('assigner_dash')

        annotator_id = request.POST.get('annotator_id')
        assigned_s3_path = (request.POST.get('assigned_s3_path') or '').strip()
        project_id = request.POST.get('assigned_project_id')
        display_name = (request.POST.get('display_name') or '').strip()

        if not annotator_id or not assigned_s3_path:
            messages.error(request, 'Select an annotator and provide a bucket path.')
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
                assigned_project = Project.objects.get(id=project_id, owner=custom_user)
            except Project.DoesNotExist:
                messages.error(request, 'Assigned project not found.')
                return redirect('assigner_dash')

        assignment = AnnotatorBucketAssignment.objects.create(
            annotator=annotator,
            project=assigned_project,
            s3_path=assigned_s3_path,
            display_name=display_name or assigned_s3_path,
        )

        if not annotator.assigned_project and assigned_project:
            annotator.assigned_project = assigned_project
            annotator.assigned_s3_path = assigned_s3_path
            annotator.save(update_fields=['assigned_project', 'assigned_s3_path', 'updated_date'])

        messages.success(
            request,
            f'Added bucket "{assignment.display_name}" for {annotator.django_user.username}.',
        )
        return redirect('assigner_dash')

    annotators = list(CustomUser.objects.filter(role=CustomUser.ROLE_ANNOTATOR).select_related(
        'django_user',
        'assigned_project',
    ).prefetch_related('assigned_project__labels', 'bucket_assignments__project__labels'))
    for annotator in annotators:
        annotator.bucket_assignment_list = _attach_assignment_progress(
            annotator.bucket_assignments.all()
        )
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

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'set_bucket_completion':
            assignment_id = request.POST.get('assignment_id')
            mark_complete = request.POST.get('manual_complete') == '1'
            try:
                assignment = AnnotatorBucketAssignment.objects.select_related(
                    'annotator__django_user',
                    'project',
                ).get(id=assignment_id, annotator=custom_user)
            except AnnotatorBucketAssignment.DoesNotExist:
                messages.error(request, 'Bucket assignment not found.')
                return redirect('anotater_dash')

            bucket_progress = _sync_assignment_progress(
                assignment,
                manual_complete_override=mark_complete,
                manual_actor=custom_user.django_user.username,
            )
            if bucket_progress.get('status') == ASSIGNMENT_STATUS_UNAVAILABLE:
                messages.error(request, 'Bucket progress JSON could not be updated.')
            elif mark_complete:
                messages.success(request, f'Bucket "{assignment.display_name}" marked complete.')
            else:
                messages.success(request, f'Bucket "{assignment.display_name}" moved back to in progress.')
            return redirect('anotater_dash')

    annotator_assignments = _attach_assignment_progress(
        custom_user.bucket_assignments.select_related('project').prefetch_related('project__labels')
    )
    return render(
        request,
        'accounts/worker_dashboard.html',
        {
            'custom_user': custom_user,
            'user_type': custom_user.user_type,
            'dashboard_title': 'Annotator Dashboard',
            'annotator_assignments': annotator_assignments,
        },
    )


@login_required(login_url='login')
def reviewer_dashboard_view(request):
    custom_user = _get_custom_profile_or_none(request)
    if not custom_user or custom_user.role != CustomUser.ROLE_REVIEWER:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')

    if request.method == 'GET' and request.GET.get('action') == 'preview_review_image':
        review_key = request.GET.get('review_key') or ''
        if not review_key:
            return HttpResponse(status=400)
        preview_bytes = _review_json_preview_bytes(review_key)
        if preview_bytes is None:
            return HttpResponse(status=404)
        return HttpResponse(preview_bytes, content_type='image/jpeg')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete_review_json':
            review_key = request.POST.get('review_key') or ''
            if not review_key:
                messages.error(request, 'Review JSON key is required.')
                return redirect('reviewer_dash')
            deleted, delete_message = _delete_review_json_object(review_key)
            if deleted:
                messages.success(request, f'Deleted {os.path.basename(review_key)} from S3.')
            else:
                messages.error(request, f'Could not delete JSON from S3. {delete_message}')
            return redirect(
                f"{request.path}?project_id={request.POST.get('project_id','')}&annotator_id={request.POST.get('annotator_id','')}&review_date={request.POST.get('review_date','')}&page={request.POST.get('page','1')}"
            )

    projects = Project.objects.order_by('name')
    annotators = CustomUser.objects.filter(role=CustomUser.ROLE_ANNOTATOR).select_related('django_user').order_by('django_user__username')
    review_assignment_rows = _attach_assignment_progress(
        AnnotatorBucketAssignment.objects.select_related(
            'annotator__django_user',
            'project',
        ).prefetch_related('project__labels')
    )

    selected_project_id = request.GET.get('project_id') or ''
    selected_annotator_id = request.GET.get('annotator_id') or ''
    selected_date = request.GET.get('review_date') or ''
    selected_page = request.GET.get('page') or '1'
    review_items = []
    page_obj = None

    if selected_project_id and selected_annotator_id and selected_date:
        try:
            project = Project.objects.get(id=selected_project_id)
            annotator = CustomUser.objects.select_related('django_user').get(
                id=selected_annotator_id,
                role=CustomUser.ROLE_ANNOTATOR,
            )
            review_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            review_items = _review_json_objects(
                project_name=project.name,
                annotator_name=annotator.django_user.username,
                review_date=review_date_obj,
            )
            paginator = Paginator(review_items, 10)
            page_obj = paginator.get_page(selected_page)
            for item in page_obj.object_list:
                item['preview_url'] = (
                    f"{request.path}?action=preview_review_image"
                    f"&review_key={quote(item['key'], safe='')}"
                    f"&project_id={selected_project_id}"
                    f"&annotator_id={selected_annotator_id}"
                    f"&review_date={selected_date}"
                    f"&page={page_obj.number}"
                )
            if not review_items:
                messages.info(request, 'No review JSON files found for the selected project, annotator, and date.')
        except (Project.DoesNotExist, CustomUser.DoesNotExist, ValueError):
            messages.error(request, 'Invalid reviewer filter values.')

    return render(
        request,
        'accounts/worker_dashboard.html',
        {
            'custom_user': custom_user,
            'user_type': custom_user.user_type,
            'dashboard_title': 'Reviewer Dashboard',
            'review_projects': projects,
            'review_annotators': annotators,
            'selected_project_id': selected_project_id,
            'selected_annotator_id': selected_annotator_id,
            'selected_review_date': selected_date,
            'review_items': page_obj.object_list if page_obj else [],
            'review_page_obj': page_obj,
            'review_assignment_rows': review_assignment_rows,
        },
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
