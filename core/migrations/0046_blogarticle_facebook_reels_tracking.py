from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_blogarticle_facebook_homepage_comment_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogarticle',
            name='facebook_reel_id',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='blogarticle',
            name='facebook_reel_posted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='blogarticle',
            name='facebook_reel_video_path',
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
