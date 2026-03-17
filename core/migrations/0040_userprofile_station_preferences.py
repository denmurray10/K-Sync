from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_radiotrack_live_ai_payload'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='favorite_eras',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='onboarding_completed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='favorite_groups',
            field=models.ManyToManyField(blank=True, related_name='station_fans', to='core.kpopgroup'),
        ),
    ]
