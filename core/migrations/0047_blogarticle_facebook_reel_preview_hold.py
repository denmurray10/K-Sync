from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0046_blogarticle_facebook_reels_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogarticle',
            name='facebook_reel_preview_created_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='blogarticle',
            name='facebook_reel_preview_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'Queued'),
                    ('ready', 'Preview Ready'),
                    ('publishing', 'Publishing'),
                    ('published', 'Published'),
                    ('failed', 'Failed'),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='blogarticle',
            name='facebook_reel_preview_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False),
        ),
        migrations.AddField(
            model_name='blogarticle',
            name='facebook_reel_preview_video_path',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='blogarticle',
            name='facebook_reel_publish_scheduled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='blogarticle',
            name='facebook_reel_publish_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'Not Started'),
                    ('scheduled', 'Scheduled'),
                    ('publishing', 'Publishing'),
                    ('published', 'Published'),
                    ('failed', 'Failed'),
                ],
                max_length=20,
            ),
        ),
    ]
