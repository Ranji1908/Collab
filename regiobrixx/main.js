/* Regiobrixx — Landing Page */
(function () {
  'use strict';

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---- Mobile-Navigation ---- */
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

  /* ---- Parallax ----
     Jedes [data-parallax] sitzt in einem .parallax-Rahmen und ist höher
     als dieser. Beim Scrollen wandert das Bild innerhalb des Überstands,
     gesteuert über die Custom Property --shift. Der Überstand wird aus
     dem Layout gelesen, damit die CSS-Werte frei bleiben. */
  var layers = document.querySelectorAll('[data-parallax]');

  if (layers.length && !reduced && 'IntersectionObserver' in window) {
    document.documentElement.classList.add('js-parallax');

    var active = [];
    var ticking = false;

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var i = active.indexOf(entry.target);
        if (entry.isIntersecting && i === -1) active.push(entry.target);
        else if (!entry.isIntersecting && i > -1) active.splice(i, 1);
      });
      request();
    }, { rootMargin: '15% 0px' });

    Array.prototype.forEach.call(layers, function (img) {
      if (img.parentElement) io.observe(img.parentElement);
    });

    function paint() {
      ticking = false;
      var vh = window.innerHeight;

      active.forEach(function (frame) {
        var img = frame.querySelector('[data-parallax]');
        if (!img) return;

        // Überstand oben wie unten: (Bildhöhe − Rahmenhöhe) / 2
        var slack = (img.offsetHeight - frame.clientHeight) / 2;
        if (slack <= 0) return;

        // −1 = Rahmen tritt unten ins Bild, +1 = Rahmen verlässt es oben
        var progress = 1 - 2 * ((frame.getBoundingClientRect().top + frame.clientHeight / 2) / (vh + frame.clientHeight));
        var speed = parseFloat(img.getAttribute('data-parallax')) || 0.5;
        var shift = Math.max(-slack, Math.min(slack, progress * slack * speed));

        img.style.setProperty('--shift', shift.toFixed(2) + 'px');
      });
    }

    function request() {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(paint);
    }

    window.addEventListener('scroll', request, { passive: true });
    window.addEventListener('resize', request, { passive: true });
    window.addEventListener('load', request);
    request();
  }

  /* ---- Scroll-Reveal ---- */
  var items = document.querySelectorAll('.reveal');
  if (reduced || !('IntersectionObserver' in window)) {
    Array.prototype.forEach.call(items, function (el) { el.classList.add('in'); });
  } else {
    var reveal = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry, i) {
        if (!entry.isIntersecting) return;
        entry.target.style.transitionDelay = Math.min(i * 80, 320) + 'ms';
        entry.target.classList.add('in');
        reveal.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.1 });
    Array.prototype.forEach.call(items, function (el) { reveal.observe(el); });
  }

  /* ---- Kontaktformular → vorausgefüllte Mail ---- */
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

  /* ---- Jahreszahl ---- */
  var year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();
})();
