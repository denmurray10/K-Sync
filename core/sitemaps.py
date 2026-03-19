from django.urls import reverse
from django.contrib.sitemaps import Sitemap


class StaticViewSitemap(Sitemap):
    protocol = "https"
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return [
            "home",
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