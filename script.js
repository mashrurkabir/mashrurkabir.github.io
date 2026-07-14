/* ==========================================================================
   MASHRURKABIR.COM — script.js
   Vanilla JS, no dependencies, no build step.

   Contents
     1. Config  ← the hero background toggle lives here
     2. Sticky header
     3. Mobile navigation
     4. Scroll-reveal animations
     5. Hero background (video or starfield)
     6. Starfield renderer
     7. Footer year
     8. Contact form (Formspree)
   ========================================================================== */

'use strict';

/* --------------------------------------------------------------------------
   1. CONFIG
   -------------------------------------------------------------------------- */

/**
 * HERO BACKGROUND TOGGLE — the one line to change.
 *
 *   'starfield' → animated canvas starfield (works today, no assets needed)
 *   'video'     → looping background video from assets/hero.mp4
 *                 (drop your file into /assets first — see README.md)
 */
const HERO_BACKGROUND = 'starfield'; // TODO: set to 'video' once assets/hero.mp4 exists

const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* --------------------------------------------------------------------------
   2. Sticky header — transparent over the hero, solid once scrolled
   -------------------------------------------------------------------------- */
(function initHeader() {
  const header = document.querySelector('[data-header]');
  if (!header) return;

  const update = () => {
    header.classList.toggle('is-scrolled', window.scrollY > 24);
  };

  update();
  window.addEventListener('scroll', update, { passive: true });
})();

/* --------------------------------------------------------------------------
   3. Mobile navigation
   -------------------------------------------------------------------------- */
(function initNav() {
  const toggle = document.querySelector('[data-nav-toggle]');
  const nav = document.getElementById('site-nav');
  if (!toggle || !nav) return;

  const close = () => {
    document.body.classList.remove('nav-open');
    toggle.setAttribute('aria-expanded', 'false');
  };

  toggle.addEventListener('click', () => {
    const open = document.body.classList.toggle('nav-open');
    toggle.setAttribute('aria-expanded', String(open));
  });

  // Close on link click, Escape, or resizing back to desktop
  nav.addEventListener('click', (e) => {
    if (e.target.closest('a')) close();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.body.classList.contains('nav-open')) {
      close();
      toggle.focus();
    }
  });

  window.addEventListener('resize', () => {
    if (window.innerWidth > 860) close();
  });
})();

/* --------------------------------------------------------------------------
   4. Scroll-reveal — adds .is-visible to .reveal elements as they enter view
   -------------------------------------------------------------------------- */
(function initReveal() {
  const els = document.querySelectorAll('.reveal');
  if (!els.length) return;

  // Reduced motion or no IO support → just show everything
  if (REDUCED_MOTION || !('IntersectionObserver' in window)) {
    els.forEach((el) => el.classList.add('is-visible'));
    return;
  }

  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: '0px 0px -8% 0px' }
  );

  els.forEach((el) => io.observe(el));
})();

/* --------------------------------------------------------------------------
   5. Hero background — picks video or starfield based on HERO_BACKGROUND
   -------------------------------------------------------------------------- */
(function initHeroBackground() {
  const heroBg = document.querySelector('[data-hero-bg]');
  if (!heroBg) return; // interior pages have no hero

  if (HERO_BACKGROUND === 'video') {
    initHeroVideo(heroBg);
  } else {
    initStarfield(heroBg);
  }
})();

/**
 * Activates the <video> element. Sources are stored in data-src so the
 * browser never downloads video bytes while starfield mode is selected.
 * Every failure path (autoplay blocked, missing file, reduced motion)
 * falls back to the static poster painted by .hero-bg in CSS.
 */
function initHeroVideo(heroBg) {
  const video = heroBg.querySelector('[data-hero-video]');
  if (!video) return;

  // Respect reduced motion: leave the static poster, skip autoplay entirely
  if (REDUCED_MOTION) return;

  video.querySelectorAll('source[data-src]').forEach((source) => {
    source.src = source.dataset.src;
    source.removeAttribute('data-src');
  });

  // If no playable file exists yet, hide the element so the poster shows
  video.addEventListener('error', () => { video.hidden = true; }, true);

  video.hidden = false;
  video.muted = true; // belt-and-suspenders for mobile autoplay policies
  video.load();

  const attempt = video.play();
  if (attempt && typeof attempt.catch === 'function') {
    attempt.catch(() => { video.hidden = true; });
  }
}

/* --------------------------------------------------------------------------
   6. Starfield — lightweight canvas particle field with slow upward drift
   -------------------------------------------------------------------------- */
