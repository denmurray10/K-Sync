from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0044_emailpromotionsignup_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogarticle',
            name='facebook_homepage_comment_id',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='blogarticle',
            name='facebook_homepage_commented_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
