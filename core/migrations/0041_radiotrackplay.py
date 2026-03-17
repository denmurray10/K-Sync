from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_userprofile_station_preferences'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RadioTrackPlay',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('listened_at', models.DateTimeField(auto_now_add=True)),
                ('track', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='play_events', to='core.radiotrack')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='radio_track_plays', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-listened_at'],
            },
        ),
        migrations.AddIndex(
            model_name='radiotrackplay',
            index=models.Index(fields=['user', '-listened_at'], name='core_radiot_user_id_63c6b3_idx'),
        ),
        migrations.AddIndex(
            model_name='radiotrackplay',
            index=models.Index(fields=['track', '-listened_at'], name='core_radiot_track_i_8a13c0_idx'),
        ),
    ]
