/**
 * Global Business Lead Intelligence System
 * Frontend Application Logic
 */

// ============================================
// STATE
// ============================================
let allBusinesses = [];
let filteredBusinesses = [];
let currentSort = { field: 'opportunity_score', order: 'desc' };
let activeFilters = {
    has_website: '',
    has_email: '',
    min_opportunity: 0,
    max_performance: 100,
    city: '',
    niche: '',
    service: '',
    high_confidence: false,
};
let isSearching = false;

// ============================================
// INITIALIZATION
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    loadExistingData();
    setupEventListeners();
    loadSuggestions();
    loadServiceOptions();
});

function setupEventListeners() {
    // Search form
    const searchForm = document.getElementById('searchForm');
    searchForm.addEventListener('submit', handleSearch);

    // Limit slider
    const limitSlider = document.getElementById('limitSlider');
    const limitValue = document.getElementById('limitValue');
    limitSlider.addEventListener('input', (e) => {
        limitValue.textContent = e.target.value;
    });

    // Filter chips
    document.querySelectorAll('.filter-chip').forEach(chip => {
        chip.addEventListener('click', () => toggleFilter(chip));
    });

    // Export buttons
    document.getElementById('exportAll').addEventListener('click', () => exportSpecialized('all'));
    document.getElementById('exportHealth').addEventListener('click', () => exportSpecialized('health'));

    // Clear data
    document.getElementById('clearData').addEventListener('click', clearData);

    // New select filters
    const cityFilter = document.getElementById('cityFilter');
    const nicheFilter = document.getElementById('nicheFilter');

    if (cityFilter) {
        cityFilter.addEventListener('change', (e) => {
            activeFilters.city = e.target.value;
            applyFilters();
        });
    }

    if (nicheFilter) {
        nicheFilter.addEventListener('change', (e) => {
            activeFilters.niche = e.target.value;
            applyFilters();
        });
    }

    // Service filter
    const serviceFilter = document.getElementById('serviceFilter');
    if (serviceFilter) {
        serviceFilter.addEventListener('change', (e) => {
            activeFilters.service = e.target.value;
            applyFilters();
        });
    }

    // Dropdown toggle
    const leadListBtn = document.getElementById('leadListBtn');
    const leadListMenu = document.getElementById('leadListMenu');

    if (leadListBtn && leadListMenu) {
        // Use a more robust toggle approach
        leadListBtn.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            const isHidden = leadListMenu.classList.contains('hidden');

            // Close other menus if any, then toggle this one
            leadListMenu.classList.toggle('hidden');
            console.log('Dropdown toggled. Now hidden:', leadListMenu.classList.contains('hidden'));
        };

        // Close dropdown when clicking outside
        window.addEventListener('click', (e) => {
            if (leadListMenu && !leadListMenu.classList.contains('hidden')) {
                if (!leadListBtn.contains(e.target) && !leadListMenu.contains(e.target)) {
                    leadListMenu.classList.add('hidden');
                }
            }
        });
    }

    // Modal close
    document.getElementById('modalClose').addEventListener('click', closeModal);
    document.getElementById('modalBackdrop').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeModal();
    });

    // Escape to close modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });
}

// ============================================
// SEARCH
// ============================================
async function handleSearch(e) {
    e.preventDefault();
    if (isSearching) return;

    const keyword = document.getElementById('keyword').value.trim();
    const city = document.getElementById('city').value.trim();
    const country = document.getElementById('country').value.trim();
    const limit = parseInt(document.getElementById('limitSlider').value);

    if (!keyword || !city || !country) {
        showToast('Please fill in all search fields', 'warning');
        return;
    }

    isSearching = true;
    updateSearchUI(true);

    const progressSection = document.getElementById('progressSection');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const progressPercent = document.getElementById('progressPercent');

    progressSection.classList.remove('hidden');
    progressBar.style.width = '0%';
    progressText.textContent = 'Initializing search...';
    progressPercent.textContent = '0%';

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword, city, country, limit }),
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        handleSSEMessage(data);
                    } catch (err) {
                        console.warn('SSE parse error:', err);
                    }
                }
            }
        }
    } catch (err) {
        console.error('Search error:', err);
        showToast('Search failed: ' + err.message, 'error');
    } finally {
        isSearching = false;
        updateSearchUI(false);
    }
}

