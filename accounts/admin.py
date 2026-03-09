from django.contrib import admin

from .models import (
    AnnotatorBucketAssignment,
    CustomUser,
    Label,
    Organization,
    Project,
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


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'color']
    list_filter = ['project']
    search_fields = ['name']


@admin.register(AnnotatorBucketAssignment)
class AnnotatorBucketAssignmentAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'annotator', 'project', 's3_path', 'created_date']
    list_filter = ['project', 'created_date']
    search_fields = ['display_name', 's3_path', 'annotator__django_user__username']
