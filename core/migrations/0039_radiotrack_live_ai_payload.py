from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_chatblockedterm'),
    ]

    operations = [
        migrations.AddField(
            model_name='radiotrack',
            name='live_ai_generated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='radiotrack',
            name='live_ai_payload',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
