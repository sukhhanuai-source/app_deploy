from django.contrib import admin

from .models import (
    Annotation,
    Attribute,
    CustomUser,
    ImageFrame,
    Job,
    Label,
    Organization,
    Project,
    Task,
)


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ['get_username', 'role', 'assigned_project', 'get_email', 'is_verified', 'created_date']
    list_filter = ['role', 'is_verified', 'assigned_project', 'created_date']
    search_fields = ['django_user__username', 'django_user__email', 'phone_number']
    readonly_fields = ['created_date', 'updated_date']
    fieldsets = (
        ('User Info', {'fields': ('django_user', 'phone_number')}),
        ('Account Details', {'fields': ('role', 'assigned_s3_path', 'assigned_project', 'is_verified')}),
        ('Timestamps', {'fields': ('created_date', 'updated_date'), 'classes': ('collapse',)}),
    )

    def get_username(self, obj):
        return obj.django_user.username

    get_username.short_description = 'Username'

    def get_email(self, obj):
        return obj.django_user.email

    get_email.short_description = 'Email'


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'created_date']
    search_fields = ['name', 'owner__django_user__username']
    filter_horizontal = ['members']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'owner', 'created_date']
    list_filter = ['organization', 'created_date']
    search_fields = ['name', 'organization__name']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'owner', 'status', 'created_date']
    list_filter = ['status', 'project']
    search_fields = ['name', 'project__name']


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ['id', 'task', 'assignee', 'start_frame', 'stop_frame', 'created_date']
    list_filter = ['task']


@admin.register(ImageFrame)
class ImageFrameAdmin(admin.ModelAdmin):
    list_display = ['id', 'task', 'frame', 'path', 'width', 'height']
    list_filter = ['task']
    search_fields = ['path']


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'color']
    list_filter = ['project']
    search_fields = ['name']


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ['name', 'label', 'type']
    list_filter = ['type', 'label']
    search_fields = ['name']


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display = ['id', 'job', 'label', 'type', 'frame']
    list_filter = ['type', 'label']
