(function () {
    if (typeof window === 'undefined' || typeof document === 'undefined') return;
    if (window.__ksyncButtonTrackingBound) return;
    window.__ksyncButtonTrackingBound = true;

    window.dataLayer = window.dataLayer || [];

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
})();
