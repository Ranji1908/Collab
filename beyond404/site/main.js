// Progressive enhancement: draw chart lines as they come into view.
(function () {
  var root = document.documentElement;
  var header = document.querySelector('.top');
  var onScroll = function () { header.classList.toggle('is-scrolled', window.scrollY > 8); };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) return;

  root.classList.add('js');
  var items = document.querySelectorAll('.draw, .fade');
  items.forEach(function (el) {
    if (el.getTotalLength) el.style.setProperty('--len', Math.ceil(el.getTotalLength()));
  });
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add('is-drawn'); io.unobserve(e.target); }
    });
  }, { threshold: 0.2 });
  items.forEach(function (el) { io.observe(el); });
})();
