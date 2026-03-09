from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_rollback_video_assignment_changes'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Annotation',
        ),
        migrations.DeleteModel(
            name='Attribute',
        ),
        migrations.DeleteModel(
            name='ImageFrame',
        ),
        migrations.DeleteModel(
            name='Job',
        ),
        migrations.DeleteModel(
            name='Task',
        ),
    ]
