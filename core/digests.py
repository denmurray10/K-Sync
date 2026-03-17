import re
from zoneinfo import ZoneInfo

from django.core.mail import send_mail
from django.utils import timezone

from .models import ComebackData, Ranking, UserNotification, UserProfile


def _safe_user_tz(tz_name):
    candidate = str(tz_name or '').strip() or 'Europe/London'
    try:
        return ZoneInfo(candidate)
    except Exception:
        return ZoneInfo('Europe/London')


def _collect_digest_content(local_date):
    year = local_date.year
    month = local_date.month
    date_key = local_date.strftime('%Y-%m-%d')

    comeback_obj = ComebackData.objects.filter(year=year, month=month).first()
    day_data = (comeback_obj.data or {}).get(date_key, {}) if comeback_obj else {}

    releases = []
    for release in day_data.get('releases', [])[:5]:
        artist = str(release.get('artist') or 'Unknown artist').strip()
        title = str(release.get('title') or 'New release').strip()
        releases.append({'artist': artist, 'title': title})

    birthdays = []
    for member in day_data.get('birthdays', [])[:5]:
        name = str(member.get('name') or 'Member').strip()
        group = str(member.get('group') or '').strip()
        birthdays.append({'name': name, 'group': group})

    daily_ranking = Ranking.objects.filter(timeframe='daily').order_by('-date').first()
    chart_jumps = []
    if daily_ranking and daily_ranking.ranking_data:
        for item in (daily_ranking.ranking_data or [])[:20]:
            trend_text = str(item.get('trend') or '').strip()
            match = re.search(r'\+(\d+)', trend_text)
            if not match:
                continue
            jump_size = int(match.group(1))
            if jump_size < 5:
                continue
            chart_jumps.append({
                'artist': str(item.get('artist') or 'Unknown artist').strip(),
                'track': str(item.get('track') or 'Unknown track').strip(),
                'trend': trend_text,
            })
            if len(chart_jumps) >= 5:
                break

    return {
        'releases': releases,
        'birthdays': birthdays,
        'chart_jumps': chart_jumps,
    }


def _compose_digest_text(content, profile):
    lines = []

    if profile.digest_include_comebacks and content['releases']:
        lines.append('Comebacks:')
        for item in content['releases'][:3]:
            lines.append(f"• {item['artist']} — {item['title']}")

    if profile.digest_include_birthdays and content['birthdays']:
        lines.append('Birthdays:')
        for item in content['birthdays'][:3]:
            if item['group']:
                lines.append(f"• {item['name']} ({item['group']})")
            else:
                lines.append(f"• {item['name']}")

    if profile.digest_include_chart_jumps and content['chart_jumps']:
        lines.append('Chart jumps:')
        for item in content['chart_jumps'][:3]:
            lines.append(f"• {item['artist']} — {item['track']} ({item['trend']})")

    return '\n'.join(lines).strip()


def send_due_user_digests(now_utc=None):
    now_utc = now_utc or timezone.now()
    sent_count = 0

    profiles = UserProfile.objects.select_related('user').filter(digest_enabled=True)

    for profile in profiles:
        user = profile.user
        if not user:
            continue

        local_now = now_utc.astimezone(_safe_user_tz(profile.digest_timezone))
        if int(profile.digest_hour or 8) != local_now.hour:
            continue

        if profile.digest_last_sent_on == local_now.date():
            continue

        content = _collect_digest_content(local_now.date())
        body = _compose_digest_text(content, profile)
        if not body:
            continue

        sent_any = False

        if profile.digest_channel_push:
            UserNotification.objects.create(
                user=user,
                message=f"Your K-Beats digest is ready.\n{body}",
                type='ALERT',
                link='/dashboard/',
            )
            sent_any = True

        if profile.digest_channel_email and user.email:
            send_mail(
                subject='Your K-Beats Daily Digest',
                message=(
                    f"Hi {user.username},\n\n"
                    f"Here is your K-Beats digest for {local_now.strftime('%d %b %Y')}.\n\n"
                    f"{body}\n\n"
                    "Open K-Beats: https://kbeats.uk/dashboard/"
                ),
                from_email=None,
                recipient_list=[user.email],
                fail_silently=True,
            )
            sent_any = True

        if sent_any:
            profile.digest_last_sent_on = local_now.date()
            profile.save(update_fields=['digest_last_sent_on'])
            sent_count += 1

    return sent_count