function initStarfield(heroBg) {
  const canvas = heroBg.querySelector('[data-starfield]');
  if (!canvas) return;

  /* Tuning knobs — TODO: adjust to taste */
  const CONFIG = {
    density: 1 / 9000,   // stars per px² of hero area
    maxStars: 340,       // hard cap for very large screens
    minSpeed: 3,         // px per second (upward drift — a slow ascent)
    maxSpeed: 9,
    accentRatio: 0.14,   // fraction of stars tinted steel blue
    starColor: '235, 240, 245',
    accentColor: '143, 198, 223',
    bgTop: '#0c0f14',    // canvas paints its own backdrop each frame
    bgBottom: '#0a0a0a',
  };

  const ctx = canvas.getContext('2d');
  let stars = [];
  let width = 0;
  let height = 0;
  let rafId = null;
  let lastTime = 0;
  let inView = true;

  canvas.hidden = false;

  function makeStar(randomY) {
    const accent = Math.random() < CONFIG.accentRatio;
    return {
      x: Math.random() * width,
      y: randomY ? Math.random() * height : height + 2,
      radius: 0.4 + Math.random() * 1.1,
      speed: CONFIG.minSpeed + Math.random() * (CONFIG.maxSpeed - CONFIG.minSpeed),
      baseAlpha: 0.25 + Math.random() * 0.65,
      twinkleSpeed: 0.4 + Math.random() * 1.1, // rad/s
      twinklePhase: Math.random() * Math.PI * 2,
      color: accent ? CONFIG.accentColor : CONFIG.starColor,
    };
  }

  function resize() {
    const rect = heroBg.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = rect.width;
    height = rect.height;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const count = Math.min(Math.round(width * height * CONFIG.density), CONFIG.maxStars);
    stars = Array.from({ length: count }, () => makeStar(true));
  }

  function paintBackdrop() {
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, CONFIG.bgTop);
    gradient.addColorStop(1, CONFIG.bgBottom);
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);
  }

  function drawStars(timeSeconds, animate) {
    paintBackdrop();
    for (const star of stars) {
      const twinkle = animate
        ? 0.65 + 0.35 * Math.sin(star.twinkleSpeed * timeSeconds + star.twinklePhase)
        : 1;
      ctx.beginPath();
      ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(' + star.color + ', ' + (star.baseAlpha * twinkle).toFixed(3) + ')';
      ctx.fill();
    }
  }

  function frame(now) {
    rafId = null;
    const dt = Math.min((now - lastTime) / 1000, 0.05); // clamp tab-switch jumps
    lastTime = now;

    for (const star of stars) {
      star.y -= star.speed * dt;
      if (star.y < -2) {
        Object.assign(star, makeStar(false));
      }
    }

    drawStars(now / 1000, true);
    schedule();
  }

  function schedule() {
    if (rafId === null && inView && !document.hidden) {
      rafId = requestAnimationFrame(frame);
    }
  }

  function pause() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  resize();

  // Reduced motion → render one static frame, no animation loop
  if (REDUCED_MOTION) {
    drawStars(0, false);
    window.addEventListener('resize', () => {
      resize();
      drawStars(0, false);
    });
    return;
  }

  lastTime = performance.now();
  schedule();

  // Only animate while the hero is on screen and the tab is visible
  if ('IntersectionObserver' in window) {
    new IntersectionObserver((entries) => {
      inView = entries[0].isIntersecting;
      if (inView) {
        lastTime = performance.now();
        schedule();
      } else {
        pause();
      }
    }).observe(heroBg);
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      pause();
    } else {
      lastTime = performance.now();
      schedule();
    }
  });

  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(resize, 150);
  });
}

/* --------------------------------------------------------------------------
   7. Footer year
   -------------------------------------------------------------------------- */
document.querySelectorAll('[data-year]').forEach((el) => {
  el.textContent = new Date().getFullYear();
});

/* --------------------------------------------------------------------------
   8. Contact form — progressive enhancement over a plain Formspree POST.
      Without JS the form still submits normally; with JS we stay on-page
      and show inline status. Warns if the endpoint hasn't been set yet.
   -------------------------------------------------------------------------- */
(function initContactForm() {
  const form = document.querySelector('[data-contact-form]');
  if (!form) return;

  const status = form.querySelector('[data-form-status]');
  const setStatus = (message, kind) => {
    if (!status) return;
    status.textContent = message;
    status.classList.remove('is-success', 'is-error');
    if (kind) status.classList.add(kind);
  };

  form.addEventListener('submit', async (event) => {
    // Guard: endpoint not configured yet (see README → Formspree)
    if (form.action.includes('YOUR_FORM_ID')) {
      event.preventDefault();
      setStatus(
        'This form is not connected yet — add your Formspree endpoint in contact.html (see README).',
        'is-error'
      );
      return;
    }

    event.preventDefault();
    setStatus('Sending…');

    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { Accept: 'application/json' },
      });

      if (response.ok) {
        form.reset();
        setStatus('Message sent. I read everything and reply to most of it.', 'is-success');
      } else {
        const data = await response.json().catch(() => null);
        const detail =
          data && data.errors ? data.errors.map((err) => err.message).join(', ') : '';
        setStatus(
          detail || 'Something went wrong. Email me directly instead — the address is on this page.',
          'is-error'
        );
      }
    } catch (err) {
      setStatus('Network error. Email me directly instead — the address is on this page.', 'is-error');
    }
  });
})();
