from django.urls import reverse
from django.contrib.sitemaps import Sitemap
from .models import BlogArticle


class StaticViewSitemap(Sitemap):
    protocol = "https"
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return [
            "home",
            "listen_free_landing",
            "live",
            "schedule",
            "charts",
            "news",
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
