(function () {
    'use strict';

    const STORAGE_KEY = 'ksync_visitor_tour_seen_v1';
    const KBeatsVisitorTour = {};
    const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let overlay = null;
    let spotlight = null;
    let panel = null;
    let activeTarget = null;
    let activeSteps = [];
    let currentIndex = 0;
    let repositionFrame = null;

    const pagePath = window.location.pathname || '/';
    const isHomePage = pagePath === '/' || pagePath === '';
    const isLivePage = pagePath.indexOf('/live') === 0;

    const visitorTourSteps = [
        {
            id: 'welcome',
            title: 'Welcome to K-Beats',
            body: 'This quick tour shows where to listen live, explore charts, follow comebacks, read news, play games, and open your own station controls.',
            hint: 'Use Next to move through the essentials.',
        },
        {
            id: 'home-hero',
            selector: '[data-tour-target="home-hero"], #hero-section',
            pages: ['home'],
            title: 'Start at the main stage',
            body: 'The homepage gives first-time visitors the big picture: live K-pop radio, chart discovery, comeback tracking, and featured editorial.',
            hint: 'Featured stories and jump links move you deeper into the site.',
        },
        {
            id: 'live-player',
            selector: '[data-tour-target="live-player"], #home-live-player-bar',
            pages: ['home'],
            title: 'Listen without hunting',
            body: 'This live player shows what is on air and gives visitors a fast route into the full radio experience.',
            hint: 'Use Live On Air for the full player, queue, requests, and sharing tools.',
        },
        {
            id: 'navigation',
            selector: '[data-tour-target="navigation"], [data-tour-target="mobile-nav"], #desktop-primary-nav, .mobile-app-bar',
            title: 'Use the main navigation',
            body: 'Live, Charts, Idols, Games, Comebacks, and News are the main visitor paths. On mobile, the bottom dock keeps the key areas close.',
            hint: 'The active section is highlighted with the K-Beats neon treatment.',
        },
        {
            id: 'live-on-air',
            selector: '[data-tour-target="live-on-air"], [data-track="live_on_air_header"], [data-track="nav_live_mobile"]',
            title: 'Jump straight to radio',
            body: 'Live On Air takes visitors to the full K-Beats stream with playback, track details, upcoming songs, and fan actions.',
            hint: 'This is the fastest path for people who came here to listen.',
        },
        {
            id: 'my-station',
            selector: '[data-tour-target="my-station"], #my-station-launcher, [aria-controls="my-station-panel"]',
            title: 'Open My Station',
            body: 'My Station is the personal layer. Signed-in fans can get preferences, notifications, dashboard access, and listening shortcuts here.',
            hint: 'Guests see a prompt to sign up or log in before personalization unlocks.',
        },
        {
            id: 'charts',
            selector: '[data-tour-target="charts"], [data-track="nav_charts"]',
            pages: ['home'],
            title: 'Check the chart pulse',
            body: 'Charts show the songs currently moving through the K-Beats universe, making it easy to spot what is hot right now.',
            hint: 'Visitors can move from a chart hit into artist pages and related discovery.',
        },
        {
            id: 'comebacks',
            selector: '[data-tour-target="comebacks"], [data-track="nav_comebacks"]',
            pages: ['home'],
            title: 'Follow comeback signals',
            body: 'Comebacks collect upcoming releases and fan-relevant date signals so visitors can track what is landing next.',
            hint: 'This is a strong return-visit loop for active fans.',
        },
        {
            id: 'news',
            selector: '[data-tour-target="news"], [data-track="nav_news"]',
            pages: ['home'],
            title: 'Read the latest stories',
            body: 'News and editorial pages give context around artists, releases, tours, and fandom moments beyond the live stream.',
            hint: 'Featured articles are also surfaced from the homepage hero.',
        },
        {
            id: 'live-play',
            selector: '[data-tour-target="live-play"], #play-btn',
            pages: ['live'],
            title: 'Press play',
            body: 'The main live button starts the stream. The current track, artist, artwork, progress, and volume controls update around it.',
            hint: 'The page also syncs with the compact mobile player in the menu.',
        },
        {
            id: 'live-share',
            selector: '[data-tour-target="live-share"], #share-now-playing-btn',
            pages: ['live'],
            title: 'Share what is playing',
            body: 'Share Now Playing creates a quick social payload for the current song, so visitors can bring friends back to the live stream.',
            hint: 'On browsers without native sharing, the link is copied instead.',
        },
        {
            id: 'live-save',
            selector: '[data-tour-target="live-save"], #save-moment-btn',
            pages: ['live'],
            title: 'Save a listening moment',
            body: 'Save This Moment lets signed-in fans keep the current track as part of their listening history and personal station activity.',
            hint: 'Guests are nudged to log in before saving.',
        },
        {
            id: 'request-song',
            selector: '[data-tour-target="request-song"], a[href$="/request/"]',
            pages: ['live'],
            title: 'Request a song',
            body: 'The request action lets fans ask for tracks and gives the live page a more participatory radio feel.',
            hint: 'Fan requests can appear in the live queue when accepted.',
        },
        {
            id: 'up-next',
            selector: '[data-tour-target="up-next"], #up-next-container',
            pages: ['live'],
            title: 'See what is coming',
            body: 'Up Next previews the upcoming run of songs and shows countdown timing when available.',
            hint: 'Fan requests are marked so visitors can spot community picks.',
        },
        {
            id: 'recently-played',
            selector: '[data-tour-target="recently-played"], #recently-played-container',
            pages: ['live'],
            title: 'Find what just played',
            body: 'Recently Played helps visitors recover the track they just heard and keeps the radio page useful after a song changes.',
            hint: 'It is especially helpful for new listeners discovering artists.',
        },
        {
            id: 'live-chat',
            selector: '[data-tour-target="live-chat"], #chat-messages, #chat-input',
            pages: ['live'],
            title: 'Chat with other fans',
            body: 'Live chat is available to signed-in members, giving the stream a community layer while guests can still listen freely.',
            hint: 'If chat is hidden, log in to unlock the member-only conversation.',
            allowMissingTarget: true,
        },
    ];

    function pageMatches(step) {
        if (!step.pages || !step.pages.length) return true;
        if (step.pages.includes('home') && isHomePage) return true;
        if (step.pages.includes('live') && isLivePage) return true;
        return false;
    }

    function getStoredSeen() {
        try {
            return window.localStorage.getItem(STORAGE_KEY) === '1';
        } catch (err) {
            return false;
        }
    }

    function setStoredSeen() {
        try {
            window.localStorage.setItem(STORAGE_KEY, '1');
        } catch (err) {
            // Storage can be unavailable in private browsing; the tour still works.
        }
    }

    function getVisibleTarget(selector) {
        if (!selector) return null;

        let candidates = [];
        try {
            candidates = Array.from(document.querySelectorAll(selector));
        } catch (err) {
            return null;
        }

        const visible = candidates.find((el) => {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return rect.width > 2
                && rect.height > 2
                && style.display !== 'none'
                && style.visibility !== 'hidden'
                && Number(style.opacity || 1) !== 0;
        });

        return visible || candidates[0] || null;
    }

    function buildSteps() {
        return visitorTourSteps.filter(pageMatches);
    }

    function createOverlay() {
        if (overlay) return;

        overlay = document.createElement('div');
        overlay.id = 'visitor-tour-overlay';
        overlay.hidden = true;
        overlay.setAttribute('aria-hidden', 'true');
        overlay.innerHTML = `
            <div class="visitor-tour-scrim" data-tour-skip></div>
            <div class="visitor-tour-spotlight" aria-hidden="true"></div>
            <section class="visitor-tour-panel" role="dialog" aria-modal="true" aria-labelledby="visitor-tour-title">
                <div class="visitor-tour-panel__bar">
                    <span class="visitor-tour-kicker">K-Beats Tour</span>
                    <span class="visitor-tour-count" data-tour-count></span>
                    <button class="visitor-tour-close" type="button" data-tour-skip aria-label="Close website tour">
                        <span class="material-symbols-outlined" aria-hidden="true">close</span>
                    </button>
                </div>
                <div class="visitor-tour-panel__body">
                    <h2 id="visitor-tour-title" class="visitor-tour-title" data-tour-title></h2>
                    <p class="visitor-tour-copy" data-tour-body></p>
                    <p class="visitor-tour-hint" data-tour-hint></p>
                    <div class="visitor-tour-progress" aria-hidden="true">
                        <span class="visitor-tour-progress__fill" data-tour-progress></span>
                    </div>
                </div>
                <div class="visitor-tour-panel__actions">
                    <div class="visitor-tour-panel__actions-left">
                        <button class="visitor-tour-button" type="button" data-tour-skip>Skip</button>
                    </div>
                    <div class="visitor-tour-panel__actions-right">
                        <button class="visitor-tour-button" type="button" data-tour-prev>Back</button>
                        <button class="visitor-tour-button visitor-tour-button--primary" type="button" data-tour-next>Next</button>
                    </div>
                </div>
            </section>
        `;

        document.body.appendChild(overlay);
        spotlight = overlay.querySelector('.visitor-tour-spotlight');
        panel = overlay.querySelector('.visitor-tour-panel');

        overlay.querySelectorAll('[data-tour-skip]').forEach((btn) => {
            btn.addEventListener('click', () => finishTour(true));
        });
        overlay.querySelector('[data-tour-prev]').addEventListener('click', previousStep);
        overlay.querySelector('[data-tour-next]').addEventListener('click', nextStep);
    }

    function clearActiveTarget() {
        if (activeTarget) {
            activeTarget.classList.remove('visitor-tour-active-target');
            activeTarget = null;
        }
    }

    function findStepFrom(startIndex, direction) {
        for (let i = startIndex; i >= 0 && i < activeSteps.length; i += direction) {
            const step = activeSteps[i];
            const target = getVisibleTarget(step.selector);
            if (!step.selector || target || step.allowMissingTarget) {
                return { index: i, step, target };
            }
        }
        return null;
    }

    function isMostlyInViewport(rect) {
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
        const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
        return rect.bottom > 96
            && rect.top < viewportHeight - 96
            && rect.right > 32
            && rect.left < viewportWidth - 32;
    }

    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    function updatePanelPosition(target, isCentered) {
        if (!panel || !spotlight) return;

        const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
        const panelWidth = panel.offsetWidth || Math.min(368, viewportWidth - 32);
        const panelHeight = panel.offsetHeight || 260;
        const edge = 16;

        if (!target || isCentered) {
            spotlight.classList.remove('is-visible');
            panel.style.left = `${Math.max(edge, (viewportWidth - panelWidth) / 2)}px`;
            panel.style.top = `${Math.max(edge, (viewportHeight - panelHeight) / 2)}px`;
            return;
        }

        const rawRect = target.getBoundingClientRect();
        const pad = 9;
        const top = clamp(rawRect.top - pad, edge, viewportHeight - edge);
        const left = clamp(rawRect.left - pad, edge, viewportWidth - edge);
        const right = clamp(rawRect.right + pad, edge, viewportWidth - edge);
        const bottom = clamp(rawRect.bottom + pad, edge, viewportHeight - edge);
        const width = Math.max(24, right - left);
        const height = Math.max(24, bottom - top);

        spotlight.style.top = `${top}px`;
        spotlight.style.left = `${left}px`;
        spotlight.style.width = `${width}px`;
        spotlight.style.height = `${height}px`;
        spotlight.classList.add('is-visible');

        const preferredLeft = clamp(left + (width / 2) - (panelWidth / 2), edge, viewportWidth - panelWidth - edge);
        const belowTop = bottom + 18;
        const aboveTop = top - panelHeight - 18;
        let panelTop = belowTop;

        if (belowTop + panelHeight > viewportHeight - edge && aboveTop >= edge) {
            panelTop = aboveTop;
        } else if (belowTop + panelHeight > viewportHeight - edge) {
            panelTop = clamp(viewportHeight - panelHeight - edge, edge, viewportHeight - panelHeight - edge);
        }

        panel.style.left = `${preferredLeft}px`;
        panel.style.top = `${panelTop}px`;
    }

    function renderStep(resolved) {
        const { index, step, target } = resolved;
        currentIndex = index;
        clearActiveTarget();

        const titleEl = overlay.querySelector('[data-tour-title]');
        const bodyEl = overlay.querySelector('[data-tour-body]');
        const hintEl = overlay.querySelector('[data-tour-hint]');
        const countEl = overlay.querySelector('[data-tour-count]');
        const progressEl = overlay.querySelector('[data-tour-progress]');
        const prevBtn = overlay.querySelector('[data-tour-prev]');
        const nextBtn = overlay.querySelector('[data-tour-next]');

        titleEl.textContent = step.title || '';
        bodyEl.textContent = step.body || '';
        hintEl.textContent = step.hint || '';
        hintEl.hidden = !step.hint;
        countEl.textContent = `${index + 1} / ${activeSteps.length}`;
        progressEl.style.width = `${((index + 1) / activeSteps.length) * 100}%`;
        prevBtn.disabled = !findStepFrom(index - 1, -1);
        nextBtn.textContent = findStepFrom(index + 1, 1) ? 'Next' : 'Finish';

        if (target) {
            activeTarget = target;
            activeTarget.classList.add('visitor-tour-active-target');
        }

        window.setTimeout(() => {
            updatePanelPosition(target, !target);
            const focusTarget = nextBtn || panel;
            if (focusTarget && typeof focusTarget.focus === 'function') focusTarget.focus({ preventScroll: true });
        }, reduceMotion ? 20 : 220);
    }

    function goToIndex(index, direction) {
        const resolved = findStepFrom(index, direction);
        if (!resolved) {
            finishTour(true);
            return;
        }

        const target = resolved.target;
        if (target) {
            const rect = target.getBoundingClientRect();
            if (!isMostlyInViewport(rect)) {
                target.scrollIntoView({
                    block: 'center',
                    inline: 'nearest',
                    behavior: reduceMotion ? 'auto' : 'smooth',
                });
            }
        }

        renderStep(resolved);
    }

    function nextStep() {
        const resolved = findStepFrom(currentIndex + 1, 1);
        if (!resolved) {
            finishTour(true);
            return;
        }
        goToIndex(resolved.index, 1);
    }

    function previousStep() {
        const resolved = findStepFrom(currentIndex - 1, -1);
        if (!resolved) return;
        goToIndex(resolved.index, -1);
    }

    function finishTour(markSeen) {
        if (markSeen !== false) setStoredSeen();
        clearActiveTarget();
        if (overlay) {
            overlay.hidden = true;
            overlay.setAttribute('aria-hidden', 'true');
        }
        if (spotlight) spotlight.classList.remove('is-visible');
        document.body.classList.remove('visitor-tour-open');
    }

    function startTour(options = {}) {
        createOverlay();
        activeSteps = buildSteps();
        currentIndex = 0;
        if (!activeSteps.length) return;

        overlay.hidden = false;
        overlay.setAttribute('aria-hidden', 'false');
        document.body.classList.add('visitor-tour-open');
        goToIndex(0, 1);

        if (options.markUnseen) {
            try {
                window.localStorage.removeItem(STORAGE_KEY);
            } catch (err) {
                // Ignore storage errors.
            }
        }
    }

    function scheduleReposition() {
        if (!overlay || overlay.hidden || repositionFrame) return;
        repositionFrame = window.requestAnimationFrame(() => {
            repositionFrame = null;
            const step = activeSteps[currentIndex];
            const target = step ? getVisibleTarget(step.selector) : null;
            updatePanelPosition(target, !target);
        });
    }

    function isInternalPath() {
        const internalPrefixes = [
            '/staff/',
            '/playlist-manager/',
            '/track-manager/',
            '/song-upload-manager/',
            '/blog/generate/',
            '/blog/link-pass/',
            '/internal/',
        ];
        return internalPrefixes.some((prefix) => pagePath.indexOf(prefix) === 0);
    }

    function bindControls() {
        document.querySelectorAll('[data-tour-start]').forEach((button) => {
            button.addEventListener('click', () => startTour({ manual: true, markUnseen: true }));
        });

        document.addEventListener('keydown', (event) => {
            if (!overlay || overlay.hidden) return;
            if (event.key === 'Escape') {
                finishTour(true);
            } else if (event.key === 'ArrowRight') {
                nextStep();
            } else if (event.key === 'ArrowLeft') {
                previousStep();
            }
        });

        window.addEventListener('resize', scheduleReposition);
        window.addEventListener('scroll', scheduleReposition, { passive: true });
    }

    KBeatsVisitorTour.start = startTour;
    KBeatsVisitorTour.reset = function () {
        try {
            window.localStorage.removeItem(STORAGE_KEY);
        } catch (err) {
            // Ignore storage errors.
        }
        startTour({ manual: true });
    };
    KBeatsVisitorTour.steps = visitorTourSteps;
    window.KBeatsVisitorTour = KBeatsVisitorTour;

    document.addEventListener('DOMContentLoaded', () => {
        bindControls();
        if (!getStoredSeen() && !isInternalPath()) {
            window.setTimeout(() => startTour(), 900);
        }
    });
})();
