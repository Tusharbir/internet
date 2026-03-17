from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0002_item_location_item_negotiable_item_status_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='report',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='report',
            name='reviewed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reviewed_reports',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='report',
            name='status',
            field=models.CharField(
                choices=[
                    ('open', 'Open'),
                    ('in_review', 'In Review'),
                    ('resolved', 'Resolved'),
                    ('dismissed', 'Dismissed'),
                ],
                default='open',
                max_length=20,
            ),
        ),
        migrations.AlterModelOptions(
            name='report',
            options={'ordering': ['-created_at']},
        ),
    ]
