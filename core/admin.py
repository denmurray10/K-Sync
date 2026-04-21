from django.contrib import admin
from .models import (
    KPopGroup, KPopMember, MemberMilestone, BirthdayFeature,
    LivePoll, LivePollOption, UserProfile, FavouriteSong,
    GameScore, SongRequest, Contest, ContestEntry,
    FanClubMembership, PreLaunchSignup, BlogArticle,
    EmailPromotionSignup,
    LimitedTimeEvent, EventBadgeDrop, EventParticipation,
    RadioTrack, RadioStationState,
    RadioPlaylist, RadioPlaylistTrack, RadioSchedule,
    ChatBlockedTerm,
)


class MemberMilestoneInline(admin.TabularInline):
    model = MemberMilestone
    extra = 0


class BirthdayFeatureInline(admin.TabularInline):
    model = BirthdayFeature
    extra = 0


@admin.register(KPopGroup)
class KPopGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'group_type', 'agency', 'label', 'rank')
    list_filter = ('group_type',)
    search_fields = ('name', 'slug', 'agency', 'fandom_name')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(KPopMember)
class KPopMemberAdmin(admin.ModelAdmin):
    list_display = ('display_name_admin', 'group', 'resolved_positions_admin', 'date_of_birth', 'is_active')
    list_filter = ('group', 'is_active')
    search_fields = ('name', 'stage_name', 'full_name', 'slug', 'group__name')
    inlines = [MemberMilestoneInline, BirthdayFeatureInline]

    @admin.display(description='Display name')
    def display_name_admin(self, obj):
        return obj.display_name

    @admin.display(description='Positions')
    def resolved_positions_admin(self, obj):
        return obj.resolved_positions

class RadioPlaylistTrackInline(admin.TabularInline):
    model = RadioPlaylistTrack
    extra = 5
    raw_id_fields = ('track',)

@admin.register(RadioPlaylist)
class RadioPlaylistAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    inlines = [RadioPlaylistTrackInline]

@admin.register(RadioSchedule)
class RadioScheduleAdmin(admin.ModelAdmin):
    list_display = ('day', 'start_time', 'end_time', 'playlist', 'host', 'genre')
    list_filter = ('day', 'genre')
    search_fields = ('playlist__name', 'host')


class LivePollOptionInline(admin.TabularInline):
    model = LivePollOption
    extra = 3

@admin.register(LivePoll)
class LivePollAdmin(admin.ModelAdmin):
    list_display = ('question', 'is_active', 'created_at')
    inlines = [LivePollOptionInline]

admin.site.register(LivePollOption)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'bias')
    raw_id_fields = ('user', 'bias')


@admin.register(FavouriteSong)
class FavouriteSongAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'artist', 'added_at')
    list_filter = ('added_at',)
    raw_id_fields = ('user',)


@admin.register(GameScore)
class GameScoreAdmin(admin.ModelAdmin):
    list_display = ('user', 'game', 'score', 'correct', 'total', 'best_streak', 'played_at')
    list_filter = ('game', 'played_at')
    raw_id_fields = ('user',)


@admin.register(SongRequest)
class SongRequestAdmin(admin.ModelAdmin):
    list_display = ('song_title', 'artist', 'listener_name', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('song_title', 'artist', 'listener_name')


class ContestEntryInline(admin.TabularInline):
    model = ContestEntry
    extra = 0
    readonly_fields = ('name', 'email', 'country', 'username', 'answer', 'submitted_at')
    can_delete = False


@admin.register(Contest)
class ContestAdmin(admin.ModelAdmin):
    list_display = ('title', 'contest_number', 'artist', 'deadline', 'is_active', 'is_featured', 'entry_count')
    list_filter = ('is_active', 'is_featured')
    search_fields = ('title', 'artist')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ContestEntryInline]


@admin.register(ContestEntry)
class ContestEntryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'contest', 'country', 'submitted_at')
    list_filter = ('contest', 'submitted_at')
    search_fields = ('name', 'email', 'username')
    readonly_fields = ('submitted_at',)


@admin.register(FanClubMembership)
class FanClubMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'tier', 'joined_at')
    list_filter = ('group', 'tier', 'joined_at')
    raw_id_fields = ('user', 'group')


@admin.register(LimitedTimeEvent)
class LimitedTimeEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_type', 'starts_at', 'ends_at', 'is_active')
    list_filter = ('event_type', 'is_active')
    search_fields = ('title', 'slug')


@admin.register(EventBadgeDrop)
class EventBadgeDropAdmin(admin.ModelAdmin):
    list_display = ('badge_name', 'event', 'rarity', 'minimum_tier', 'min_votes_required', 'is_active')
    list_filter = ('rarity', 'minimum_tier', 'is_active')
    search_fields = ('badge_name', 'event__title')


@admin.register(EventParticipation)
class EventParticipationAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'votes_cast', 'joined_at')
    list_filter = ('event', 'joined_at')
    search_fields = ('user__username', 'event__title')


@admin.register(PreLaunchSignup)
class PreLaunchSignupAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'age', 'signed_up_at')
    list_filter = ('signed_up_at',)
    search_fields = ('name', 'email')


@admin.register(EmailPromotionSignup)
class EmailPromotionSignupAdmin(admin.ModelAdmin):
    list_display = ('email', 'source', 'created_at')
    list_filter = ('source', 'created_at')
    search_fields = ('email',)


@admin.register(BlogArticle)
class BlogArticleAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'category',
        'writer_name',
        'tags_preview',
        'created_at',
        'facebook_status',
        'x_status',
        'pinterest_status',
    )
    list_filter = (
        'category', 'writer_slug', 'created_at', 'facebook_posted_at',
        'x_posted_at', 'pinterest_posted_at',
    )
    search_fields = (
        'title', 'subtitle', 'slug', 'writer_slug', 'source_name', 'source_title', 'editorial_tags',
    )
    readonly_fields = (
        'slug',
        'created_at',
        'facebook_post_id',
        'facebook_posted_at',
        'x_post_id',
        'x_posted_at',
        'pinterest_post_id',
        'pinterest_posted_at',
    )

    @admin.display(description='Writer')
    def writer_name(self, obj):
        return obj.writer_name

    @admin.display(description='Tags')
    def tags_preview(self, obj):
        return ', '.join(obj.tags_list[:2]) or '—'

    @admin.display(description='Facebook')
    def facebook_status(self, obj):
        return '✅' if obj.facebook_posted_at else '—'

    @admin.display(description='X')
    def x_status(self, obj):
        return '✅' if obj.x_posted_at else '—'

    @admin.display(description='Pinterest')
    def pinterest_status(self, obj):
        return '✅' if obj.pinterest_posted_at else '—'


@admin.register(RadioTrack)
class RadioTrackAdmin(admin.ModelAdmin):
    list_display = ('title', 'artist', 'duration', 'is_request', 'created_at')
    list_filter = ('is_request', 'created_at')
    search_fields = ('title', 'artist')

@admin.register(RadioStationState)
class RadioStationStateAdmin(admin.ModelAdmin):
    list_display = ('current_track', 'listeners_count', 'updated_at')
    readonly_fields = ('updated_at',)


@admin.register(ChatBlockedTerm)
class ChatBlockedTermAdmin(admin.ModelAdmin):
    list_display = ('term', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('term',)
