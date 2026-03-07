from django.test import TestCase

from .models import BlogArticle


class BlogArticleSanitizationTests(TestCase):
    def test_save_sanitizes_disallowed_tags_and_attrs(self):
        article = BlogArticle.objects.create(
            slug='sanitize-1',
            title='Sanitize Test',
            subtitle='',
            category='news',
            source_title='Source',
            source_url='https://example.com',
            source_name='Example',
            image='',
            image_2='',
            body_html=(
                '<p>Hello</p><script>alert(1)</script>'
                '<a href="https://safe.example" onclick="evil()">link</a>'
            ),
            reading_time=1,
        )

        self.assertIn('<p>Hello</p>', article.body_html)
        self.assertNotIn('<script>', article.body_html)
        self.assertNotIn('onclick=', article.body_html)
        self.assertIn(
            '<a href="https://safe.example">link</a>',
            article.body_html,
        )

    def test_save_keeps_allowed_structure_and_handles_none(self):
        article = BlogArticle.objects.create(
            slug='sanitize-2',
            title='Allowed Tags Test',
            subtitle='',
            category='news',
            source_title='Source',
            source_url='https://example.com',
            source_name='Example',
            image='',
            image_2='',
            body_html=None,
            reading_time=1,
        )
        self.assertEqual(article.body_html, '')

        article.body_html = (
            '<p><strong>ok</strong> <em>fine</em></p>'
            '<h3>Header</h3><ul><li>One</li></ul>'
        )
        article.save()

        self.assertIn(
            '<p><strong>ok</strong> <em>fine</em></p>',
            article.body_html,
        )
        self.assertIn('<h3>Header</h3>', article.body_html)
        self.assertIn('<ul><li>One</li></ul>', article.body_html)
