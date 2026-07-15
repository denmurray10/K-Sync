import uuid

from django.db import models
from django.conf import settings
from django.utils.text import slugify
import bleach

from .editorial import WRITER_CHOICES, get_writer_profile, parse_editorial_tags

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
    debut_date = models.DateField(null=True, blank=True)
    agency = models.CharField(max_length=150, blank=True)
    fandom_name = models.CharField(max_length=100, blank=True)
    fandom_color = models.CharField(max_length=50, blank=True)
    group_bio = models.TextField(blank=True)
    official_links = models.JSONField(default=list, blank=True)

    @property
    def resolved_bio(self):
        return (self.group_bio or self.description or '').strip()

    def __str__(self):
        return f"{self.name} ({self.group_type})"


class KPopMember(models.Model):
    group = models.ForeignKey(KPopGroup, related_name='members', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=140, blank=True)
    full_name = models.CharField(max_length=150, blank=True)
    korean_name = models.CharField(max_length=150, blank=True)
    stage_name = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=100, blank=True)
    positions = models.CharField(max_length=255, blank=True)
    image_url = models.URLField(max_length=500, null=True, blank=True)
    profile_image_url = models.URLField(max_length=500, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    birthplace = models.CharField(max_length=150, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    mbti = models.CharField(max_length=16, blank=True)
    blood_type = models.CharField(max_length=10, blank=True)
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    instagram_url = models.URLField(max_length=500, blank=True)
    official_links = models.JSONField(default=list, blank=True)
    profile_metadata = models.JSONField(default=dict, blank=True)
    fan_facts = models.TextField(blank=True)
    profile_bio = models.TextField(blank=True)
    seo_description_override = models.CharField(max_length=180, blank=True)
    is_active = models.BooleanField(default=True)
    debut_date = models.DateField(null=True, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        unique_together = [('group', 'slug')]

    @property
    def display_name(self):
        return (self.stage_name or self.name or self.full_name).strip()

    @property
    def resolved_full_name(self):
        return (self.full_name or self.name or self.stage_name).strip()

    @property
    def resolved_positions(self):
        return (self.positions or self.position).strip()

    @property
    def resolved_image_url(self):
        return (self.profile_image_url or self.image_url or '').strip()

    @property
    def resolved_bio(self):
        return (self.profile_bio or self.fan_facts or '').strip()

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.stage_name or self.name or self.full_name)[:120] or f"member-{uuid.uuid4().hex[:8]}"
            slug = base_slug
            suffix = 2
            while KPopMember.objects.exclude(pk=self.pk).filter(group=self.group, slug=slug).exists():
                slug = f"{base_slug[:110]}-{suffix}"
                suffix += 1
            self.slug = slug
        if not self.full_name:
            self.full_name = self.name or self.stage_name
        if not self.positions and self.position:
            self.positions = self.position
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.group.name})"


