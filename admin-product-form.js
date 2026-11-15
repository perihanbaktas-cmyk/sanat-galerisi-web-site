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

const whatsappAccountPicker = document.querySelector('#whatsapp-account-picker');
const whatsappUrlField = document.querySelector('input[name="whatsapp_url"]');
if (whatsappAccountPicker && whatsappUrlField) {
  whatsappAccountPicker.addEventListener('change', () => {
    const selectedUrl = whatsappAccountPicker.selectedOptions[0]?.dataset.url;
    whatsappUrlField.value = selectedUrl || '';
  });
  whatsappUrlField.addEventListener('input', () => {
    const selectedUrl = whatsappAccountPicker.selectedOptions[0]?.dataset.url;
    if (whatsappAccountPicker.value && whatsappUrlField.value !== selectedUrl) {
      whatsappAccountPicker.value = '';
    }
  });
}
