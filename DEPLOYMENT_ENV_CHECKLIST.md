# Deployment Environment Checklist

Use this checklist to keep production aligned with local runtime config.

## Required Cloudinary variables

Set all of these in your hosting provider (Heroku/Render/etc):

- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

These are required for:
- Cloud-only voiceover synthesis (`/api/voiceover/synthesize/`)
- Migrating legacy local voiceovers to Cloudinary (`migrate_voiceovers_to_cloudinary`)

## Optional audio delivery toggle

- `AUDIO_STREAM_USE_CLOUDINARY_FETCH` (`true`/`false`)
- `AUDIO_STREAM_CLOUDINARY_TRANSFORM` (default: `q_auto:eco,br_96k,f_mp3`)

## Verify after setting vars

Run:

```bash
python manage.py shell -c "from django.conf import settings; print(bool(settings.CLOUDINARY_CLOUD_NAME), bool(settings.CLOUDINARY_API_KEY), bool(settings.CLOUDINARY_API_SECRET))"
```

Expected output:

```text
True True True
```

## Heroku quick set

```bash
heroku config:set CLOUDINARY_CLOUD_NAME=... CLOUDINARY_API_KEY=... CLOUDINARY_API_SECRET=...
```

## Render quick set

In Render Dashboard:
- Service → Environment
- Add the 3 Cloudinary variables above
- Save and redeploy
