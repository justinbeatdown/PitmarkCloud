// Pitmark PRT testimonial logo fix.
document.addEventListener('DOMContentLoaded', () => {
  document.querySelector('.tester-proof-kicker')?.remove();
  const avatar = document.querySelector('.tester-proof-avatar');
  if (avatar) {
    avatar.src = 'https://raw.githubusercontent.com/justinbeatdown/PitmarkCloud/22858f5ba55a3e2382fea38a339a49206dc12f89/api/timmyneutron020-logo.jpg';
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
