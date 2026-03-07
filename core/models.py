from django.db import models
import bleach

class Ranking(models.Model):
    TIMEFRAME_CHOICES = (
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('soloists', 'Solo Artists'),
        ('groups', 'Idol Groups'),
    )
    timeframe = models.CharField(max_length=20, choices=TIMEFRAME_CHOICES, default='daily')
    date = models.DateField(auto_now_add=True)
    ranking_data = models.JSONField(help_text="Stores the Top 10 JSON array")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_timeframe_display()} Ranking for {self.date}"

    class Meta:
        ordering = ['-date', '-created_at']
        unique_together = ['date', 'timeframe']

class ComebackData(models.Model):
    year = models.IntegerField()
    month = models.IntegerField()
    data = models.JSONField(help_text="Stores the full JSON response from Kpopping API")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['year', 'month']
        verbose_name_plural = "Comeback Data"

    def __str__(self):
        return f"Calendar Data for {self.month}/{self.year}"

class KPopGroup(models.Model):
    GROUP_TYPE_CHOICES = (
        ('BOY', 'Boy Group'),
        ('GIRL', 'Girl Group'),
        ('SOLO', 'Soloist'),
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    label = models.CharField(max_length=100)
    group_type = models.CharField(max_length=10, choices=GROUP_TYPE_CHOICES)
    rank = models.IntegerField(null=True, blank=True)
    logo_path = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    image_url = models.URLField(max_length=500, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.group_type})"


class KPopMember(models.Model):
    group = models.ForeignKey(KPopGroup, related_name='members', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    stage_name = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=100, blank=True)
    image_url = models.URLField(max_length=500, null=True, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.group.name})"

class LivePoll(models.Model):
    question = models.CharField(max_length=255)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.question

class LivePollOption(models.Model):
    poll = models.ForeignKey(LivePoll, related_name='options', on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    votes = models.IntegerField(default=0)

    def percentage(self):
        total = sum(option.votes for option in self.poll.options.all())
        if total == 0:
            return 0
        return int((self.votes / total) * 100)

    def __str__(self):
        return f"{self.text} ({self.votes} votes)"


class BlogArticle(models.Model):
    ALLOWED_TAGS = [
        'p', 'h3', 'strong', 'em', 'blockquote',
        'a', 'ul', 'ol', 'li', 'br',
    ]
    ALLOWED_ATTRIBUTES = {
        'a': ['href', 'title', 'target', 'rel'],
    }

    slug = models.SlugField(max_length=200, unique=True)
    title = models.CharField(max_length=300)
    subtitle = models.CharField(max_length=500, blank=True)
    category = models.CharField(max_length=50)
    source_title = models.CharField(max_length=300)
    source_url = models.URLField(max_length=500, blank=True)
    source_name = models.CharField(max_length=100, blank=True)
    image = models.URLField(max_length=500, blank=True)
    image_2 = models.URLField(max_length=500, blank=True)
    body_html = models.TextField()
    reading_time = models.IntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        html = self.body_html or ''
        self.body_html = bleach.clean(
            html,
            tags=self.ALLOWED_TAGS,
            attributes=self.ALLOWED_ATTRIBUTES,
            strip=True,
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
