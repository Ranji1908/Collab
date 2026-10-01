/* Regiobrixx — Landing Page interactions */
(function () {
  'use strict';

  /* ---- Mobile navigation ---- */
  var burger = document.getElementById('burger');
  var nav = document.getElementById('nav');

  function closeNav() {
    nav.classList.remove('open');
    burger.setAttribute('aria-expanded', 'false');
    burger.setAttribute('aria-label', 'Menü öffnen');
  }

  if (burger && nav) {
    burger.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      burger.setAttribute('aria-expanded', String(open));
      burger.setAttribute('aria-label', open ? 'Menü schließen' : 'Menü öffnen');
    });
    nav.addEventListener('click', function (e) {
      if (e.target.closest('a')) closeNav();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && nav.classList.contains('open')) {
        closeNav();
        burger.focus();
      }
    });
  }

  /* ---- Scroll reveal ---- */
  var items = document.querySelectorAll('.reveal');
  if (!('IntersectionObserver' in window)) {
    items.forEach(function (el) { el.classList.add('in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry, i) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        el.style.transitionDelay = Math.min(i * 70, 280) + 'ms';
        el.classList.add('in');
        io.unobserve(el);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.1 });
    items.forEach(function (el) { io.observe(el); });
  }

  /* ---- Contact form → prefilled mail ---- */
  var form = document.getElementById('form');
  var hint = document.getElementById('form-hint');
  var hintDefault = hint ? hint.innerHTML : '';

  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();

      if (!form.checkValidity()) {
        hint.textContent = 'Bitte füllen Sie Organisation, Name und eine gültige E-Mail-Adresse aus.';
        hint.classList.add('is-error');
        var invalid = form.querySelector(':invalid');
        if (invalid) invalid.focus();
        return;
      }

      hint.classList.remove('is-error');
      hint.innerHTML = hintDefault;

      var data = new FormData(form);
      var get = function (k) { return (data.get(k) || '').toString().trim(); };

      var subject = 'Regiobrixx-Anfrage: ' + (get('org') || 'Destination');
      var body = [
        'Hallo Regiobrixx-Team,',
        '',
        'wir interessieren uns für ein individuelles Klemmbaustein-Set.',
        '',
        'Destination / Organisation: ' + get('org'),
        'Ansprechpartner:in: ' + get('name'),
        'E-Mail: ' + get('email'),
        'Interessantes Paket: ' + get('paket'),
        '',
        'Wahrzeichen / Idee:',
        get('idee') || '—',
        '',
        'Viele Grüße'
      ].join('\n');

      window.location.href = 'mailto:hallo@regiobrixx.de?subject=' +
        encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
    });
  }

  /* ---- Footer year ---- */
  var year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();
})();
