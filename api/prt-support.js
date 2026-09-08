const q = document.getElementById('faqSearch');
const items = [...document.querySelectorAll('#faqList details')];
const buttons = [...document.querySelectorAll('[data-filter]')];
const noResults = document.getElementById('faqNoResults');

function filter(value, category = false) {
  const term = (value || '').toLowerCase().trim();
  let visible = 0;
  items.forEach(item => {
    const tags = (item.dataset.tags || '').toLowerCase();
    // textContent includes answers inside closed details and previously hidden
    // results, so repeated searches do not silently lose relevant answers.
    const match = !term || (category ? tags.split(/\s+/).includes(term)
      : (item.textContent + ' ' + tags).toLowerCase().includes(term));
    item.hidden = !match;
    if (match) visible += 1;
  });
  noResults.hidden = visible > 0;
}

function clearTopics() {
  buttons.forEach(button => {
    button.classList.remove('active');
    button.setAttribute('aria-pressed', 'false');
  });
}

q.addEventListener('input', event => {
  clearTopics();
  filter(event.target.value);
});
buttons.forEach(button => button.addEventListener('click', () => {
  const wasActive = button.classList.contains('active');
  clearTopics();
  q.value = '';
  if (wasActive) {
    filter('');
    return;
  }
  button.classList.add('active');
  button.setAttribute('aria-pressed', 'true');
  filter(button.dataset.filter, true);
}));