class MemberMilestone(models.Model):
    CATEGORY_CHOICES = (
        ('birthday', 'Birthday'),
        ('career', 'Career'),
        ('release', 'Release'),
        ('editorial', 'Editorial'),
    )

    member = models.ForeignKey(KPopMember, related_name='milestones', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    milestone_date = models.DateField(null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='career')
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', '-milestone_date', 'title']

    def __str__(self):
        return f"{self.member.display_name} - {self.title}"


class BirthdayFeature(models.Model):
    member = models.ForeignKey(KPopMember, related_name='birthday_features', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    embed_url = models.URLField(max_length=500, blank=True)
    cta_label = models.CharField(max_length=80, blank=True)
    cta_url = models.URLField(max_length=500, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'title']

    def __str__(self):
        return f"{self.member.display_name} - {self.title}"

class LivePoll(models.Model):
    TIER_CHOICES = (
        ('FREE', 'Free'),
        ('PLUS', 'Plus'),
        ('ULTRA', 'Ultra'),
    )

    question = models.CharField(max_length=255)
    is_active = models.BooleanField(default=False)
    early_access_starts_at = models.DateTimeField(null=True, blank=True)
    early_access_group = models.ForeignKey(
        'KPopGroup',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='early_access_polls',
    )
    early_access_min_tier = models.CharField(max_length=10, choices=TIER_CHOICES, default='PLUS')
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
    FACEBOOK_REEL_PREVIEW_STATUS_CHOICES = (
        ('', 'Queued'),
        ('ready', 'Preview Ready'),
        ('publishing', 'Publishing'),
        ('published', 'Published'),
        ('failed', 'Failed'),
    )
    FACEBOOK_REEL_PUBLISH_STATUS_CHOICES = (
        ('', 'Not Started'),
        ('scheduled', 'Scheduled'),
        ('publishing', 'Publishing'),
        ('published', 'Published'),
        ('failed', 'Failed'),
    )
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
    writer_slug = models.CharField(max_length=40, choices=WRITER_CHOICES, default='mia-kang')
    editorial_tags = models.CharField(
        max_length=200,
        blank=True,
        help_text='Comma-separated editorial tags, for example: Breaking News, Exclusive',
    )
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
    facebook_reel_id = models.CharField(max_length=100, blank=True)
    facebook_reel_posted_at = models.DateTimeField(null=True, blank=True)
    facebook_reel_video_path = models.CharField(max_length=500, blank=True)
    facebook_reel_preview_video_path = models.CharField(max_length=500, blank=True)
    facebook_reel_preview_created_at = models.DateTimeField(null=True, blank=True)
    facebook_reel_publish_scheduled_at = models.DateTimeField(null=True, blank=True)
    facebook_reel_preview_status = models.CharField(
        max_length=20,
        choices=FACEBOOK_REEL_PREVIEW_STATUS_CHOICES,
        blank=True,
    )
    facebook_reel_publish_status = models.CharField(
        max_length=20,
        choices=FACEBOOK_REEL_PUBLISH_STATUS_CHOICES,
        blank=True,
    )
    facebook_reel_preview_token = models.UUIDField(default=uuid.uuid4, editable=False)
    facebook_homepage_comment_id = models.CharField(max_length=100, blank=True)
    facebook_homepage_commented_at = models.DateTimeField(null=True, blank=True)
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

    @property
    def writer_profile(self):
        return get_writer_profile(self.writer_slug)

    @property
    def writer_name(self):
        return self.writer_profile.name

    @property
    def tags_list(self):
        return parse_editorial_tags(self.editorial_tags)


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
    favorite_groups = models.ManyToManyField(
        KPopGroup,
        blank=True,
        related_name='station_fans',
    )
    favorite_eras = models.JSONField(default=list, blank=True)
    onboarding_completed = models.BooleanField(default=False)
    digest_enabled = models.BooleanField(default=False)
    digest_channel_push = models.BooleanField(default=True)
    digest_channel_email = models.BooleanField(default=False)
    digest_timezone = models.CharField(max_length=64, default='Europe/London')
    digest_hour = models.PositiveSmallIntegerField(default=8)
    digest_include_comebacks = models.BooleanField(default=True)
    digest_include_birthdays = models.BooleanField(default=True)
    digest_include_chart_jumps = models.BooleanField(default=True)
    digest_last_sent_on = models.DateField(null=True, blank=True)

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


class RadioTrackPlay(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='radio_track_plays',
    )
    track = models.ForeignKey(
        'RadioTrack',
        on_delete=models.CASCADE,
        related_name='play_events',
    )
    listened_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-listened_at']
        indexes = [
            models.Index(fields=['user', '-listened_at']),
            models.Index(fields=['track', '-listened_at']),
        ]

    def __str__(self):
        return f"{self.user.username} listened to {self.track.title}"


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


class LiveChatMessage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='live_chat_messages',
    )
    message = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}: {self.message[:40]}"


class ChatBlockedTerm(models.Model):
    term = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['term']

    def __str__(self):
        return self.term


