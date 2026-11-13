(() => {
  document.querySelectorAll('.copy-code').forEach((button) => {
    button.addEventListener('click', () => {
      navigator.clipboard.writeText(button.dataset.copy || '');
    });
  });

  const form = document.querySelector('.admin-form form');
  const categoryFieldset = document.querySelector('.category-checks');
  if (!form || !categoryFieldset) return;

  const categories = Array.from(categoryFieldset.querySelectorAll('input[name="category_choice"]'));
  const warning = document.getElementById('category-selection-error');

  categories.forEach((checkbox) => {
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) {
        categories.forEach((other) => {
          if (other !== checkbox) other.checked = false;
        });
      }
      if (categories.some((item) => item.checked) && warning) warning.hidden = true;
    });
  });

  form.addEventListener('submit', (event) => {
    if (categories.some((checkbox) => checkbox.checked)) return;

    event.preventDefault();
    if (warning) {
      warning.hidden = false;
      warning.innerHTML = categories.length
        ? 'Lütfen tablo için bir kategori seç.'
        : 'Henüz kategori eklenmemiş. <a href="/atolye-yonetim-8f31/settings">Ayarlar sayfasından kategori ekle</a>.';
    }
    categoryFieldset.scrollIntoView({ behavior: 'smooth', block: 'center' });
    if (categories[0]) categories[0].focus({ preventScroll: true });
  });
})();
