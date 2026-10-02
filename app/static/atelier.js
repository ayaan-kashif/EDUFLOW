/* Small, dependency-free interaction layer. Content remains visible without motion. */
'use strict';
const Atelier = (() => {
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const revealed = new WeakSet();
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      observer.unobserve(entry.target);
      if (reducedMotion.matches || revealed.has(entry.target)) continue;
      revealed.add(entry.target);
      entry.target.animate([
        {opacity: .35, transform: 'translateY(16px)'},
        {opacity: 1, transform: 'translateY(0)'}
      ], {duration: 600, easing: 'cubic-bezier(.22,1,.36,1)'});
    }
  }, {threshold: .08});

  function observe(root = document) {
    root.querySelectorAll('.journey>button,.coverage-hero,.readiness,.ledger-card,.source-grid>.card,.plan-sidebar>.card,.evidence-layout>.card').forEach(el => {
      if (!revealed.has(el)) observer.observe(el);
    });
  }

  function enter(name) {
    const navigationHadFocus = document.activeElement?.closest('nav');
    document.body.dataset.view = name;
    document.querySelector('.masthead').classList.remove('menu-open');
    const menu = document.getElementById('mobile-menu');
    menu?.setAttribute('aria-expanded', 'false');
    menu?.setAttribute('aria-label', 'Open navigation');
    if (menu) menu.textContent = 'Menu +';
    const surface = document.getElementById(`${name}-view`);
    surface?.classList.remove('is-entering');
    requestAnimationFrame(() => surface?.classList.add('is-entering'));
    window.scrollTo({top: 0, behavior: 'instant'});
    if (navigationHadFocus) document.getElementById('workspace')?.focus({preventScroll:true});
    observe();
    document.title = `${{overview:'Overview',sources:'Sources',plan:'Planner',evidence:'Evidence'}[name]} · EduFlow`;
  }

  const menu = document.getElementById('mobile-menu');
  menu?.addEventListener('click', () => {
    const open = document.querySelector('.masthead').classList.toggle('menu-open');
    menu.setAttribute('aria-expanded', String(open));
    menu.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    menu.textContent = open ? 'Close −' : 'Menu +';
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.querySelector('.masthead.menu-open')) {
      document.querySelector('.masthead').classList.remove('menu-open');
      menu.setAttribute('aria-expanded','false');
      menu.setAttribute('aria-label','Open navigation');
      menu.textContent='Menu +'; menu.focus();
    }
    if (document.getElementById('palette')?.open && /^[0-3]$/.test(event.key)) {
      const name=['overview','sources','plan','evidence'][Number(event.key)];
      document.querySelector(`[data-command="${name}"]`)?.click();
    }
  });
  document.getElementById('timeline-mode')?.addEventListener('click', event => {
    const agenda = document.getElementById('timeline').classList.toggle('timeline-agenda');
    event.currentTarget.setAttribute('aria-pressed', String(agenda));
    event.currentTarget.textContent = agenda ? 'Week view' : 'Agenda view';
  });

  // A bounded 12px parallax shift on the decorative illustration only.
  let frame = null;
  function scrollScene() {
    if (frame !== null || reducedMotion.matches) return;
    frame = requestAnimationFrame(() => {
      frame = null;
      if (document.body.dataset.view !== 'overview') return;
      const scene = document.querySelector('.paper-stack');
      scene?.style.setProperty('--scene-scroll', `${Math.min(12, scrollY * .035)}px`);
    });
  }
  window.addEventListener('scroll', scrollScene, {passive:true});
  reducedMotion.addEventListener('change', () => {
    if (reducedMotion.matches) {
      document.querySelector('.paper-stack')?.style.removeProperty('--scene-scroll');
      document.getAnimations().forEach(animation => animation.cancel());
    }
  });
  window.addEventListener('load', () => {
    observe();
    for (const id of ['overview-content','documents']) {
      const root = document.getElementById(id);
      if (root) new MutationObserver(() => observe(root)).observe(root,{childList:true});
    }
  }, {once:true});
  // Paint the requested surface before asynchronous data loading starts.
  const initial=['overview','sources','plan','evidence'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'overview';
  document.querySelectorAll('.surface').forEach(surface=>surface.hidden=surface.id!==`${initial}-view`);
  document.body.dataset.view=initial;
  return {enter,observe};
})();
