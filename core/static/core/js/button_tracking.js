(function () {
    if (typeof window === 'undefined' || typeof document === 'undefined') return;
    if (window.__ksyncButtonTrackingBound) return;
    window.__ksyncButtonTrackingBound = true;

    window.dataLayer = window.dataLayer || [];

    const trackedFormStarts = new WeakSet();
    const scrollMilestones = [25, 50, 75, 100];
    const seenScrollMilestones = new Set();
    const engagementMilestones = [30, 60, 180];
    const seenEngagementMilestones = new Set();
    let engagedSeconds = 0;
    let lastEngagementTick = Date.now();
    let maxScrollPercent = 0;

    const clarity = (...args) => {
        if (typeof window.clarity === 'function') {
            try {
                window.clarity(...args);
            } catch (e) {
                // Analytics failures should never affect page behavior.
            }
        }
    };

    const slugify = (value) => String(value || '')
        .trim()
        .toLowerCase()
        .replace(/['"]/g, '')
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '')
        .slice(0, 80);

    const normalizeDestination = (value) => {
        const raw = String(value || '').trim();
        if (!raw) return '';
        if (raw.startsWith('#')) return raw;

        try {
            const parsed = new URL(raw, window.location.origin);
            if (parsed.origin === window.location.origin) {
                return `${parsed.pathname}${parsed.search}${parsed.hash}`;
            }
            return parsed.toString();
        } catch (e) {
            return raw;
        }
    };

    const getHostFromDestination = (value) => {
        const raw = String(value || '').trim();
        if (!raw || raw.startsWith('#') || raw.startsWith('/')) return '';

        try {
            return new URL(raw, window.location.origin).host || '';
        } catch (e) {
            return '';
        }
    };

    const toClarityValue = (value, fallback = 'unknown') => {
        const normalized = slugify(String(value || '').slice(0, 120));
        return normalized || fallback;
    };

    const setClarityTags = (pairs) => {
        Object.entries(pairs || {}).forEach(([key, value]) => {
            const normalized = toClarityValue(value, '');
            if (normalized) {
                clarity('set', key, normalized);
            }
        });
    };

    const fireClarityEvent = (eventName, tags) => {
        const safeEventName = toClarityValue(eventName, 'site_interaction');
        clarity('event', safeEventName);
        setClarityTags(tags);
    };

    const getVisibleText = (element) => {
        if (!element) return '';

        const preferred = [
            element.dataset?.trackText,
            element.getAttribute?.('aria-label'),
            element.getAttribute?.('title'),
            element.getAttribute?.('name'),
            element.getAttribute?.('value'),
            element.innerText,
            element.textContent,
            element.getAttribute?.('alt'),
        ];

        for (const candidate of preferred) {
            const cleaned = String(candidate || '').replace(/\s+/g, ' ').trim();
            if (cleaned) return cleaned;
        }
        return '';
    };

    const getClosestCategory = (element) => {
        const explicit = element.closest('[data-track-category]');
        if (explicit?.dataset?.trackCategory) {
            return slugify(explicit.dataset.trackCategory) || 'site_interaction';
        }

        const scope = element.closest('header, footer, nav, main, section, aside, form, dialog');
        if (scope) {
            const scopeName = scope.getAttribute('id')
                || scope.getAttribute('aria-label')
                || scope.getAttribute('data-track-scope')
                || scope.tagName.toLowerCase();
            return slugify(scopeName) || 'site_interaction';
        }

        return 'site_interaction';
    };

    const getLabel = (element) => {
        if (element.dataset?.track) {
            return slugify(element.dataset.track) || 'unnamed_control';
        }

        const fromId = slugify(element.id || '');
        if (fromId) return fromId;

        const fromName = slugify(element.getAttribute('name') || '');
        if (fromName) return fromName;

        const fromText = slugify(getVisibleText(element));
        if (fromText) return fromText;

        if (element.tagName.toLowerCase() === 'a') {
            const href = normalizeDestination(element.getAttribute('href'));
            const fromHref = slugify(href);
            if (fromHref) return fromHref;
        }

        return `${element.tagName.toLowerCase()}_interaction`;
    };

    const getDestination = (element) => {
        if (element.dataset?.trackDestination) {
            return normalizeDestination(element.dataset.trackDestination);
        }

        if (element.tagName.toLowerCase() === 'a') {
            return normalizeDestination(element.getAttribute('href'));
        }

        if (element.tagName.toLowerCase() === 'form') {
            return normalizeDestination(element.getAttribute('action') || window.location.pathname);
        }

        const form = element.closest('form');
        if (form && /^(submit|button)$/i.test(element.getAttribute('type') || '')) {
            return normalizeDestination(form.getAttribute('action') || window.location.pathname);
        }

        return '';
    };

    const pushTrackingEvent = (element, eventName) => {
        if (!element || element.closest('[data-track-ignore="true"]')) return;

        const payload = {
            event: eventName,
            click_category: getClosestCategory(element),
            click_label: getLabel(element),
            click_destination: getDestination(element),
            click_text: getVisibleText(element).slice(0, 120),
            click_element: element.tagName.toLowerCase(),
            page_path: window.location.pathname,
        };

        window.dataLayer.push(payload);
        document.dispatchEvent(new CustomEvent('ksync:tracking', { detail: payload }));

        const clarityTags = {
            last_event: eventName,
            last_click_category: payload.click_category,
            last_click_label: payload.click_label,
            last_click_element: payload.click_element,
        };

        if (payload.click_destination) {
            clarityTags.last_click_destination = payload.click_destination;
        }

        fireClarityEvent(eventName, clarityTags);

        if (payload.click_label) {
            fireClarityEvent(`click_${payload.click_label}`, {
                click_category: payload.click_category,
                click_destination: payload.click_destination || 'none',
            });
        }

        const outboundHost = getHostFromDestination(payload.click_destination);
        if (outboundHost && outboundHost !== window.location.host) {
            const outboundPayload = {
                event: 'outbound_click',
                outbound_host: outboundHost,
                click_label: payload.click_label,
                page_path: window.location.pathname,
            };
            window.dataLayer.push(outboundPayload);
            fireClarityEvent('outbound_click', {
                outbound_host: outboundHost,
                outbound_label: payload.click_label,
            });
        }
    };

    const trackScrollDepth = () => {
        const doc = document.documentElement;
        const body = document.body;
        const scrollTop = window.scrollY || doc.scrollTop || body.scrollTop || 0;
        const scrollHeight = Math.max(
            body.scrollHeight,
            doc.scrollHeight,
            body.offsetHeight,
            doc.offsetHeight,
            body.clientHeight,
            doc.clientHeight
        );
        const viewportHeight = window.innerHeight || doc.clientHeight || 1;
        const maxScrollable = Math.max(scrollHeight - viewportHeight, 1);
        const currentPercent = Math.min(100, Math.round((scrollTop / maxScrollable) * 100));

        if (currentPercent > maxScrollPercent) {
            maxScrollPercent = currentPercent;
            setClarityTags({
                max_scroll_depth: `${Math.min(100, Math.floor(maxScrollPercent / 5) * 5)}pct`,
            });
        }

        scrollMilestones.forEach((milestone) => {
            if (currentPercent >= milestone && !seenScrollMilestones.has(milestone)) {
                seenScrollMilestones.add(milestone);
                window.dataLayer.push({
                    event: 'scroll_depth',
                    scroll_depth: milestone,
                    page_path: window.location.pathname,
                });
                fireClarityEvent(`scroll_${milestone}`, {
                    scroll_depth: `${milestone}pct`,
                });
            }
        });
    };

    const trackEngagement = () => {
        const now = Date.now();
        if (document.visibilityState === 'visible') {
            engagedSeconds += Math.max(0, Math.round((now - lastEngagementTick) / 1000));
        }
        lastEngagementTick = now;

        engagementMilestones.forEach((milestone) => {
            if (engagedSeconds >= milestone && !seenEngagementMilestones.has(milestone)) {
                seenEngagementMilestones.add(milestone);
                window.dataLayer.push({
                    event: 'engaged_time',
                    engaged_seconds: milestone,
                    page_path: window.location.pathname,
                });
                fireClarityEvent(`engaged_${milestone}s`, {
                    engagement_bucket: `${milestone}s`,
                });
            }
        });
    };

    const getMediaLabel = (element) => toClarityValue(
        element?.dataset?.track
        || element?.id
        || element?.getAttribute?.('aria-label')
        || element?.currentSrc
        || element?.src
        || element?.tagName,
        'media'
    );

    const trackMediaEvent = (element, action) => {
        const label = getMediaLabel(element);
        const payload = {
            event: 'media_interaction',
            media_action: action,
            media_label: label,
            media_type: element.tagName.toLowerCase(),
            page_path: window.location.pathname,
        };

        window.dataLayer.push(payload);
        fireClarityEvent(`media_${action}`, {
            last_media_action: action,
            last_media_label: label,
            last_media_type: element.tagName.toLowerCase(),
        });
    };

    document.addEventListener('click', function (event) {
        const target = event.target;
        if (!target || typeof target.closest !== 'function') return;

        const interactive = target.closest('a[href], button, input[type="submit"], input[type="button"], [role="button"], summary');
        if (!interactive) return;
        if (interactive.disabled || interactive.getAttribute('aria-disabled') === 'true') return;

        pushTrackingEvent(interactive, 'button_click');
    }, true);

    document.addEventListener('submit', function (event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;
        if (form.closest('[data-track-ignore="true"]')) return;

        const submitter = event.submitter instanceof HTMLElement ? event.submitter : form;
        pushTrackingEvent(submitter, 'form_submit');
    }, true);

    document.addEventListener('focusin', function (event) {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;

        const field = target.closest('input, select, textarea');
        if (!(field instanceof HTMLElement)) return;

        const form = field.closest('form');
        if (!(form instanceof HTMLFormElement)) return;
        if (trackedFormStarts.has(form) || form.closest('[data-track-ignore="true"]')) return;

        trackedFormStarts.add(form);
        const formName = toClarityValue(
            form.getAttribute('id')
            || form.getAttribute('name')
            || form.getAttribute('action')
            || 'form'
        );

        window.dataLayer.push({
            event: 'form_start',
            form_name: formName,
            page_path: window.location.pathname,
        });
        fireClarityEvent('form_start', {
            last_form_started: formName,
        });
    }, true);

    document.addEventListener('play', function (event) {
        const target = event.target;
        if (target instanceof HTMLMediaElement) {
            trackMediaEvent(target, 'play');
        }
    }, true);

    document.addEventListener('pause', function (event) {
        const target = event.target;
        if (target instanceof HTMLMediaElement && !target.ended) {
            trackMediaEvent(target, 'pause');
        }
    }, true);

    document.addEventListener('ended', function (event) {
        const target = event.target;
        if (target instanceof HTMLMediaElement) {
            trackMediaEvent(target, 'complete');
        }
    }, true);

    document.addEventListener('visibilitychange', trackEngagement);
    window.addEventListener('scroll', trackScrollDepth, { passive: true });
    window.addEventListener('beforeunload', trackEngagement);

    trackScrollDepth();
    lastEngagementTick = Date.now();
    window.setInterval(trackEngagement, 10000);
})();
