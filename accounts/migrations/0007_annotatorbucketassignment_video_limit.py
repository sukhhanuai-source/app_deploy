from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_annotatorbucketassignment'),
    ]

    operations = [
        migrations.AddField(
            model_name='annotatorbucketassignment',
            name='video_limit',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Optional number of video files to expose in LabelMe for this assignment.',
                null=True,
            ),
        ),
    ]
