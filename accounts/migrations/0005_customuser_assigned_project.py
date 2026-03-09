from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_customuser_assigned_s3_path'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='assigned_project',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name='assigned_annotators',
                to='accounts.project',
            ),
        ),
    ]
