document.querySelectorAll('.copy-code').forEach((button) => {
  button.addEventListener('click', () => {
    navigator.clipboard.writeText(button.dataset.copy || '');
  });
});

const categoryInputs = document.querySelectorAll('.category-checks input[name="category_choice"]');
categoryInputs.forEach((checkbox) => {
  checkbox.addEventListener('change', () => {
    if (!checkbox.checked) return;
    categoryInputs.forEach((other) => {
      if (other !== checkbox) other.checked = false;
    });
  });
});
