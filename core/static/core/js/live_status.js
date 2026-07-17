(function () {
    'use strict';

    if (window.KBeatsLiveStatus) return;

    const endpoint = '/api/live/status/';
    const subscribers = new Set();
    const minimumFreshnessMs = 8000;
    const pollIntervalMs = 15000;
    let latest = null;
    let lastFetchedAt = 0;
    let inFlight = null;
    let pollTimer = null;

    function publish(data) {
        latest = data;
        lastFetchedAt = Date.now();
        subscribers.forEach((callback) => {
            try {
                callback(data);
            } catch (error) {
                // A consumer should never stop the shared live-status channel.
            }
        });
        window.dispatchEvent(new CustomEvent('kbeats:live-status', { detail: data }));
        return data;
    }

    async function refresh(options) {
        const force = Boolean(options && options.force);
        if (!force && latest && Date.now() - lastFetchedAt < minimumFreshnessMs) {
            return latest;
        }
        if (inFlight) return inFlight;

        inFlight = fetch(`${endpoint}?_ts=${Date.now()}`, { cache: 'no-store' })
            .then((response) => {
                if (!response.ok) throw new Error(`Live status returned ${response.status}`);
                return response.json();
            })
            .then((data) => publish(data))
            .finally(() => {
                inFlight = null;
            });

        return inFlight;
    }

    function start() {
        if (pollTimer) return;
        refresh().catch(() => {});
        pollTimer = window.setInterval(() => {
            if (!document.hidden) refresh().catch(() => {});
        }, pollIntervalMs);
    }

    function subscribe(callback, options) {
        if (typeof callback !== 'function') return function () {};
        subscribers.add(callback);
        if ((!options || options.immediate !== false) && latest) callback(latest);
        start();
        return function unsubscribe() {
            subscribers.delete(callback);
        };
    }

    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) refresh().catch(() => {});
    });

    window.KBeatsLiveStatus = {
        getLatest: () => latest,
        refresh,
        subscribe,
        start,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start, { once: true });
    } else {
        start();
    }
})();
