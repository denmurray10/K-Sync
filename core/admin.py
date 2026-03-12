from django.contrib import admin
from .models import (
    LivePoll, LivePollOption, UserProfile, FavouriteSong,
    GameScore, SongRequest, Contest, ContestEntry,
    FanClubMembership, PreLaunchSignup, BlogArticle,
)


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
    list_display = ('user', 'group', 'joined_at')
    list_filter = ('group', 'joined_at')
    raw_id_fields = ('user', 'group')


@admin.register(PreLaunchSignup)
class PreLaunchSignupAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'age', 'signed_up_at')
    list_filter = ('signed_up_at',)
    search_fields = ('name', 'email')


@admin.register(BlogArticle)
class BlogArticleAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'category',
        'created_at',
        'facebook_status',
        'x_status',
        'pinterest_status',
    )
    list_filter = (
        'category', 'created_at', 'facebook_posted_at',
        'x_posted_at', 'pinterest_posted_at',
    )
    search_fields = (
        'title', 'subtitle', 'slug', 'source_name', 'source_title',
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

    @admin.display(description='Facebook')
    def facebook_status(self, obj):
        return '✅' if obj.facebook_posted_at else '—'

    @admin.display(description='X')
    def x_status(self, obj):
        return '✅' if obj.x_posted_at else '—'

    @admin.display(description='Pinterest')
    def pinterest_status(self, obj):
        return '✅' if obj.pinterest_posted_at else '—'
