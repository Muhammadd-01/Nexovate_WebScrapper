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
};
let isSearching = false;

// ============================================
// INITIALIZATION
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    loadExistingData();
    setupEventListeners();
    loadSuggestions();
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

        // Also update the select dropdowns in the filter bar
        const cityFilter = document.getElementById('cityFilter');
        const nicheFilter = document.getElementById('nicheFilter');

        if (cityFilter) {
            const current = cityFilter.value;
            cityFilter.innerHTML = '<option value="">All Cities</option>' +
                data.cities.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
            cityFilter.value = current;
        }

        if (nicheFilter) {
            const current = nicheFilter.value;
            nicheFilter.innerHTML = '<option value="">All Niches</option>' +
                data.keywords.map(n => `<option value="${escapeHtml(n)}">${escapeHtml(n)}</option>`).join('');
            nicheFilter.value = current;
        }

    } catch (err) {
        console.warn('Failed to load suggestions:', err);
    }
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

function applyFilters() {
    filteredBusinesses = allBusinesses.filter(biz => {
        if (activeFilters.has_website === 'true' && !biz.has_website) return false;
        if (activeFilters.has_website === 'false' && biz.has_website) return false;
        if (activeFilters.has_email === 'true' && !biz.email) return false;
        if (activeFilters.max_performance < 100 && biz.performance_score > activeFilters.max_performance) return false;
        if (activeFilters.min_opportunity > 0 && biz.opportunity_score < activeFilters.min_opportunity) return false;

        // City Filter
        if (activeFilters.city && biz.city !== activeFilters.city) return false;

        // Niche Filter
        if (activeFilters.niche && biz.keyword !== activeFilters.niche) return false;

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
