from django.db import models
from django.conf import settings
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
        'p', 'h2', 'h3', 'strong', 'em', 'blockquote',
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
    image_3 = models.URLField(max_length=500, blank=True)
    body_html = models.TextField()
    reading_time = models.IntegerField(default=3)
    facebook_post_id = models.CharField(max_length=100, blank=True)
    facebook_posted_at = models.DateTimeField(null=True, blank=True)
    x_post_id = models.CharField(max_length=100, blank=True)
    x_posted_at = models.DateTimeField(null=True, blank=True)
    pinterest_post_id = models.CharField(max_length=100, blank=True)
    pinterest_posted_at = models.DateTimeField(null=True, blank=True)
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


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    bias = models.ForeignKey(
        KPopGroup,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='biased_by',
    )

    def __str__(self):
        return f"{self.user.username}'s profile"


class FavouriteSong(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favourite_songs',
    )
    title = models.CharField(max_length=300)
    artist = models.CharField(max_length=200)
    artwork_url = models.URLField(max_length=500, blank=True)
    preview_url = models.URLField(max_length=500, blank=True)
    itunes_url = models.URLField(max_length=500, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-added_at']
        unique_together = ['user', 'title', 'artist']

    def __str__(self):
        return f"{self.user.username} ♥ {self.title}"


class SongRequest(models.Model):
    song_title = models.CharField(max_length=300)
    artist = models.CharField(max_length=200)
    listener_name = models.CharField(max_length=100, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.artist} – {self.song_title}"


class GameScore(models.Model):
    GAME_CHOICES = [
        ('song_game', 'Song Game'),
        ('idol_scramble', 'Idol Scramble'),
        ('lyric_drop', 'Lyric Drop'),
        ('chart_clash', 'Chart Clash'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='game_scores',
    )
    game = models.CharField(max_length=50, choices=GAME_CHOICES, default='song_game')
    score = models.IntegerField()
    correct = models.IntegerField(default=0)
    total = models.IntegerField(default=0)
    best_streak = models.IntegerField(default=0)
    played_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-played_at']

    def __str__(self):
        return f"{self.user.username} — {self.get_game_display()} {self.score}pts"


class Contest(models.Model):
    slug = models.SlugField(unique=True, max_length=200)
    title = models.CharField(max_length=300)
    subtitle = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    image = models.URLField(max_length=500, blank=True)
    artist = models.CharField(max_length=200, blank=True)
    prizes = models.JSONField(
        default=list,
        blank=True,
        help_text='List of {"icon": "...", "title": "...", "subtitle": "..."} objects',
    )
    rules = models.TextField(
        blank=True,
        help_text='One rule per line',
    )
    entry_question = models.CharField(max_length=500, blank=True)
    deadline = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    contest_number = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_featured', 'deadline']

    @property
    def entry_count(self):
        return self.entries.count()

    def __str__(self):
        return self.title


class ContestEntry(models.Model):
    contest = models.ForeignKey(Contest, related_name='entries', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    email = models.EmailField()
    country = models.CharField(max_length=100, blank=True)
    username = models.CharField(max_length=100, blank=True)
    answer = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.name} → {self.contest.title}"


class FanClubMembership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='fan_club_memberships',
    )
    group = models.ForeignKey(
        KPopGroup,
        on_delete=models.CASCADE,
        related_name='fan_club_members',
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    is_genesis = models.BooleanField(default=False)

    class Meta:
        unique_together = ['user', 'group']
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user.username} ∈ {self.group.name}"

class UserNotification(models.Model):
    NOTIFICATION_TYPES = (
        ('INVITE', 'Club Invitation'),
        ('ALERT', 'System Alert'),
        ('SOCIAL', 'Social Interaction'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    message = models.TextField()
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='ALERT')
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:30]}..."