function handleSSEMessage(data) {
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const progressPercent = document.getElementById('progressPercent');

    switch (data.type) {
        case 'status':
            progressText.textContent = data.message;
            break;

        case 'progress':
            const pct = Math.round((data.current / data.total) * 100);
            progressBar.style.width = pct + '%';
            progressText.textContent = data.message;
            progressPercent.textContent = pct + '%';

            // Refresh table every 2 businesses to show progress live
            if (data.current % 2 === 0 || data.current === 1) {
                loadExistingData();
            }
            break;

        case 'complete':
            progressBar.style.width = '100%';
            progressText.textContent = data.message;
            progressPercent.textContent = '100%';
            showToast(data.message, 'success');
            loadExistingData();
            setTimeout(() => {
                document.getElementById('progressSection').classList.add('hidden');
            }, 3000);
            break;

        case 'error':
            progressText.textContent = data.message;
            showToast(data.message, 'error');
            break;
    }
}

function updateSearchUI(searching) {
    const btn = document.getElementById('searchBtn');
    const spinner = document.getElementById('searchSpinner');
    const btnText = document.getElementById('searchBtnText');

    if (searching) {
        btn.disabled = true;
        spinner.classList.remove('hidden');
        btnText.textContent = 'Searching...';
    } else {
        btn.disabled = false;
        spinner.classList.add('hidden');
        btnText.textContent = 'Search & Analyze';
    }
}

// ============================================
// DATA LOADING
// ============================================
async function loadSuggestions() {
    try {
        const resp = await fetch('/api/suggestions');
        const data = await resp.json();

        const updateDatalist = (id, items) => {
            const dl = document.getElementById(id);
            if (!dl) return;
            dl.innerHTML = items.map(item => `<option value="${escapeHtml(item)}">`).join('');
        };

        updateDatalist('citiesList', data.cities);
        updateDatalist('countriesList', data.countries);
        updateDatalist('keywordsList', data.keywords);

        // Update Dynamic Filter Chips for City and Niche
        const cityChipsContainer = document.getElementById('cityChips');
        const nicheChipsContainer = document.getElementById('nicheChips');

        const renderDynamicChips = (container, items, filterKey) => {
            if (!container) return;
            // First chip is "All"
            let html = `<button class="filter-chip ${!activeFilters[filterKey] ? 'active' : ''}" data-dyn-filter="${filterKey}" data-val="">All</button>`;

            items.forEach(item => {
                const isActive = activeFilters[filterKey] === item;
                html += `<button class="filter-chip ${isActive ? 'active' : ''}" data-dyn-filter="${filterKey}" data-val="${escapeHtml(item)}">${escapeHtml(item)}</button>`;
            });
            container.innerHTML = html;

            // Attach listeners to these new chips
            container.querySelectorAll('.filter-chip').forEach(btn => {
                btn.addEventListener('click', () => {
                    const key = btn.getAttribute('data-dyn-filter');
                    const val = btn.getAttribute('data-val');

                    // Update state
                    activeFilters[key] = val;

                    // Update UI visually within this container only
                    container.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
                    btn.classList.add('active');

                    applyFilters();
                });
            });
        };

        renderDynamicChips(cityChipsContainer, data.cities, 'city');
        renderDynamicChips(nicheChipsContainer, data.keywords, 'niche');

    } catch (err) {
        console.warn('Failed to load suggestions:', err);
    }
}

