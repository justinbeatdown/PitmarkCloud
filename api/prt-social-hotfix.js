// Pitmark PRT testimonial logo fix.
document.addEventListener('DOMContentLoaded', () => {
  document.querySelector('.tester-proof-kicker')?.remove();
  const avatar = document.querySelector('.tester-proof-avatar');
  if (avatar) {
    avatar.src = '/prt-timmy-logo.jpg?v=1';
    avatar.alt = 'TimmyNeutron020 logo';
    avatar.style.width = '64px';
    avatar.style.height = '64px';
    avatar.style.borderRadius = '8px';
    avatar.style.objectFit = 'contain';
    avatar.style.background = '#080808';
    avatar.style.padding = '4px';
    avatar.style.border = '1px solid #2f3434';
    avatar.style.boxSizing = 'border-box';
  }
});
