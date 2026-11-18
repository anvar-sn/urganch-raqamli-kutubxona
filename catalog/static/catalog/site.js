document.addEventListener('DOMContentLoaded', () => {
  /* 1. Clear stale Service Workers & Caches so styles and pages always load fresh */
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations().then((regs) => {
      regs.forEach((r) => r.unregister());
    }).catch(() => {});
  }

  /* 2. Theme Toggle (Light / Dark Mode) - Single Unified Handler */
  const toggleTheme = (e) => {
    if (e && e.stopPropagation) e.stopPropagation();
    const root = document.documentElement;
    const isDark = root.classList.toggle('dark');
    const mode = isDark ? 'dark' : 'light';
    root.setAttribute('data-prime-theme', mode);
    try {
      localStorage.setItem('uzedu_theme', mode);
      localStorage.setItem('litsey_theme', mode);
    } catch (err) {}
  };
  window.toggleAppTheme = toggleTheme;
  document.querySelectorAll('#theme-toggle, .theme-toggle-btn').forEach((btn) => {
    btn.onclick = toggleTheme;
  });

  /* 3. Navigation & Responsive Controls */
  const libNavbar = document.getElementById('lib-navbar');
  const libMenuToggle = document.getElementById('lib-menu-toggle');
  const libNavBackdrop = document.getElementById('lib-nav-backdrop');
  const setLibMenu = (open) => {
    if (!libNavbar || !libMenuToggle) return;
    libNavbar.classList.toggle('is-menu-open', open);
    libMenuToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    libMenuToggle.setAttribute('aria-label', open ? 'Menyuni yopish' : 'Menyuni ochish');
    document.body.classList.toggle('lib-menu-locked', open);
  };
  if (libNavbar && libMenuToggle) {
    libMenuToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      setLibMenu(!libNavbar.classList.contains('is-menu-open'));
    });
    if (libNavBackdrop) libNavBackdrop.addEventListener('click', () => setLibMenu(false));
    libNavbar.querySelectorAll('.lib-nav-links a').forEach((a) => {
      a.addEventListener('click', () => setLibMenu(false));
    });
    window.addEventListener('resize', () => {
      if (window.innerWidth > 900) setLibMenu(false);
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') setLibMenu(false);
    });
  }

  /* Keng jadvallarni telefonda gorizontal suriladigan qilish */
  document.querySelectorAll('main table').forEach((tbl) => {
    const parent = tbl.parentElement;
    if (!parent) return;
    const cs = window.getComputedStyle(parent);
    if (cs.overflowX === 'auto' || cs.overflowX === 'scroll') return;
    const wrap = document.createElement('div');
    wrap.className = 'lib-table-scroll';
    parent.insertBefore(wrap, tbl);
    wrap.appendChild(tbl);
  });

  const appLayout = document.getElementById('uzedu-app-layout');
  const sidebarToggle = document.getElementById('sidebar-toggle-btn');
  const mobileClose = document.getElementById('uzedu-mobile-close');
  const backdrop = document.getElementById('uzedu-sidebar-backdrop');

  if (appLayout && sidebarToggle) {
    try {
      if (window.innerWidth > 960 && localStorage.getItem('uzedu_sidebar_collapsed') === '1') {
        appLayout.classList.add('sidebar-collapsed');
      }
    } catch (e) {}

    sidebarToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      if (window.innerWidth <= 960) {
        appLayout.classList.toggle('sidebar-mobile-open');
      } else {
        const collapsed = appLayout.classList.toggle('sidebar-collapsed');
        try {
          localStorage.setItem('uzedu_sidebar_collapsed', collapsed ? '1' : '0');
        } catch (err) {}
      }
    });

    if (mobileClose) {
      mobileClose.addEventListener('click', () => appLayout.classList.remove('sidebar-mobile-open'));
    }
    if (backdrop) {
      backdrop.addEventListener('click', () => appLayout.classList.remove('sidebar-mobile-open'));
    }
  }

  /* 3b. Topbar Language & User Profile Popovers */
  const langTrigger = document.getElementById('uzedu-lang-trigger');
  const langPopover = document.getElementById('uzedu-lang-popover');
  const userTrigger = document.getElementById('uzedu-user-trigger');
  const userPopover = document.getElementById('uzedu-user-popover');

  const closePopovers = () => {
    if (langPopover) langPopover.hidden = true;
    if (userPopover) userPopover.hidden = true;
  };

  if (langTrigger && langPopover) {
    langTrigger.addEventListener('click', (e) => {
      e.stopPropagation();
      const willOpen = langPopover.hidden;
      closePopovers();
      langPopover.hidden = !willOpen;
    });
    langPopover.querySelectorAll('[data-set-lang]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const code = btn.getAttribute('data-set-lang');
        const label = document.getElementById('uzedu-current-lang-label');
        if (label) {
          label.textContent = code === 'ru' ? 'Ру' : code === 'uz_cyrl' ? 'Ўз' : 'O‘z';
        }
        langPopover.querySelectorAll('[data-set-lang]').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        closePopovers();
      });
    });
  }

  if (userTrigger && userPopover) {
    userTrigger.addEventListener('click', (e) => {
      e.stopPropagation();
      const willOpen = userPopover.hidden;
      closePopovers();
      userPopover.hidden = !willOpen;
    });
  }

  document.addEventListener('click', () => closePopovers());
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closePopovers();
      if (appLayout) appLayout.classList.remove('sidebar-mobile-open');
    }
  });

  /* 4. Interactive 3D Hero Book Mouse Parallax */
  const heroStage = document.getElementById('hero-3d-stage');
  const heroBook = document.getElementById('hero-book-3d');
  if (heroStage && heroBook && window.matchMedia('(pointer: fine)').matches) {
    heroStage.addEventListener('mousemove', (e) => {
      const rect = heroStage.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      const rotY = -18 + x * 28;
      const rotX = 6 - y * 20;
      heroBook.style.animation = 'none';
      heroBook.style.transform = `rotateY(${rotY.toFixed(2)}deg) rotateX(${rotX.toFixed(2)}deg) translateZ(14px)`;
    });

    heroStage.addEventListener('mouseleave', () => {
      heroBook.style.transform = '';
      heroBook.style.animation = '';
    });
  }

  /* 5. Interactive 3D Tilt Cards */
  if (window.matchMedia('(pointer: fine)').matches) {
    const attachTilt = (card) => {
      if (card.dataset.tiltBound) return;
      card.dataset.tiltBound = '1';
      card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const px = (e.clientX - rect.left) / rect.width - 0.5;
        const py = (e.clientY - rect.top) / rect.height - 0.5;
        const rx = (-py * 7).toFixed(2);
        const ry = (px * 9).toFixed(2);
        card.style.transform = `perspective(1000px) translateY(-6px) rotateX(${rx}deg) rotateY(${ry}deg)`;
      });
      card.addEventListener('mouseleave', () => {
        card.style.transform = '';
      });
    };

    document.querySelectorAll('[data-tilt-card], .bookcard, .book-card').forEach(attachTilt);
    window.__attachTiltCards = () => {
      document.querySelectorAll('[data-tilt-card], .bookcard, .book-card').forEach(attachTilt);
    };
  }

  /* 6. AJAX Favorite Heart Toggle */
  document.querySelectorAll('form.fav-form').forEach((form) => {
    form.addEventListener('submit', async (e) => {
      if (!window.fetch) return;
      e.preventDefault();
      const btn = form.querySelector('button');
      const csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
      try {
        const res = await fetch(form.action, {
          method: 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrfInput ? csrfInput.value : ''
          },
          body: new FormData(form)
        });
        if (!res.ok) throw new Error('Network error');
        const data = await res.json();
        if (btn) {
          var heartSvg = data.favorite 
            ? '<svg width="15" height="15" viewBox="0 0 24 24" fill="#ef4444" stroke="#ef4444" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>'
            : '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';
          if (btn.classList.contains('heart')) {
            btn.classList.toggle('is-favorite', data.favorite);
            btn.innerHTML = heartSvg;
          } else {
            btn.innerHTML = heartSvg + (data.favorite ? ' <span>Sevimlilardan olish</span>' : ' <span>Sevimlilarga qo‘shish</span>');
          }
        }
      } catch (err) {
        form.submit();
      }
    });
  });

  /* 7. Prevent Accidental Double-Submit on Standard Forms */
  document.querySelectorAll('form').forEach((form) => {
    if (form.id === 'ai-form' || form.id === 'ziyouz-live-form' || form.classList.contains('fav-form')) return;
    form.addEventListener('submit', () => {
      const btn = form.querySelector('button[type="submit"],button:not([type])');
      if (btn && !btn.dataset.keepLabel) {
        btn.dataset.keepLabel = '1';
        btn.disabled = true;
        btn.style.opacity = '.75';
        setTimeout(() => {
          btn.disabled = false;
          btn.style.opacity = '';
        }, 4000);
      }
    });
  });

  /* 8. Live Ziyouz.com & Global E-Library Instant PDF Search on Home */
  const ziyouzForm = document.getElementById('ziyouz-live-form');
  const ziyouzInput = document.getElementById('ziyouz-live-input');
  const ziyouzGrid = document.getElementById('ziyouz-live-grid');
  const ziyouzReset = document.getElementById('ziyouz-reset-btn');
  const modal = document.getElementById('ziyouz-pdf-modal');
  const modalTitle = document.getElementById('ziyouz-modal-title');
  const modalSub = document.getElementById('ziyouz-modal-sub');
  const modalFrame = document.getElementById('ziyouz-modal-frame');
  const modalDownload = document.getElementById('ziyouz-modal-download');
  const modalClose = document.getElementById('ziyouz-modal-close');

  function openZiyouzModal(title, author, url) {
    if (!modal || !modalFrame) {
      window.open(url, '_blank', 'noopener');
      return;
    }
    modalTitle.textContent = title || 'Kitob mutolaasi';
    modalSub.textContent = author ? `${author} · Ziyouz PDF` : 'Ziyouz.com to‘g‘ridan-to‘g‘ri PDF';
    modalDownload.href = url;
    const isPdf = /\.pdf(\?|$)/i.test(url);
    modalFrame.src = isPdf
      ? `/api/pdf/?url=${encodeURIComponent(url)}`
      : url;
    modal.hidden = false;
    modal.style.display = 'flex';
  }

  function closeZiyouzModal() {
    if (!modal) return;
    modal.hidden = true;
    modal.style.display = 'none';
    if (modalFrame) modalFrame.src = 'about:blank';
  }

  if (modalClose) modalClose.addEventListener('click', closeZiyouzModal);
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeZiyouzModal();
    });
  }

  async function loadZiyouzBooks(queryText) {
    if (!ziyouzGrid) return;
    ziyouzGrid.innerHTML = `
      <div class="empty" style="grid-column:1/-1;padding:28px;">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
        <h3>Ziyouz.com PDF bazasidan qidirilmoqda…</h3>
      </div>
    `;
    try {
      const res = await fetch(`/api/ziyouz/?q=${encodeURIComponent(queryText || '')}`);
      const data = await res.json();
      const results = (data && data.results) || [];
      if (!results.length) {
        ziyouzGrid.innerHTML = `
          <div class="empty" style="grid-column:1/-1;">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <h3>«${queryText}» bo‘yicha PDF topilmadi</h3>
            <p>Boshqa kalit so‘z bilan qidirib ko‘ring (masalan: Navoiy, Qodiriy, Matematika, Tarix).</p>
          </div>
        `;
        return;
      }
      ziyouzGrid.innerHTML = results.map((item) => {
        const safeTitle = (item.title || 'Kitob').replace(/"/g, '&quot;');
        const safeAuthor = (item.author || 'Ziyouz.com').replace(/"/g, '&quot;');
        const safeCat = (item.category || item.subject || 'Ziyouz PDF').replace(/"/g, '&quot;');
        const safeUrl = item.pdf || item.url || '#';
        return `
          <article class="sensor-ziyonet-card">
            <div>
              <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px;">
                <span style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:0.6px;padding:4px 10px;border-radius:99px;background:rgba(255,255,255,0.18);color:#93c5fd;">${safeCat}</span>
                <span style="font-size:10.5px;font-weight:800;padding:3px 9px;border-radius:8px;background:#f59e0b;color:#fff;">PDF</span>
              </div>
              <h3 style="margin:8px 0 4px;font-size:16px;font-weight:800;line-height:1.35;color:#fff;">${safeTitle}</h3>
              <p style="margin:0;font-size:13px;color:rgba(226,232,240,0.85);">${safeAuthor}</p>
            </div>
            <div style="display:flex;gap:10px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.15);">
              <button type="button" class="button button-small ziyouz-read-btn" style="flex:1;min-height:42px;background:#38bdf8;color:#041a33;font-weight:800;border:0;border-radius:10px;font-size:13.5px;display:flex;align-items:center;justify-content:center;gap:6px;" data-read-url="${safeUrl}" data-read-title="${safeTitle}" data-read-author="${safeAuthor}">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
                <span>Onlayn O‘qish</span>
              </button>
              <a class="button button-small" style="min-height:42px;padding:0 14px;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.15);color:#fff;border:1px solid rgba(255,255,255,0.3);border-radius:10px;text-decoration:none;font-weight:700;" href="${safeUrl}" target="_blank" rel="noopener" download title="Yuklab olish">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              </a>
            </div>
          </article>
        `;
      }).join('');

      ziyouzGrid.querySelectorAll('[data-read-url]').forEach((el) => {
        el.addEventListener('click', (ev) => {
          ev.preventDefault();
          openZiyouzModal(
            el.getAttribute('data-read-title'),
            el.getAttribute('data-read-author'),
            el.getAttribute('data-read-url')
          );
        });
      });

      if (window.__attachTiltCards) window.__attachTiltCards();
    } catch (err) {
      ziyouzGrid.innerHTML = `
        <div class="empty" style="grid-column:1/-1;">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <h3>Ziyouz xizmati bilan bog‘lanishda xatolik</h3>
        </div>
      `;
    }
  }

  if (ziyouzForm && ziyouzGrid) {
    ziyouzForm.addEventListener('submit', (e) => {
      e.preventDefault();
      loadZiyouzBooks(ziyouzInput ? ziyouzInput.value.trim() : '');
    });
    if (ziyouzReset) {
      ziyouzReset.addEventListener('click', () => {
        if (ziyouzInput) ziyouzInput.value = '';
        loadZiyouzBooks('');
      });
    }
    loadZiyouzBooks(ziyouzInput ? ziyouzInput.value.trim() : '');
  }

  // =========================================================================
  // 3D SPATIAL CARD TILT & GLARE REFLECTION (APPLE VISION / 3D TACTILE)
  // =========================================================================
  const card3d = document.getElementById('auth3dCard');
  if (card3d && window.matchMedia && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    let bounds = null;
    let isHovering = false;
    let rafId = null;

    function updateBounds() {
      bounds = card3d.getBoundingClientRect();
    }

    card3d.addEventListener('mouseenter', () => {
      isHovering = true;
      updateBounds();
    });

    window.addEventListener('resize', () => {
      if (isHovering) updateBounds();
    });

    card3d.addEventListener('mousemove', (e) => {
      if (!bounds) updateBounds();
      const mouseX = e.clientX - bounds.left;
      const mouseY = e.clientY - bounds.top;
      const xPct = Math.max(0, Math.min(1, mouseX / bounds.width));
      const yPct = Math.max(0, Math.min(1, mouseY / bounds.height));

      // Max tilt angle: 6 degrees for subtle, elegant depth
      const rotX = (0.5 - yPct) * 8;
      const rotY = (xPct - 0.5) * 8;

      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        card3d.style.transform = `perspective(1200px) rotateX(${rotX.toFixed(2)}deg) rotateY(${rotY.toFixed(2)}deg) scale3d(1.006, 1.006, 1.006)`;
        card3d.style.setProperty('--mouse-x', `${(xPct * 100).toFixed(1)}%`);
        card3d.style.setProperty('--mouse-y', `${(yPct * 100).toFixed(1)}%`);
        card3d.style.setProperty('--glare-op', '0.14');
      });
    });

    card3d.addEventListener('mouseleave', () => {
      isHovering = false;
      if (rafId) cancelAnimationFrame(rafId);
      card3d.style.transform = 'perspective(1200px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)';
      card3d.style.setProperty('--glare-op', '0');
    });
  }
});
