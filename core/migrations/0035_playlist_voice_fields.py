from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_playlisttrack_voiceover_length_percent'),
    ]

    operations = [
        migrations.AddField(
            model_name='radioplaylist',
            name='default_voice_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='radioplaylist',
            name='default_voice_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='radioplaylisttrack',
            name='voice_over_voice_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='radioplaylisttrack',
            name='voice_over_voice_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
