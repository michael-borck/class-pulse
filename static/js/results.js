/* Shared result renderers for Present mode and the per-question Results page.
 *
 * Each function takes the question's config (options) and the stats payload
 * from classpulse/stats.py and returns either an HTML string or a Chart.js
 * config. Keeping them in one place means both pages draw the same picture,
 * and the matrix/scatter frames match what the audience tapped
 * (templates/audience_view.html): Y up the left, X along the bottom.
 *
 * Every piece of presenter- or audience-supplied text goes through esc().
 */
(function () {
    'use strict';

    function esc(s) {
        const d = document.createElement('div');
        d.textContent = s == null ? '' : String(s);
        return d.innerHTML;
    }

    const asObject = (v) => (v && typeof v === 'object' && !Array.isArray(v)) ? v : {};
    const asArray = (v) => Array.isArray(v) ? v : [];

    const BAR_TYPES = ['multiple_choice', 'multi_select', 'numeric', 'multiple_choice_other', 'slider'];
    const INDIGO = 'rgba(79,70,229,0.75)';

    // Bar charts: choice-style types, numeric/slider histograms, rating,
    // ranking scores and points allocations.
    function barConfig(type, s, opts) {
        const results = (s && s.results) || {};
        if (type === 'ranking' || type === 'points') {
            // Horizontal, so long option names stay readable. Ranking plots the
            // score (longer = ranked higher) already sorted best-first; points
            // plots the average allocation per person.
            const labels = (s && s.options) || Object.keys(results);
            const values = type === 'ranking' ? ((s && s.scores) || {}) : results;
            return { type: 'bar',
                data: { labels, datasets: [{ label: type === 'ranking' ? 'Score' : 'Average points',
                                             data: labels.map(l => values[l] || 0), backgroundColor: INDIGO }] },
                options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                    scales: { x: { beginAtZero: true } },
                    plugins: { legend: { display: false },
                        tooltip: { callbacks: { label: (ctx) => type === 'ranking'
                            ? ` average position ${results[ctx.label] || '–'}`
                            : ` ${ctx.parsed.x} points on average` } } } } };
        }
        if (BAR_TYPES.includes(type)) {
            const labels = (s && s.options) || Object.keys(results);
            return { type: 'bar',
                data: { labels, datasets: [{ label: 'Votes', data: labels.map(l => results[l] || 0),
                                             backgroundColor: INDIGO }] },
                options: { responsive: true, maintainAspectRatio: false,
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                    plugins: { legend: { display: false } } } };
        }
        const max = (s && s.max_rating) || 5;
        const labels = Array.from({ length: max }, (_, i) => `${i + 1} ⭐`);
        return { type: 'bar',
            data: { labels, datasets: [{ label: 'Ratings', data: labels.map((_, i) => results[String(i + 1)] || 0),
                                         backgroundColor: 'rgba(249,115,22,0.75)' }] },
            options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
                plugins: { legend: { display: false } } } };
    }

    function usesBarChart(type) {
        return BAR_TYPES.includes(type) || ['rating', 'ranking', 'points'].includes(type);
    }

    // Short lines above the chart for types that need them.
    function captionHTML(type, s) {
        let out = '';
        if (type === 'numeric' && s && s.average != null) {
            out += `<p class="text-sm font-medium text-gray-700 mb-2">Average: ${esc(s.average)}</p>`;
        }
        if (type === 'slider') {
            const cfg = (s && s.config) || {};
            if (s && s.average != null) {
                out += `<p class="text-sm font-medium text-gray-700 mb-1">Average: ${esc(s.average)} · Median: ${esc(s.median)}</p>`;
            }
            if (cfg.low_label || cfg.high_label) {
                out += `<div class="flex justify-between text-xs text-gray-500 mb-1"><span>← ${esc(cfg.low_label || cfg.min)}</span><span>${esc(cfg.high_label || cfg.max)} →</span></div>`;
            }
        }
        if (type === 'ranking') out += '<p class="text-xs text-gray-500 mb-1">Longer bar = ranked higher</p>';
        if (type === 'points' && s) {
            out += `<p class="text-xs text-gray-500 mb-1">Average points per person, out of ${esc(s.total || 100)}</p>`;
        }
        return out;
    }

    // The typed answers behind a poll's "Other" bar.
    function otherAnswersHTML(s) {
        const items = asArray(s && s.other_answers);
        if (!items.length) return '';
        return `<p class="text-xs font-semibold text-gray-500 mt-2 mb-1">"Other" answers (${items.length})</p>
            <div class="space-y-1">${items.map(a => `<div class="bg-white border rounded px-2 py-1 text-sm text-gray-800">${esc(a.text)}</div>`).join('')}</div>`;
    }

    // Pin on image: every pin drawn over the image in an SVG whose viewBox is
    // the image's own pixel size, so pins land on the right spot however the
    // image is scaled or letterboxed. Overlapping translucent pins darken
    // where the room agrees.
    const imageSizes = {};
    function renderImagePin(el, config, s) {
        if (!el) return;
        const url = asObject(config).image_url;
        if (!url) { el.innerHTML = '<p class="text-gray-400 italic text-center mt-4">No image configured.</p>'; return; }
        const size = imageSizes[url];
        if (!size) {
            const img = new Image();
            img.onload = () => { imageSizes[url] = [img.naturalWidth || 1000, img.naturalHeight || 750]; renderImagePin(el, config, s); };
            img.onerror = () => { el.innerHTML = '<p class="text-red-500 text-center mt-4">Image failed to load.</p>'; };
            img.src = url;
            return;
        }
        const [w, h] = size;
        const r = Math.max(w, h) * 0.018;
        const pins = asArray(s && s.points).map(p =>
            `<circle cx="${(p.x / 100 * w).toFixed(1)}" cy="${(p.y / 100 * h).toFixed(1)}" r="${r.toFixed(1)}" fill="rgba(220,38,38,0.4)" stroke="white" stroke-width="${(r / 5).toFixed(1)}"/>`).join('');
        el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet" class="w-full h-full" role="img" aria-label="${asArray(s && s.points).length} pins on the image">
            <image href="${esc(url)}" width="${w}" height="${h}"/>${pins}</svg>`;
    }

    // Image choice: each image with its label, count, share and a bar; the
    // leader is outlined. Renders at zero votes too, so the room sees the options.
    function imageChoiceHTML(options, s) {
        const opts = asArray(options);
        if (!opts.length) return '<p class="text-gray-400 italic text-center mt-4">No images configured.</p>';
        const results = (s && s.results) || {};
        const counts = opts.map(o => results[o.label] || 0);
        const total = counts.reduce((a, b) => a + b, 0);
        const maxCount = Math.max(0, ...counts);
        const cols = Math.min(opts.length, 3);
        const cards = opts.map((o, i) => {
            const count = counts[i];
            const pct = total ? Math.round(count / total * 100) : 0;
            const leading = count > 0 && count === maxCount;
            return `<div class="rounded-lg border ${leading ? 'border-indigo-500 ring-2 ring-indigo-300' : 'border-gray-200'} bg-white overflow-hidden flex flex-col">
                <div class="bg-gray-100 flex items-center justify-center" style="aspect-ratio:4/3;">
                    <img src="${esc(o.url)}" alt="${esc(o.label)}" class="w-full h-full object-contain" loading="lazy">
                </div>
                <div class="p-3">
                    <div class="flex items-baseline justify-between gap-2">
                        <span class="font-semibold text-gray-800 truncate">${esc(o.label)}</span>
                        <span class="text-sm text-gray-600 shrink-0">${count} (${pct}%)</span>
                    </div>
                    <div class="mt-2 h-2 rounded-full bg-gray-200 overflow-hidden">
                        <div class="h-full ${leading ? 'bg-indigo-600' : 'bg-indigo-400'}" style="width:${pct}%"></div>
                    </div>
                </div>
            </div>`;
        }).join('');
        return `<div class="grid gap-4 content-start" style="grid-template-columns:repeat(${cols},minmax(0,1fr));">${cards}</div>`;
    }

    // Emoji: every option stays visible at zero votes; vote share scales the
    // glyph (2rem up to 5rem for the leader) so the mood reads from the back row.
    function emojiHTML(options, s) {
        const opts = asArray(options);
        if (!opts.length) return '<p class="text-gray-400 italic text-center mt-4">No emojis configured.</p>';
        const results = (s && s.results) || {};
        const counts = opts.map(o => results[o] || 0);
        const total = counts.reduce((a, b) => a + b, 0);
        const maxCount = Math.max(0, ...counts);
        const chips = opts.map((o, i) => {
            const n = counts[i];
            const pct = total ? Math.round(n / total * 100) : 0;
            const leading = n > 0 && n === maxCount;
            const size = 2 + (maxCount ? (n / maxCount) * 3 : 0);
            return `<div class="flex flex-col items-center gap-1 ${leading ? '' : 'opacity-80'}">
                <span style="font-size:${size.toFixed(2)}rem; line-height:1.1;">${esc(o)}</span>
                <span class="text-sm font-semibold ${leading ? 'text-indigo-700' : 'text-gray-500'}">${n} (${pct}%)</span>
            </div>`;
        }).join('');
        return `<div class="flex flex-wrap items-center justify-center gap-x-8 gap-y-6 p-4">${chips}</div>`;
    }

    // Matrix heatmap in the same chart frame the audience tapped. Row 1 is
    // stored as the top row (the high end of Y).
    function matrixHTML(config, s) {
        const cfg = asObject(config);
        const cols = parseInt(cfg.cols, 10) || 2;
        const rows = parseInt(cfg.rows, 10) || 2;
        const results = (s && s.results) || {};
        const maxCount = Math.max(0, ...Object.values(results));
        const hasX = !!(cfg.x_label || cfg.x_low || cfg.x_high);
        const hasY = !!(cfg.y_label || cfg.y_low || cfg.y_high);

        let cells = '';
        for (let r = 1; r <= rows; r++) {
            for (let c = 1; c <= cols; c++) {
                const n = results[`${c},${r}`] || 0;
                const strength = maxCount ? n / maxCount : 0;
                const bg = n ? `background-color: rgba(79,70,229,${(0.15 + 0.85 * strength).toFixed(3)});` : '';
                const txt = strength > 0.45 ? 'text-white' : 'text-gray-700';
                cells += `<div class="rounded-md border border-gray-200 ${n ? '' : 'bg-gray-50'} flex items-center justify-center" style="${bg}">
                    <span class="text-xl md:text-3xl font-bold ${txt}">${n || ''}</span>
                </div>`;
            }
        }
        const yAxis = hasY ? `
            <div class="flex flex-col justify-between items-center text-xs md:text-sm text-gray-500 py-1 min-w-[1.5rem] max-w-[6rem] break-words">
                <span class="text-center">${esc(cfg.y_high || '')}</span>
                <span class="font-semibold text-gray-700 whitespace-nowrap" style="writing-mode: vertical-rl; transform: rotate(180deg);">${esc(cfg.y_label || '')}</span>
                <span class="text-center">${esc(cfg.y_low || '')}</span>
            </div>` : '';
        const xAxis = hasX ? `${hasY ? '<div></div>' : ''}
            <div class="flex justify-between items-baseline text-xs md:text-sm text-gray-500 gap-2">
                <span>${esc(cfg.x_low || '')}</span>
                <span class="font-semibold text-gray-700 text-center">${esc(cfg.x_label || '')}</span>
                <span>${esc(cfg.x_high || '')}</span>
            </div>` : '';
        // min-height (not height) plus a 1fr row: the cells stretch to fill a
        // tall host but never shrink below their minimum, so in a small grid
        // card the host scrolls instead of the cells sliding over the X axis.
        return `<div class="grid gap-x-2 gap-y-1"
                     style="min-height: 100%; grid-template-columns: ${hasY ? 'auto ' : ''}minmax(0, 1fr); grid-template-rows: 1fr${hasX ? ' auto' : ''};">
            ${yAxis}
            <div class="grid gap-1.5" style="grid-template-columns: repeat(${cols}, minmax(0, 1fr)); grid-template-rows: repeat(${rows}, minmax(2.5rem, 1fr));">${cells}</div>
            ${xAxis}
        </div>`;
    }

    // Scatter: one dot per respondent on a 0–100 plane; the optional colour
    // and size dimensions are read off each point.
    const SCATTER_RADII = { sm: 4, md: 7, lg: 11 };
    // With end labels, an axis shows them at 0 and 100 and hides the numbers
    // in between; quadrants darken the 50 gridline.
    function scatterAxis(cfg, axis) {
        const low = cfg[axis + '_low'], high = cfg[axis + '_high'];
        const out = { min: 0, max: 100, title: { display: !!cfg[axis + '_label'], text: cfg[axis + '_label'] || '' } };
        if (low || high) {
            out.ticks = { stepSize: 50, autoSkip: false, maxRotation: 0,
                callback: (v) => v === 0 ? (low || '0') : v === 100 ? (high || '100') : '' };
        }
        if (cfg.quadrants) {
            out.grid = { color: (ctx) => ctx.tick && ctx.tick.value === 50 ? 'rgba(100,116,139,0.6)' : 'rgba(0,0,0,0.08)',
                         lineWidth: (ctx) => ctx.tick && ctx.tick.value === 50 ? 2 : 1 };
            if (!out.ticks) out.ticks = { stepSize: 10 };
        }
        return out;
    }

    function scatterConfig(config, s, colors) {
        const cfg = asObject(config);
        const palette = asObject(colors);
        const radius = (ctx) => SCATTER_RADII[(ctx.raw && ctx.raw.s) || 'md'] || 7;
        return { type: 'scatter',
            data: { datasets: [{
                label: 'Responses',
                data: (s && s.points) || [],
                pointRadius: radius,
                pointHoverRadius: (ctx) => radius(ctx) + 2,
                pointBackgroundColor: (ctx) => palette[(ctx.raw && ctx.raw.c)] || 'rgba(79,70,229,0.75)',
            }] },
            options: { responsive: true, maintainAspectRatio: false,
                scales: { x: scatterAxis(cfg, 'x'), y: scatterAxis(cfg, 'y') },
                plugins: { legend: { display: false },
                    tooltip: { callbacks: { label: (ctx) => {
                        const p = ctx.raw || {};
                        const extras = [p.c, p.s].filter(Boolean).join(', ');
                        return ` (${Math.round(p.x)}, ${Math.round(p.y)})${extras ? ', ' + extras : ''}`;
                    } } } } } };
    }

    // Short answer: a readable list, optionally with an Answers/Cloud toggle.
    // `prefix` namespaces the element ids so several can share a page.
    function shortAnswerHTML(prefix, hClass, withToggle) {
        const p = esc(prefix);
        const toggle = withToggle ? `
            <div class="mb-2 inline-flex rounded-md border border-gray-300 overflow-hidden text-xs" role="group" aria-label="Show answers as">
                <button type="button" data-sa-toggle="${p}" data-sa-view="list" aria-pressed="true" class="px-3 py-1 bg-indigo-600 text-white">📝 Answers</button>
                <button type="button" data-sa-toggle="${p}" data-sa-view="cloud" aria-pressed="false" class="px-3 py-1 bg-white text-gray-700">☁ Cloud</button>
            </div>` : '';
        return `${toggle}
            <div id="${p}-list" class="w-full ${hClass} overflow-y-auto border rounded-md bg-gray-50 p-3 space-y-2"></div>
            <div id="${p}-cloud" class="hidden w-full ${hClass} border rounded-md bg-gray-50"></div>`;
    }

    function populateShortAnswer(prefix, s) {
        const items = asArray(s && s.results);
        const list = document.getElementById(prefix + '-list');
        if (list) {
            list.innerHTML = items.length
                ? items.map(a => `<div class="bg-white border rounded px-3 py-2 text-sm text-gray-800">${esc(a && a.text != null ? a.text : a)}</div>`).join('')
                : '<p class="text-sm text-gray-400 italic">No answers yet.</p>';
        }
        const cloud = document.getElementById(prefix + '-cloud');
        if (cloud) {
            cloud._words = asArray(s && s.cloud);
            // jQCloud lays out against the element's size, which is zero while
            // hidden; the toggle handler draws it when it's shown instead.
            if (!cloud.classList.contains('hidden')) window.initWordCloud(cloud.id, cloud._words);
        }
    }

    // One delegated handler for every Answers/Cloud toggle on the page.
    document.addEventListener('click', (e) => {
        const btn = e.target.closest && e.target.closest('[data-sa-toggle]');
        if (!btn) return;
        const prefix = btn.dataset.saToggle;
        const view = btn.dataset.saView;
        const list = document.getElementById(prefix + '-list');
        const cloud = document.getElementById(prefix + '-cloud');
        if (list) list.classList.toggle('hidden', view !== 'list');
        if (cloud) {
            cloud.classList.toggle('hidden', view !== 'cloud');
            if (view === 'cloud') window.initWordCloud(cloud.id, cloud._words || []);
        }
        document.querySelectorAll(`[data-sa-toggle="${CSS.escape(prefix)}"]`).forEach(x => {
            const on = x.dataset.saView === view;
            x.setAttribute('aria-pressed', on ? 'true' : 'false');
            x.classList.toggle('bg-indigo-600', on); x.classList.toggle('text-white', on);
            x.classList.toggle('bg-white', !on); x.classList.toggle('text-gray-700', !on);
        });
    });

    window.CPResults = {
        esc, usesBarChart, barConfig, captionHTML, imageChoiceHTML, emojiHTML,
        matrixHTML, scatterConfig, shortAnswerHTML, populateShortAnswer,
        otherAnswersHTML, renderImagePin,
    };
})();
