document.addEventListener('change', function (event) {
  const input = event.target.closest('input[type="file"][name="image"]');
  if (!input || !input.files || !input.files[0]) return;
  const preview = document.querySelector('[data-preview]');
  if (!preview) return;
  const image = preview.querySelector('img');
  image.src = URL.createObjectURL(input.files[0]);
  preview.classList.add('has-image');
});

document.addEventListener('click', function (event) {
  const button = event.target.closest('[data-carousel]');
  if (!button) return;
  const carousel = button.closest('.carousel');
  const track = carousel && carousel.querySelector('.carousel-track');
  if (!track) return;
  const card = track.querySelector('.product-card');
  const distance = card ? card.getBoundingClientRect().width + 18 : 280;
  track.scrollBy({ left: button.dataset.carousel === 'next' ? distance : -distance, behavior: 'smooth' });
});

(function () {
  function visitorId() {
    const key = 'perihan-gallery-visitor';
    try {
      let id = localStorage.getItem(key);
      if (!id) {
        id = crypto.randomUUID ? crypto.randomUUID() : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
          const r = Math.random() * 16 | 0;
          return (c === 'x' ? r : (r & 3 | 8)).toString(16);
        });
        localStorage.setItem(key, id);
      }
      return id;
    } catch (_) {
      return 'session-' + Math.random().toString(16).slice(2) + Date.now().toString(16);
    }
  }
  const visitor = visitorId();
  function update(code, value) {
    document.querySelectorAll('.like-button').forEach(button => {
      if (button.dataset.likeCode !== code) return;
      button.dataset.liked = value.liked ? '1' : '0';
      button.setAttribute('aria-pressed', value.liked ? 'true' : 'false');
      button.setAttribute('aria-label', `${value.count} beğeni${value.liked ? ', beğendin' : ''}`);
      const count = button.querySelector('.like-count');
      if (count) count.textContent = value.count;
    });
  }
  fetch('/api/likes?visitor=' + encodeURIComponent(visitor), { cache: 'no-store' })
    .then(response => response.ok ? response.json() : Promise.reject())
    .then(data => Object.entries(data.likes || {}).forEach(([code, value]) => update(code, value)))
    .catch(() => {});
  document.addEventListener('click', function (event) {
    const button = event.target.closest('.like-button');
    if (!button || button.disabled) return;
    event.preventDefault();
    const code = button.dataset.likeCode;
    const liked = button.dataset.liked !== '1';
    button.disabled = true;
    fetch('/api/likes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, visitor, liked })
    })
      .then(response => response.ok ? response.json() : Promise.reject())
      .then(result => update(result.code, result))
      .catch(() => {})
      .finally(() => { button.disabled = false; });
  });
})();
