from django.contrib.auth.models import User as DjangoUser
from django.db import models


class CustomUser(models.Model):
    ROLE_ADMIN = 'admin'
    ROLE_ANNOTATOR = 'annotator'
    ROLE_REVIEWER = 'reviewer'
    ROLE_ASSIGNER = 'assigner'

    ROLE_CHOICES = (
        (ROLE_ADMIN, 'Admin'),
        (ROLE_ANNOTATOR, 'Annotator'),
        (ROLE_REVIEWER, 'Reviewer'),
        (ROLE_ASSIGNER, 'Assigner'),
    )

    django_user = models.OneToOneField(
        DjangoUser,
        on_delete=models.CASCADE,
        related_name='custom_profile',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ANNOTATOR)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    assigned_s3_path = models.CharField(
        max_length=1024,
        blank=True,
        default='',
        help_text='Assigned S3 bucket/prefix for this user, e.g. s3://bucket/path or bucket/path.',
    )
    assigned_project = models.ForeignKey(
        'Project',
        on_delete=models.SET_NULL,
        related_name='assigned_annotators',
        null=True,
        blank=True,
    )
    is_verified = models.BooleanField(default=False, help_text='Admin verification status')
    created_date = models.DateTimeField(auto_now_add=True, null=True)
    updated_date = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f"{self.django_user.username} ({self.role})"

    @property
    def user_type(self):
        """Backward-compatible alias used by existing views/templates."""
        return self.role

    class Meta:
        ordering = ['-created_date']


class Organization(models.Model):
    name = models.CharField(max_length=255, unique=True)
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='owned_organizations',
    )
    members = models.ManyToManyField(CustomUser, related_name='organizations', blank=True)
    created_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Project(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='owned_projects',
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='projects',
    )
    created_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_date']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'name'],
                name='uniq_project_name_per_organization',
            )
        ]


class Label(models.Model):
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='labels')
    color = models.CharField(max_length=20, default='#FF5733')

    def __str__(self):
        return f"{self.project.name}: {self.name}"

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['project', 'name'], name='uniq_label_name_per_project')
        ]


class AnnotatorBucketAssignment(models.Model):
    annotator = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='bucket_assignments',
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        related_name='bucket_assignments',
        null=True,
        blank=True,
    )
    s3_path = models.CharField(max_length=1024)
    display_name = models.CharField(max_length=255, blank=True, default='')
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name or self.s3_path

    class Meta:
        ordering = ['project__name', 's3_path']
