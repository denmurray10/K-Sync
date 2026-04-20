from django.urls import reverse
from django.contrib.sitemaps import Sitemap
from .models import BlogArticle, KPopGroup, KPopMember


class StaticViewSitemap(Sitemap):
    protocol = "https"
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return [
            "home",
            "listen_free_landing",
            "uk_kpop_radio",
            "midnight_kpop_vibes",
            "rainy_day_kpop",
            "late_night_kpop_music",
            "best_kpop_playlist_2026",
            "discover_new_kpop_music",
            "live",
            "schedule",
            "charts",
            "news",
            "idols",
            "comeback_timeline",
            "presenters",
            "fan_clubs",
            "about_us",
            "privacy_policy",
            "cookie_policy",
            "terms_of_service",
        ]

    def location(self, item):
        return reverse(item)


class BlogArticleSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return BlogArticle.objects.order_by('-created_at')

    def lastmod(self, obj):
        return obj.created_at

    def location(self, obj):
        return reverse('blog_article_read', kwargs={'slug': obj.slug})


class GroupProfileSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return KPopGroup.objects.order_by('name')

    def location(self, obj):
        return reverse('idol_page', args=[obj.slug])


class MemberProfileSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return KPopMember.objects.select_related('group').filter(is_active=True).order_by('group__name', 'order', 'name')

    def location(self, obj):
        return reverse('member_page', args=[obj.group.slug, obj.slug])


class MemberBirthdaySitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return KPopMember.objects.select_related('group').filter(is_active=True, date_of_birth__isnull=False).order_by('group__name', 'order', 'name')

    def location(self, obj):
        return reverse('member_birthday_page', args=[obj.group.slug, obj.slug])
