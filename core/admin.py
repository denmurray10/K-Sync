from django.contrib import admin
from .models import (
    LivePoll, LivePollOption, UserProfile, FavouriteSong,
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
