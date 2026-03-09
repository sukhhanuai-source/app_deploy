from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_annotation_attribute_imageframe_job_label_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='assigned_s3_path',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Assigned S3 bucket/prefix for this user, e.g. s3://bucket/path or bucket/path.',
                max_length=1024,
            ),
        ),
    ]
