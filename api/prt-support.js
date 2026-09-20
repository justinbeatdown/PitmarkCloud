const q = document.getElementById('faqSearch');
const items = [...document.querySelectorAll('#faqList details')];
const buttons = [...document.querySelectorAll('[data-filter]')];
const quickFilters = [...document.querySelectorAll('[data-support-filter]')];
const noResults = document.getElementById('faqNoResults');
const count = document.getElementById('faqCount');

function setCount(visible) {
  if (count) count.textContent = visible === 1 ? '1 answer available' : `${visible} answers available`;
}

function filter(value, category = false) {
  const term = (value || '').toLowerCase().trim();
  let visible = 0;
  items.forEach(item => {
    const tags = (item.dataset.tags || '').toLowerCase();
    const match = !term || (category
      ? tags.split(/\s+/).includes(term)
      : (item.textContent + ' ' + tags).toLowerCase().includes(term));
    item.hidden = !match;
    if (match) visible += 1;
  });
  if (noResults) noResults.hidden = visible > 0;
  setCount(visible);
}

function clearTopics() {
  buttons.forEach(button => {
    button.classList.remove('active');
    button.setAttribute('aria-pressed', 'false');
  });
}

function activateTopic(value) {
  clearTopics();
  if (q) q.value = '';
  const button = buttons.find(item => item.dataset.filter === value);
  if (button) {
    button.classList.add('active');
    button.setAttribute('aria-pressed', 'true');
  }
  filter(value, true);
}

if (q) q.addEventListener('input', event => {
  clearTopics();
  filter(event.target.value);
});

buttons.forEach(button => button.addEventListener('click', () => {
  const wasActive = button.classList.contains('active');
  clearTopics();
  if (q) q.value = '';
  if (wasActive) {
    filter('');
    return;
  }
  button.classList.add('active');
  button.setAttribute('aria-pressed', 'true');
  filter(button.dataset.filter, true);
}));

quickFilters.forEach(link => link.addEventListener('click', () => {
  const value = link.dataset.supportFilter;
  if (value) activateTopic(value);
}));

setCount(items.length);
