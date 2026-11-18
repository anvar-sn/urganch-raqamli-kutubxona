(async function () {
  const cfg = window.readerConfig;
  if (!cfg) return;

  const container = document.getElementById('reader-container');
  const stage = document.getElementById('pdf-stage');
  const stack = document.getElementById('pdf-pages-stack');
  const loading = document.getElementById('pdf-loading');
  const errorBox = document.getElementById('pdf-error');
  const pageInput = document.getElementById('page-number');
  const pageTotal = document.getElementById('page-total');
  const pageLabel = document.getElementById('page-label');
  const bar = document.getElementById('reader-progress-bar');
  const topFill = document.getElementById('reader-progress-fill');
  const statusEl = document.getElementById('save-status');
  const zoomLabel = document.getElementById('zoom-label');
  const fullscreenBtn = document.getElementById('fullscreen-btn');
  const prevBtn = document.getElementById('prev-page');
  const nextBtn = document.getElementById('next-page');

  /* 1. Contrast Theme Selector (Standard, Sepia, Night) */
  const contrastBtns = document.querySelectorAll('.contrast-btn');
  function applyContrast(mode) {
    const mapped = mode === 'contrast' ? 'high-contrast' : mode;
    if (container) container.setAttribute('data-reader-theme', mapped);
    if (stage) stage.setAttribute('data-reader-theme', mapped);
    contrastBtns.forEach((btn) => {
      btn.classList.toggle('active', btn.getAttribute('data-contrast') === mode);
    });
    try {
      localStorage.setItem('litsey_reader_contrast', mode);
    } catch (e) {}
  }

  try {
    const savedContrast = localStorage.getItem('litsey_reader_contrast');
    if (savedContrast) applyContrast(savedContrast);
  } catch (e) {}

  contrastBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      applyContrast(btn.getAttribute('data-contrast') || 'standard');
    });
  });

  /* 2. Fullscreen Toggle */
  if (fullscreenBtn && container) {
    fullscreenBtn.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        container.requestFullscreen().catch(() => {});
      } else {
        document.exitFullscreen().catch(() => {});
      }
    });
  }

  /* 3. Continuous Vertical Multi-Page PDF.js Renderer */
  let pdf = null;
  let page = Math.max(1, Number(cfg.startPage) || 1);
  let scale = 1;
  let baseWidth = 600;
  let baseHeight = 840;
  let baseAspect = 1.4;
  let slotWidth = 760;
  let saveTimer = null;
  let observer = null;
  let renderGeneration = 0;
  const slots = [];
  const activeRenders = new Set();

  const csrf = () => {
    const m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return m ? decodeURIComponent(m[1]) : cfg.csrf;
  };

  function updateUiPage(num) {
    if (!pdf) return;
    page = Math.max(1, Math.min(pdf.numPages, num));
    if (document.activeElement !== pageInput) {
      pageInput.value = page;
    }
    pageLabel.textContent = `Sahifa ${page} / ${pdf.numPages}`;
    pageTotal.textContent = '/ ' + pdf.numPages;
    const pct = Math.min(100, Math.round((page * 100) / pdf.numPages));
    if (bar) bar.style.width = pct + '%';
    if (topFill) topFill.style.width = pct + '%';
    if (prevBtn) prevBtn.disabled = page <= 1;
    if (nextBtn) nextBtn.disabled = page >= pdf.numPages;
    if (zoomLabel) zoomLabel.textContent = Math.round(scale * 100) + '%';
  }

  async function saveProgress() {
    if (!pdf) return;
    if (statusEl) statusEl.textContent = 'Saqlanmoqda…';
    try {
      const r = await fetch(cfg.saveUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf()
        },
        body: JSON.stringify({ page, total: pdf.numPages })
      });
      if (!r.ok) throw new Error('save failed');
      const d = await r.json();
      if (bar) bar.style.width = d.percent + '%';
      if (topFill) topFill.style.width = d.percent + '%';
      if (statusEl) statusEl.textContent = '✓ Saqlandi';
    } catch (e) {
      if (statusEl) statusEl.textContent = 'Saqlashda uzilish';
    }
  }

  function scheduleSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveProgress, 600);
  }

  function computeSlotWidth() {
    const avail = (stage ? stage.clientWidth : 900) - 44;
    const fitBase = Math.max(280, Math.min(avail, 880));
    return Math.round(fitBase * scale);
  }

  async function renderSlot(slot, gen) {
    const num = Number(slot.dataset.page);
    if (!pdf || slot.dataset.rendered === String(gen) || activeRenders.has(num)) return;
    activeRenders.add(num);
    try {
      const p = await pdf.getPage(num);
      if (gen !== renderGeneration) return;
      const vp1 = p.getViewport({ scale: 1 });
      const targetScale = slotWidth / vp1.width;
      const v = p.getViewport({ scale: targetScale });
      const dpr = Math.min(window.devicePixelRatio || 1, 2);

      slot.style.width = Math.floor(v.width) + 'px';
      slot.style.height = Math.floor(v.height) + 'px';

      let canvas = slot.querySelector('canvas');
      if (!canvas) {
        canvas = document.createElement('canvas');
        slot.innerHTML = '';
        slot.appendChild(canvas);
        const badge = document.createElement('span');
        badge.className = 'pdf-page-badge';
        badge.textContent = num;
        slot.appendChild(badge);
      }

      canvas.width = Math.floor(v.width * dpr);
      canvas.height = Math.floor(v.height * dpr);
      const ctx = canvas.getContext('2d');

      await p.render({
        canvasContext: ctx,
        viewport: v,
        transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null
      }).promise;

      if (gen === renderGeneration) {
        slot.dataset.rendered = String(gen);
        if (loading && !loading.hidden) loading.hidden = true;
      }
    } catch (e) {
      console.error('Page render error', num, e);
    } finally {
      activeRenders.delete(num);
    }
  }

  function cleanupDistantSlots(centerPage) {
    for (let i = 0; i < slots.length; i++) {
      const num = i + 1;
      if (Math.abs(num - centerPage) > 16 && slots[i].dataset.rendered) {
        slots[i].dataset.rendered = '';
        slots[i].innerHTML = `<span class="pdf-page-stub">Sahifa ${num}</span><span class="pdf-page-badge">${num}</span>`;
      }
    }
  }

  function detectVisiblePage() {
    if (!stage || !slots.length) return;
    const viewMid = stage.scrollTop + stage.clientHeight * 0.35;
    let bestPage = page;
    for (let i = 0; i < slots.length; i++) {
      const s = slots[i];
      const top = s.offsetTop;
      const bottom = top + s.offsetHeight;
      if (bottom >= viewMid) {
        bestPage = i + 1;
        break;
      }
      bestPage = i + 1;
    }
    if (bestPage !== page) {
      updateUiPage(bestPage);
      scheduleSave();
      cleanupDistantSlots(bestPage);
    }
  }

  function scrollToPage(num, smooth = true) {
    if (!pdf || !slots.length) return;
    const target = Math.max(1, Math.min(pdf.numPages, num));
    const slot = slots[target - 1];
    if (slot && stage) {
      stage.scrollTo({
        top: Math.max(0, slot.offsetTop - 12),
        behavior: smooth ? 'smooth' : 'auto'
      });
      updateUiPage(target);
      renderSlot(slot, renderGeneration);
      if (slots[target]) renderSlot(slots[target], renderGeneration);
      scheduleSave();
    }
  }

  function setupObserver() {
    if (observer) observer.disconnect();
    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            renderSlot(entry.target, renderGeneration);
          }
        });
      },
      { root: stage, rootMargin: '700px 0px' }
    );
    slots.forEach((s) => observer.observe(s));
  }

  function rebuildZoom() {
    if (!pdf || !stage) return;
    const prevScrollRatio = stage.scrollHeight > 0 ? stage.scrollTop / stage.scrollHeight : 0;
    renderGeneration++;
    activeRenders.clear();
    slotWidth = computeSlotWidth();
    const estH = Math.round(slotWidth * baseAspect);
    slots.forEach((s, idx) => {
      s.dataset.rendered = '';
      s.style.width = slotWidth + 'px';
      s.style.height = estH + 'px';
      const num = idx + 1;
      s.innerHTML = `<span class="pdf-page-stub">Sahifa ${num}</span><span class="pdf-page-badge">${num}</span>`;
    });
    if (zoomLabel) zoomLabel.textContent = Math.round(scale * 100) + '%';
    setupObserver();
    stage.scrollTop = Math.round(prevScrollRatio * stage.scrollHeight);
    detectVisiblePage();
    // Immediately render around current page
    for (let offset = -1; offset <= 2; offset++) {
      const idx = page - 1 + offset;
      if (slots[idx]) renderSlot(slots[idx], renderGeneration);
    }
  }

  /* 4. Initialize Document */
  try {
    if (!window.pdfjsLib) throw new Error('PDF.js yuklanmadi');
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    pdf = await pdfjsLib.getDocument({ url: cfg.pdfUrl }).promise;
    page = Math.max(1, Math.min(page, pdf.numPages));

    const firstPage = await pdf.getPage(1);
    const vp1 = firstPage.getViewport({ scale: 1 });
    baseWidth = vp1.width || 600;
    baseHeight = vp1.height || 840;
    baseAspect = baseHeight / baseWidth;
    slotWidth = computeSlotWidth();
    const estH = Math.round(slotWidth * baseAspect);

    stack.innerHTML = '';
    for (let i = 1; i <= pdf.numPages; i++) {
      const slot = document.createElement('div');
      slot.className = 'pdf-page-slot';
      slot.dataset.page = String(i);
      slot.style.width = slotWidth + 'px';
      slot.style.height = estH + 'px';
      slot.innerHTML = `<span class="pdf-page-stub">Sahifa ${i}</span><span class="pdf-page-badge">${i}</span>`;
      stack.appendChild(slot);
      slots.push(slot);
    }

    updateUiPage(page);
    if (page > 1) {
      scrollToPage(page, false);
    }
    setupObserver();
    await renderSlot(slots[page - 1], renderGeneration);
    if (slots[page]) renderSlot(slots[page], renderGeneration);
    if (loading) loading.hidden = true;
    saveProgress();
  } catch (e) {
    console.error(e);
    if (loading) loading.hidden = true;
    if (errorBox) errorBox.hidden = false;
    if (stage) stage.hidden = true;
  }

  /* 5. Continuous Scroll Listener (No jarring per-page wheel hijacking) */
  let scrollRaf = null;
  if (stage) {
    stage.addEventListener('scroll', () => {
      if (scrollRaf) return;
      scrollRaf = requestAnimationFrame(() => {
        scrollRaf = null;
        detectVisiblePage();
      });
    }, { passive: true });
  }

  /* 6. Toolbar & Keyboard Controls */
  if (prevBtn) prevBtn.addEventListener('click', () => { if (pdf && page > 1) scrollToPage(page - 1); });
  if (nextBtn) nextBtn.addEventListener('click', () => { if (pdf && page < pdf.numPages) scrollToPage(page + 1); });
  if (pageInput) {
    pageInput.addEventListener('change', () => {
      if (pdf) {
        const n = Math.max(1, Math.min(pdf.numPages, Number(pageInput.value) || 1));
        scrollToPage(n);
      }
    });
  }
  const zoomInBtn = document.getElementById('zoom-in');
  const zoomOutBtn = document.getElementById('zoom-out');
  if (zoomInBtn) {
    zoomInBtn.addEventListener('click', () => {
      if (pdf && scale < 2.2) {
        scale = Math.min(2.2, +(scale + 0.15).toFixed(2));
        rebuildZoom();
      }
    });
  }
  if (zoomOutBtn) {
    zoomOutBtn.addEventListener('click', () => {
      if (pdf && scale > 0.5) {
        scale = Math.max(0.5, +(scale - 0.15).toFixed(2));
        rebuildZoom();
      }
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
    if (e.key === 'ArrowLeft' && pdf && page > 1) {
      e.preventDefault();
      scrollToPage(page - 1);
    } else if (e.key === 'ArrowRight' && pdf && page < pdf.numPages) {
      e.preventDefault();
      scrollToPage(page + 1);
    } else if ((e.key === '+' || e.key === '=') && pdf && scale < 2.2) {
      scale = Math.min(2.2, +(scale + 0.15).toFixed(2));
      rebuildZoom();
    } else if (e.key === '-' && pdf && scale > 0.5) {
      scale = Math.max(0.5, +(scale - 0.15).toFixed(2));
      rebuildZoom();
    }
  });
})();
