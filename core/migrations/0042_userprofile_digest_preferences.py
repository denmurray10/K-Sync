from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_radiotrackplay'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='digest_channel_email',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='digest_channel_push',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='digest_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='digest_hour',
            field=models.PositiveSmallIntegerField(default=8),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='digest_include_birthdays',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='digest_include_chart_jumps',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='digest_include_comebacks',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='digest_last_sent_on',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='digest_timezone',
            field=models.CharField(default='Europe/London', max_length=64),
        ),
    ]
