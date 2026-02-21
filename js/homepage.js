document.addEventListener('DOMContentLoaded', async () => {
  const user = await checkAuth();
  if (user?.email) {
    window.location.href = 'dashboard.html';
    return;
  }
  initScrollReveal();
});

function initScrollReveal() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      e.target.classList.toggle('revealed', e.isIntersecting);
    });
  }, { threshold: 0.15 });
  document.querySelectorAll('.how-step, .story-content, .cta-inner').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    observer.observe(el);
  });
}