// ============================================
// SERVICE OPTIONS LOADER
// ============================================
async function loadServiceOptions() {
    try {
        const resp = await fetch('/api/services');
        const data = await resp.json();
        const services = data.services || [];

        const serviceChipsContainer = document.getElementById('serviceChips');
        if (!serviceChipsContainer) return;

        let html = `<button class="filter-chip ${!activeFilters.service ? 'active' : ''}" data-dyn-filter="service" data-val="">All</button>`;

        services.forEach(s => {
            const isActive = activeFilters.service === s;
            html += `<button class="filter-chip ${isActive ? 'active' : ''}" data-dyn-filter="service" data-val="${escapeHtml(s)}">${escapeHtml(s)}</button>`;
        });
        serviceChipsContainer.innerHTML = html;

        serviceChipsContainer.querySelectorAll('.filter-chip').forEach(btn => {
            btn.addEventListener('click', () => {
                const val = btn.getAttribute('data-val');
                activeFilters.service = val;

                serviceChipsContainer.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');

                applyFilters();
            });
        });
    } catch (err) {
        console.warn('Failed to load services:', err);
    }
}

// ============================================
// SERVICE BADGE RENDERER
// ============================================
const SERVICE_CSS_MAP = {
    'Full-Stack Web Development': 'svc-web',
    'Software Development': 'svc-software',
    'Mobile App Development': 'svc-mobile',
    'Shopify Store Development': 'svc-shopify',
    'SEO Services': 'svc-seo',
    'Digital Marketing': 'svc-marketing',
    'UI/UX Design': 'svc-uiux',
    'Graphic & Vector Design': 'svc-graphic',
    'Photo Editing': 'svc-photo',
    'Video Editing': 'svc-video',
    'Website Maintenance & Support': 'svc-maintain',
};

function renderServiceBadge(serviceName) {
    if (!serviceName) return '<span class="text-slate-600 text-xs">—</span>';
    const cssClass = SERVICE_CSS_MAP[serviceName] || 'svc-web';
    return `<span class="service-badge ${cssClass}">${escapeHtml(serviceName)}</span>`;
}

function getConfidenceClass(score) {
    if (score >= 70) return 'high';
    if (score >= 40) return 'medium';
    return 'low';
}


async function loadExistingData() {
    try {
        const params = new URLSearchParams();
        if (activeFilters.has_website) params.set('has_website', activeFilters.has_website);
        if (activeFilters.has_email) params.set('has_email', activeFilters.has_email);
        if (activeFilters.min_opportunity > 0) params.set('min_opportunity', activeFilters.min_opportunity);
        if (activeFilters.max_performance < 100) params.set('max_performance', activeFilters.max_performance);
        params.set('sort_by', currentSort.field);
        params.set('sort_order', currentSort.order);
        params.set('limit', 500);

        const resp = await fetch('/api/businesses?' + params.toString());
        const data = await resp.json();

        allBusinesses = data.businesses || [];
        filteredBusinesses = allBusinesses;
        updateStats();
        renderTable();
    } catch (err) {
        console.error('Failed to load data:', err);
    }
}

// ============================================
// STATS
// ============================================
function updateStats() {
    const businesses = filteredBusinesses;

    // Total
    animateNumber('statTotal', businesses.length);

    // With website
    const withWebsite = businesses.filter(b => b.has_website).length;
    animateNumber('statWebsite', withWebsite);

    // With email
    const withEmail = businesses.filter(b => b.email).length;
    animateNumber('statEmail', withEmail);

    // High opportunity (score >= 60)
    const highOpp = businesses.filter(b => b.opportunity_score >= 60).length;
    animateNumber('statHighOpp', highOpp);

    // Avg performance
    const withPerf = businesses.filter(b => b.performance_score > 0);
    const avgPerf = withPerf.length > 0
        ? Math.round(withPerf.reduce((sum, b) => sum + b.performance_score, 0) / withPerf.length)
        : 0;
    animateNumber('statAvgPerf', avgPerf);

    // No website
    const noWebsite = businesses.filter(b => !b.has_website).length;
    animateNumber('statNoWebsite', noWebsite);
}