class GameScore(models.Model):
    GAME_CHOICES = [
        ('song_game', 'Song Game'),
        ('idol_scramble', 'Idol Scramble'),
        ('lyric_drop', 'Lyric Drop'),
        ('chart_clash', 'Chart Clash'),
        ('daily_drop', 'Daily Drop'),
        ('chart_oracle', 'Chart Oracle'),
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


class ChartPrediction(models.Model):
    """Chart Oracle: a user's call on tomorrow's chart, made against today's
    daily ranking and resolved when the next daily ranking lands."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chart_predictions',
    )
    prediction_date = models.DateField(help_text="Date of the daily ranking the prediction was made against")
    payload = models.JSONField(default=dict, blank=True, help_text="Matchups, the user's picks, and the #1 call")
    resolved = models.BooleanField(default=False)
    points = models.IntegerField(default=0)
    correct = models.IntegerField(default=0)
    total = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-prediction_date']
        unique_together = ['user', 'prediction_date']

    def __str__(self):
        state = 'resolved' if self.resolved else 'open'
        return f"{self.user.username} — Oracle {self.prediction_date} ({state})"


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
    TIER_CHOICES = (
        ('FREE', 'Free'),
        ('PLUS', 'Plus'),
        ('ULTRA', 'Ultra'),
    )

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
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default='FREE')

    class Meta:
        unique_together = ['user', 'group']
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user.username} ∈ {self.group.name}"

    @property
    def perks(self):
        perk_map = {
            'FREE': {
                'early_access_polls': False,
                'premium_themes': False,
                'exclusive_voice_dj_packs': False,
            },
            'PLUS': {
                'early_access_polls': True,
                'premium_themes': True,
                'exclusive_voice_dj_packs': False,
            },
            'ULTRA': {
                'early_access_polls': True,
                'premium_themes': True,
                'exclusive_voice_dj_packs': True,
            },
        }
        return perk_map.get(self.tier, perk_map['FREE'])

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


class LimitedTimeEvent(models.Model):
    EVENT_CHOICES = (
        ('CHART_BATTLE', 'Chart Battle'),
        ('ARTIST_SPOTLIGHT', 'Artist Spotlight Week'),
        ('BADGE_DROP', 'Badge Drop'),
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=200, unique=True)
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-starts_at']

    def __str__(self):
        return self.title


class EventBadgeDrop(models.Model):
    RARITY_CHOICES = (
        ('COMMON', 'Common'),
        ('RARE', 'Rare'),
        ('EPIC', 'Epic'),
        ('LEGENDARY', 'Legendary'),
    )
    TIER_CHOICES = (
        ('FREE', 'Free'),
        ('PLUS', 'Plus'),
        ('ULTRA', 'Ultra'),
    )

    event = models.ForeignKey(
        LimitedTimeEvent,
        on_delete=models.CASCADE,
        related_name='badge_drops',
    )
    badge_name = models.CharField(max_length=255)
    badge_type = models.CharField(max_length=50, default='EVENT')
    rarity = models.CharField(max_length=20, choices=RARITY_CHOICES, default='COMMON')
    minimum_tier = models.CharField(max_length=10, choices=TIER_CHOICES, default='FREE')
    min_votes_required = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.badge_name} ({self.event.title})"


class EventParticipation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='event_participations',
    )
    event = models.ForeignKey(
        LimitedTimeEvent,
        on_delete=models.CASCADE,
        related_name='participations',
    )
    votes_cast = models.PositiveIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'event']
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user.username} in {self.event.title}"


class PreLaunchSignup(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    age = models.PositiveIntegerField()
    signed_up_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-signed_up_at']

    def __str__(self):
        return f"{self.name} ({self.email})"


class EmailPromotionSignup(models.Model):
    email = models.EmailField(unique=True)
    source = models.CharField(max_length=100, default='homepage_newsletter')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email

class RadioTrack(models.Model):
    title = models.CharField(max_length=300)
    artist = models.CharField(max_length=200)
    album_art = models.URLField(max_length=500, blank=True)
    duration = models.CharField(max_length=20, help_text="e.g. 3:45", default="3:00")
    duration_seconds = models.IntegerField(default=180, help_text="Duration in seconds")
    audio_url = models.URLField(max_length=500, blank=True, null=True)
    live_ai_payload = models.JSONField(default=dict, blank=True)
    live_ai_generated_at = models.DateTimeField(null=True, blank=True)
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
    default_voice_id = models.CharField(max_length=255, blank=True, default='')
    default_voice_name = models.CharField(max_length=255, blank=True, default='')
    tracks = models.ManyToManyField(RadioTrack, through='RadioPlaylistTrack', related_name='playlists')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class RadioPlaylistTrack(models.Model):
    playlist = models.ForeignKey(RadioPlaylist, on_delete=models.CASCADE)
    track = models.ForeignKey(RadioTrack, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)
    voice_over_voice_id = models.CharField(max_length=255, blank=True, default='')
    voice_over_voice_name = models.CharField(max_length=255, blank=True, default='')
    voice_over_text = models.TextField(blank=True)
    voice_over_active = models.BooleanField(default=False)
    duck_volume_percent = models.PositiveSmallIntegerField(default=10)
    voice_over_start_percent = models.PositiveSmallIntegerField(default=0)
    voice_over_length_percent = models.PositiveSmallIntegerField(default=22)

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
    voice_over = models.TextField(blank=True)

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
    voice_over = models.TextField(blank=True)
    playlist = models.ForeignKey(RadioPlaylist, on_delete=models.CASCADE)
    host = models.CharField(max_length=255, default='Auto DJ')
    genre = models.CharField(max_length=50, default='MUSIC')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'start_time']

    def __str__(self):
        return f"{self.template.name} {self.start_time}-{self.end_time}: {self.playlist.name}"
