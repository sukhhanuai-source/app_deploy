from django.contrib.auth.models import User as DjangoUser
from django.core.validators import MinValueValidator
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


class Task(models.Model):
    STATUS_CREATED = 'created'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'

    STATUS_CHOICES = (
        (STATUS_CREATED, 'Created'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
    )

    name = models.CharField(max_length=255)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    owner = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='owned_tasks')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CREATED)
    created_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_date']
        constraints = [
            models.UniqueConstraint(fields=['project', 'name'], name='uniq_task_name_per_project')
        ]


class Job(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='jobs')
    assignee = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name='assigned_jobs',
        null=True,
        blank=True,
    )
    start_frame = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    stop_frame = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    created_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Job {self.id} - {self.task.name}"

    class Meta:
        ordering = ['id']


class ImageFrame(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='images')
    frame = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    path = models.CharField(max_length=1024)
    width = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    height = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    def __str__(self):
        return f"{self.task.name} - frame {self.frame}"

    class Meta:
        ordering = ['task', 'frame']
        constraints = [
            models.UniqueConstraint(fields=['task', 'frame'], name='uniq_frame_per_task')
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


class Attribute(models.Model):
    TYPE_TEXT = 'text'
    TYPE_NUMBER = 'number'
    TYPE_BOOLEAN = 'boolean'
    TYPE_SELECT = 'select'

    TYPE_CHOICES = (
        (TYPE_TEXT, 'Text'),
        (TYPE_NUMBER, 'Number'),
        (TYPE_BOOLEAN, 'Boolean'),
        (TYPE_SELECT, 'Select'),
    )

    label = models.ForeignKey(Label, on_delete=models.CASCADE, related_name='attributes')
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_TEXT)

    def __str__(self):
        return f"{self.label.name}: {self.name}"

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['label', 'name'], name='uniq_attribute_name_per_label')
        ]


class Annotation(models.Model):
    TYPE_BBOX = 'bbox'
    TYPE_POLYGON = 'polygon'
    TYPE_POLYLINE = 'polyline'
    TYPE_MASK = 'mask'
    TYPE_CUBOID = 'cuboid'
    TYPE_SKELETON = 'skeleton'

    TYPE_CHOICES = (
        (TYPE_BBOX, 'Bounding Box'),
        (TYPE_POLYGON, 'Polygon'),
        (TYPE_POLYLINE, 'Polyline'),
        (TYPE_MASK, 'Mask'),
        (TYPE_CUBOID, 'Cuboid'),
        (TYPE_SKELETON, 'Skeleton'),
    )

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='annotations')
    label = models.ForeignKey(Label, on_delete=models.PROTECT, related_name='annotations')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    frame = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    coordinates = models.JSONField(help_text='Coordinates / geometry payload for the annotation.')

    def __str__(self):
        return f"Annotation {self.id} ({self.type})"

    class Meta:
        ordering = ['frame', 'id']