function animateNumber(elementId, target) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const start = parseInt(el.textContent) || 0;
    const duration = 500;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(start + (target - start) * eased);
        if (progress < 1) requestAnimationFrame(update);
    }

    requestAnimationFrame(update);
}

// ============================================
// TABLE RENDERING
// ============================================
function renderTable() {
    const tbody = document.getElementById('tableBody');
    const emptyState = document.getElementById('emptyState');

    if (filteredBusinesses.length === 0) {
        tbody.innerHTML = '';
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');

    // Sort
    const sorted = [...filteredBusinesses].sort((a, b) => {
        let valA = a[currentSort.field] ?? 0;
        let valB = b[currentSort.field] ?? 0;
        if (typeof valA === 'string') valA = valA.toLowerCase();
        if (typeof valB === 'string') valB = valB.toLowerCase();
        if (currentSort.order === 'asc') return valA > valB ? 1 : -1;
        return valA < valB ? 1 : -1;
    });

    tbody.innerHTML = sorted.map((biz, idx) => `
        <tr class="fade-in" style="animation-delay: ${Math.min(idx * 20, 500)}ms" onclick="openDetail('${biz.place_id}')">
            <td class="px-4 py-3 text-sm">
                <div class="font-semibold text-white truncate max-w-[200px]" title="${escapeHtml(biz.name)}">${escapeHtml(biz.name)}</div>
                <div class="text-xs text-slate-400 truncate max-w-[200px]" title="${escapeHtml(biz.address)}">${escapeHtml(biz.address || '')}</div>
            </td>
            <td class="px-4 py-3 text-sm text-slate-300">${escapeHtml(biz.phone || '—')}</td>
            <td class="px-4 py-3 text-sm">
                ${biz.website
            ? `<a href="${escapeHtml(biz.website)}" target="_blank" class="text-indigo-400 hover:text-indigo-300 truncate block max-w-[150px]" title="${escapeHtml(biz.website)}" onclick="event.stopPropagation()">
                        ${truncateUrl(biz.website)}
                       </a>`
            : '<span class="text-red-400 text-xs font-medium">No Website</span>'
        }
            </td>
            <td class="px-4 py-3 text-sm">
                ${biz.email
            ? `<a href="mailto:${escapeHtml(biz.email)}" class="text-emerald-400 hover:text-emerald-300 text-xs" onclick="event.stopPropagation()">${escapeHtml(biz.email)}</a>`
            : '<span class="text-slate-500">—</span>'
        }
            </td>
            <td class="px-4 py-3">${renderSocialIcons(biz.socials)}</td>
            <td class="px-4 py-3 text-center">${renderScoreBadge(biz.performance_score, true)}</td>
            <td class="px-4 py-3 text-center">${renderScoreBadge(biz.opportunity_score, false)}</td>
            <td class="px-4 py-3">${renderServiceBadge(biz.primary_pitch)}</td>
        </tr>
    `).join('');
}

function renderSocialIcons(socials) {
    if (!socials) return '<span class="text-slate-500 text-xs">—</span>';

    const icons = [];
    const platforms = [
        { key: 'instagram', label: 'IG', cls: 'instagram' },
        { key: 'facebook', label: 'FB', cls: 'facebook' },
        { key: 'linkedin', label: 'IN', cls: 'linkedin' },
        { key: 'twitter', label: 'X', cls: 'twitter' },
        { key: 'youtube', label: 'YT', cls: 'youtube' },
        { key: 'tiktok', label: 'TK', cls: 'tiktok' },
    ];

    for (const p of platforms) {
        if (socials[p.key]) {
            icons.push(`<a href="${escapeHtml(socials[p.key])}" target="_blank" class="social-icon ${p.cls}" title="${p.key}" onclick="event.stopPropagation()">${p.label}</a>`);
        }
    }

    return icons.length > 0
        ? `<div class="flex gap-1 flex-wrap">${icons.join('')}</div>`
        : '<span class="text-slate-500 text-xs">None</span>';
}

function renderScoreBadge(score, isPerformance) {
    const s = parseInt(score) || 0;
    if (s === 0 && isPerformance) {
        return '<span class="text-slate-500 text-xs">N/A</span>';
    }

    let cls;
    if (isPerformance) {
        cls = s >= 70 ? 'score-low' : s >= 40 ? 'score-medium' : 'score-high';
    } else {
        cls = s >= 70 ? 'score-high' : s >= 40 ? 'score-medium' : 'score-low';
    }

    return `<span class="inline-flex items-center justify-center w-10 h-7 rounded-md text-xs font-bold ${cls}">${s}</span>`;
}

// ============================================
// SORTING
// ============================================
function sortTable(field) {
    if (currentSort.field === field) {
        currentSort.order = currentSort.order === 'desc' ? 'asc' : 'desc';
    } else {
        currentSort.field = field;
        currentSort.order = 'desc';
    }

    // Update sort indicators
    document.querySelectorAll('.sort-indicator').forEach(el => el.textContent = '');
    const indicator = document.querySelector(`[data-sort="${field}"] .sort-indicator`);
    if (indicator) {
        indicator.textContent = currentSort.order === 'desc' ? ' ↓' : ' ↑';
    }

    renderTable();
}

// ============================================
// FILTERS
// ============================================
function toggleFilter(chip) {
    const filter = chip.dataset.filter;
    const value = chip.dataset.value;

    chip.classList.toggle('active');

    switch (filter) {
        case 'no_website':
            activeFilters.has_website = chip.classList.contains('active') ? 'false' : '';
            break;
        case 'has_website':
            activeFilters.has_website = chip.classList.contains('active') ? 'true' : '';
            break;
        case 'has_email':
            activeFilters.has_email = chip.classList.contains('active') ? 'true' : '';
            break;
        case 'poor_perf':
            activeFilters.max_performance = chip.classList.contains('active') ? 50 : 100;
            break;
        case 'high_opp':
            activeFilters.min_opportunity = chip.classList.contains('active') ? 60 : 0;
            break;
        case 'high_confidence':
            activeFilters.high_confidence = chip.classList.contains('active');
            break;
    }

    // Deactivate conflicting filters
    if (filter === 'no_website' && chip.classList.contains('active')) {
        const hasWebChip = document.querySelector('[data-filter="has_website"]');
        if (hasWebChip) { hasWebChip.classList.remove('active'); }
    }
    if (filter === 'has_website' && chip.classList.contains('active')) {
        const noWebChip = document.querySelector('[data-filter="no_website"]');
        if (noWebChip) { noWebChip.classList.remove('active'); }
    }

    applyFilters();
}

// ============================================
// FILTERING
// ============================================
function applyFilters() {
    filteredBusinesses = allBusinesses.filter(biz => {
        // Simple property filters (the original chips)
        if (activeFilters.no_website && biz.has_website) return false;
        if (activeFilters.has_website && !biz.has_website) return false;
        if (activeFilters.has_email && !biz.email) return false;
        if (activeFilters.poor_perf && biz.performance_score >= 50) return false;
        if (activeFilters.high_opp && biz.opportunity_score < 60) return false;

        // High confidence filter (the new chip)
        const primaryServiceRank = biz.recommended_services?.[0];
        if (activeFilters.high_confidence) {
            if (!primaryServiceRank || primaryServiceRank.confidence_score < 75) return false;
        }

        // Dynamic chips filters (City, Niche, Service)
        const cityFilterVal = activeFilters.city;
        const nicheFilterVal = activeFilters.niche;
        const serviceFilterVal = activeFilters.service;

        if (cityFilterVal && biz.city !== cityFilterVal) return false;
        if (nicheFilterVal && biz.keyword !== nicheFilterVal) return false;
        if (serviceFilterVal && biz.primary_pitch !== serviceFilterVal) return false;

        return true;
    });

    updateStats();
    renderTable();
}

// ============================================
// DETAIL MODAL
// ============================================
function openDetail(placeId) {
    const biz = allBusinesses.find(b => b.place_id === placeId);
    if (!biz) return;

    const modal = document.getElementById('modalBackdrop');
    const content = document.getElementById('modalBody');

    const health = biz.health || {};
    const socials = biz.socials || {};

    content.innerHTML = `
        <div class="space-y-6">
            <!-- Header -->
            <div>
                <h2 class="text-2xl font-bold text-white">${escapeHtml(biz.name)}</h2>
                <p class="text-slate-400 text-sm mt-1">${escapeHtml(biz.address || '')}</p>
            </div>

            <!-- Quick Info Grid -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div class="glass-card p-3 text-center">
                    <div class="text-xs text-slate-400 mb-1">Performance</div>
                    <div class="text-xl font-bold ${biz.performance_score >= 70 ? 'text-emerald-400' : biz.performance_score >= 40 ? 'text-amber-400' : 'text-red-400'}">${biz.performance_score || 'N/A'}</div>
                </div>
                <div class="glass-card p-3 text-center">
                    <div class="text-xs text-slate-400 mb-1">SEO</div>
                    <div class="text-xl font-bold ${biz.seo_score >= 70 ? 'text-emerald-400' : biz.seo_score >= 40 ? 'text-amber-400' : 'text-red-400'}">${biz.seo_score || 'N/A'}</div>
                </div>
                <div class="glass-card p-3 text-center">
                    <div class="text-xs text-slate-400 mb-1">Accessibility</div>
                    <div class="text-xl font-bold ${biz.accessibility_score >= 70 ? 'text-emerald-400' : biz.accessibility_score >= 40 ? 'text-amber-400' : 'text-red-400'}">${biz.accessibility_score || 'N/A'}</div>
                </div>
                <div class="glass-card p-3 text-center">
                    <div class="text-xs text-slate-400 mb-1">Opportunity</div>
                    <div class="text-xl font-bold ${biz.opportunity_score >= 70 ? 'text-red-400' : biz.opportunity_score >= 40 ? 'text-amber-400' : 'text-emerald-400'}">${biz.opportunity_score}</div>
                </div>
            </div>

            <!-- Contact Info -->
            <div class="glass-card p-4">
                <h3 class="text-sm font-semibold text-indigo-400 mb-3 uppercase tracking-wider">Contact</h3>
                <div class="space-y-2 text-sm">
                    <div class="flex justify-between">
                        <span class="text-slate-400">Phone</span>
                        <span class="text-white">${escapeHtml(biz.phone || 'N/A')}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">Email</span>
                        <span class="text-white">${biz.email ? `<a href="mailto:${escapeHtml(biz.email)}" class="text-emerald-400 hover:underline">${escapeHtml(biz.email)}</a>` : 'Not found'}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">Website</span>
                        <span>${biz.website ? `<a href="${escapeHtml(biz.website)}" target="_blank" class="text-indigo-400 hover:underline">${truncateUrl(biz.website)}</a>` : '<span class="text-red-400">None</span>'}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">Rating</span>
                        <span class="text-amber-400">${biz.rating ? biz.rating + ' ★ (' + biz.user_ratings_total + ')' : 'N/A'}</span>
                    </div>
                </div>
            </div>

            <!-- Social Links -->
            <div class="glass-card p-4">
                <h3 class="text-sm font-semibold text-indigo-400 mb-3 uppercase tracking-wider">Social Media</h3>
                <div class="flex flex-wrap gap-2">
                    ${renderDetailSocials(socials)}
                </div>
            </div>

            <!-- Health Analysis -->
            ${biz.has_website ? `
            <div class="glass-card p-4">
                <h3 class="text-sm font-semibold text-indigo-400 mb-3 uppercase tracking-wider">Website Health</h3>
                <div class="grid grid-cols-2 gap-2 text-sm">
                    ${healthItem('HTTPS', health.https_enabled)}
                    ${healthItem('Mobile Viewport', health.has_viewport)}
                    ${healthItem('Title Tag', health.has_title)}
                    ${healthItem('Meta Description', health.has_meta_description)}
                    ${healthItem('H1 Tag', health.has_h1)}
                    ${healthItem('Favicon', health.has_favicon)}
                    <div class="flex justify-between py-1">
                        <span class="text-slate-400">Response Time</span>
                        <span class="text-white">${health.response_time || 0}s</span>
                    </div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-400">Broken Links</span>
                        <span class="${health.broken_links_count > 0 ? 'text-red-400' : 'text-emerald-400'}">${health.broken_links_count || 0}</span>
                    </div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-400">Images with Alt</span>
                        <span class="text-white">${health.images_with_alt || 0}/${health.images_total || 0}</span>
                    </div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-400">CMS/Tech</span>
                        <span class="text-white">${escapeHtml(biz.detected_cms || 'Unknown')}</span>
                    </div>
                </div>
                ${health.tech_stack && health.tech_stack.length > 0 ? `
                <div class="mt-3 flex flex-wrap gap-1">
                    ${health.tech_stack.map(t => `<span class="px-2 py-1 rounded-md bg-slate-700/50 text-xs text-slate-300">${escapeHtml(t)}</span>`).join('')}
                </div>` : ''}
            </div>` : ''}

            <!-- Pitch Summary -->
            <div class="glass-card p-4">
                <h3 class="text-sm font-semibold text-amber-400 mb-3 uppercase tracking-wider">📊 Pitch Summary</h3>
                <pre class="text-sm text-slate-300 whitespace-pre-wrap font-sans leading-relaxed">${escapeHtml(biz.pitch_summary || 'No analysis available.')}</pre>
            </div>

            <!-- Service Opportunity Breakdown -->
            ${(() => {
            const recs = biz.recommended_services || [];
            if (recs.length === 0) return '';

            const pitchSummary = biz.service_pitch_summary || '';
            const serviceItems = recs.map(rec => {
                const cls = getConfidenceClass(rec.confidence_score);
                const badge = renderServiceBadge(rec.service);
                return `
                        <div class="service-item">
                            <div class="service-item-header">
                                ${badge}
                                <span class="text-xs font-bold text-slate-300">${rec.confidence_score}/100</span>
                            </div>
                            <div class="confidence-bar-wrap">
                                <div class="confidence-bar-fill ${cls}" style="width: ${rec.confidence_score}%"></div>
                            </div>
                            <div class="service-item-reason">${escapeHtml(rec.reason || '')}</div>
                        </div>
                    `;
            }).join('');

            return `
                <div class="glass-card p-4">
                    <h3 class="text-sm font-semibold text-indigo-400 mb-2 uppercase tracking-wider">🎯 Service Opportunities</h3>
                    ${pitchSummary ? `<p class="text-xs text-slate-400 mb-4 leading-relaxed">${escapeHtml(pitchSummary)}</p>` : ''}
                    <div class="grid grid-cols-1 gap-3">
                        ${serviceItems}
                    </div>
                </div>`;
        })()}
        </div>
    `;

    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    document.getElementById('modalBackdrop').classList.add('hidden');
    document.body.style.overflow = '';
}

function healthItem(label, value) {
    return `
        <div class="flex justify-between py-1">
            <span class="text-slate-400">${label}</span>
            <span class="${value ? 'text-emerald-400' : 'text-red-400'}">${value ? '✓' : '✗'}</span>
        </div>
    `;
}

function renderDetailSocials(socials) {
    const platforms = [
        { key: 'instagram', label: 'Instagram', cls: 'instagram' },
        { key: 'facebook', label: 'Facebook', cls: 'facebook' },
        { key: 'linkedin', label: 'LinkedIn', cls: 'linkedin' },
        { key: 'twitter', label: 'Twitter/X', cls: 'twitter' },
        { key: 'youtube', label: 'YouTube', cls: 'youtube' },
        { key: 'tiktok', label: 'TikTok', cls: 'tiktok' },
        { key: 'pinterest', label: 'Pinterest', cls: 'pinterest' },
        { key: 'threads', label: 'Threads', cls: 'threads' },
    ];

    const items = platforms.map(p => {
        if (socials[p.key]) {
            return `<a href="${escapeHtml(socials[p.key])}" target="_blank" class="social-icon ${p.cls}" title="${p.label}">${p.label.slice(0, 2).toUpperCase()}</a>`;
        }
        return `<span class="social-icon opacity-20 bg-slate-700" title="${p.label} – not found">${p.label.slice(0, 2).toUpperCase()}</span>`;
    });

    return items.join('');
}

// ============================================
// EXPORT
// ============================================
function exportSpecialized(format) {
    const params = new URLSearchParams();

    // Always include current filters
    const currentKeyword = document.getElementById('keyword').value.trim();
    const currentCity = document.getElementById('city').value.trim();
    const currentCountry = document.getElementById('country').value.trim();

    if (currentKeyword) params.set('keyword', currentKeyword);
    if (currentCity) params.set('city', currentCity);
    if (currentCountry) params.set('country', currentCountry);

    if (activeFilters.has_website) params.set('has_website', activeFilters.has_website);
    if (activeFilters.has_email) params.set('has_email', activeFilters.has_email);
    if (activeFilters.min_opportunity > 0) params.set('min_opportunity', activeFilters.min_opportunity);
    if (activeFilters.max_performance < 100) params.set('max_performance', activeFilters.max_performance);

    const url = (format === 'health' ? '/api/businesses/pdf?' : '/api/businesses/csv?') + params.toString();

    // Use a more robust download approach instead of window.location.href
    // This helps ensure the browser respects the filename header
    const filename = format === 'health'
        ? `Health_Report_${new Date().toISOString().slice(0, 10)}.pdf`
        : `${format}_leads_${new Date().toISOString().slice(0, 10)}.csv`;

    const a = document.createElement('a');
    a.href = url;
    a.download = filename; // Hint for the browser
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

function exportAll() {
    exportSpecialized('all');
}

function exportFiltered() {
    exportSpecialized('all');
}

// ============================================
// CLEAR DATA
// ============================================
async function clearData() {
    if (!confirm('Are you sure you want to delete all business data? This cannot be undone.')) return;

    try {
        const resp = await fetch('/api/businesses', { method: 'DELETE' });
        const data = await resp.json();
        showToast(`Deleted ${data.deleted} businesses`, 'success');
        allBusinesses = [];
        filteredBusinesses = [];
        updateStats();
        renderTable();
    } catch (err) {
        showToast('Failed to clear data', 'error');
    }
}

// ============================================
// UTILITIES
// ============================================
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function truncateUrl(url) {
    if (!url) return '';
    try {
        const parsed = new URL(url.startsWith('http') ? url : 'https://' + url);
        return parsed.hostname.replace('www.', '');
    } catch {
        return url.length > 30 ? url.slice(0, 30) + '...' : url;
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');

    const colors = {
        success: 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300',
        error: 'bg-red-500/20 border-red-500/50 text-red-300',
        warning: 'bg-amber-500/20 border-amber-500/50 text-amber-300',
        info: 'bg-indigo-500/20 border-indigo-500/50 text-indigo-300',
    };

    const icons = {
        success: '✓',
        error: '✗',
        warning: '⚠',
        info: 'ℹ',
    };

    toast.className = `flex items-center gap-3 px-4 py-3 rounded-xl border backdrop-blur-lg shadow-xl ${colors[type]} fade-in`;
    toast.innerHTML = `
        <span class="text-lg">${icons[type]}</span>
        <span class="text-sm font-medium">${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