class ClubInvitation(models.Model):
    INVITATION_STATUS = (
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('DECLINED', 'Declined'),
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_invitations'
    )
    invitee_email = models.EmailField(null=True, blank=True)
    invitee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='club_invitations'
    )
    club_name = models.CharField(max_length=255)
    archetype = models.CharField(max_length=50, default='vanguard')
    status = models.CharField(max_length=20, choices=INVITATION_STATUS, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        target = self.invitee.username if self.invitee else self.invitee_email
        return f"Invite to {target} for {self.club_name}"

class ClubLaunch(models.Model):
    name = models.CharField(max_length=255)
    artist = models.CharField(max_length=255)
    mission_statement = models.TextField()
    archetype = models.CharField(max_length=50, default='vanguard')
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='club_launches'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Launch: {self.name} ({self.artist})"

class UserBadge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='badges'
    )
    name = models.CharField(max_length=255)
    badge_type = models.CharField(max_length=50, default='GENESIS')
    group = models.ForeignKey(
        KPopGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    is_glowing = models.BooleanField(default=True)
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-awarded_at']

    def __str__(self):
        return f"{self.name} awarded to {self.user.username}"


class PreLaunchSignup(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    age = models.PositiveIntegerField()
    signed_up_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-signed_up_at']

    def __str__(self):
        return f"{self.name} ({self.email})"

class RadioTrack(models.Model):
    title = models.CharField(max_length=300)
    artist = models.CharField(max_length=200)
    album_art = models.URLField(max_length=500, blank=True)
    duration = models.CharField(max_length=20, help_text="e.g. 3:45", default="3:00")
    duration_seconds = models.IntegerField(default=180, help_text="Duration in seconds")
    audio_url = models.URLField(max_length=500, blank=True, null=True)
    is_request = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.artist} - {self.title}"

class RadioStationState(models.Model):
    current_track = models.ForeignKey(RadioTrack, null=True, blank=True, on_delete=models.SET_NULL, related_name='current_as_state')
    up_next = models.JSONField(default=list, help_text="List of RadioTrack IDs in queue order")
    recently_played = models.JSONField(default=list, help_text="List of RadioTrack IDs in history order")
    listeners_count = models.IntegerField(default=3847)
    started_at = models.DateTimeField(null=True, blank=True, help_text="Time when the current track started playing")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Radio State (Last updated: {self.updated_at})"

    class Meta:
        verbose_name_plural = "Radio Station State"

class RadioPlaylist(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    tracks = models.ManyToManyField(RadioTrack, through='RadioPlaylistTrack', related_name='playlists')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class RadioPlaylistTrack(models.Model):
    playlist = models.ForeignKey(RadioPlaylist, on_delete=models.CASCADE)
    track = models.ForeignKey(RadioTrack, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.playlist.name} - {self.track.title} (#{self.order})"

class RadioSchedule(models.Model):
    DAY_CHOICES = (
        ('MON', 'Monday'),
        ('TUE', 'Tuesday'),
        ('WED', 'Wednesday'),
        ('THU', 'Thursday'),
        ('FRI', 'Friday'),
        ('SAT', 'Saturday'),
        ('SUN', 'Sunday'),
    )
    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    playlist = models.ForeignKey(RadioPlaylist, on_delete=models.CASCADE, related_name='schedules')
    host = models.CharField(max_length=255, default='Auto DJ')
    genre = models.CharField(max_length=50, default='MUSIC')
    description = models.TextField(blank=True)
    show_color = models.CharField(max_length=20, default='CYAN')

    class Meta:
        ordering = ['day', 'start_time']
        verbose_name_plural = "Radio Schedules"

    def __str__(self):
        return f"{self.get_day_display()} {self.start_time}-{self.end_time}: {self.playlist.name}"


class RadioScheduleTemplate(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class RadioScheduleTemplateSlot(models.Model):
    template = models.ForeignKey(RadioScheduleTemplate, on_delete=models.CASCADE, related_name='slots')
    start_time = models.TimeField()
    end_time = models.TimeField()
    show_name = models.CharField(max_length=255, blank=True)
    show_color = models.CharField(max_length=20, default='CYAN')
    playlist = models.ForeignKey(RadioPlaylist, on_delete=models.CASCADE)
    host = models.CharField(max_length=255, default='Auto DJ')
    genre = models.CharField(max_length=50, default='MUSIC')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'start_time']

    def __str__(self):
        return f"{self.template.name} {self.start_time}-{self.end_time}: {self.playlist.name}"
