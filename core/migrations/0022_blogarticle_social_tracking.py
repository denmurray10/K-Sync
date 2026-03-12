from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_prelaunchsignup'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogarticle',
            name='facebook_post_id',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='blogarticle',
            name='facebook_posted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='blogarticle',
            name='pinterest_post_id',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='blogarticle',
            name='pinterest_posted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='blogarticle',
            name='x_post_id',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='blogarticle',
            name='x_posted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
