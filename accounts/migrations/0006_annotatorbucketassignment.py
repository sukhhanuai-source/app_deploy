from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_customuser_assigned_project'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnnotatorBucketAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('s3_path', models.CharField(max_length=1024)),
                ('display_name', models.CharField(blank=True, default='', max_length=255)),
                ('created_date', models.DateTimeField(auto_now_add=True)),
                ('updated_date', models.DateTimeField(auto_now=True)),
                ('annotator', models.ForeignKey(on_delete=models.CASCADE, related_name='bucket_assignments', to='accounts.customuser')),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='bucket_assignments', to='accounts.project')),
            ],
            options={
                'ordering': ['project__name', 's3_path'],
            },
        ),
    ]
