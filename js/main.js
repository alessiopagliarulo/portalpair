// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    const href = this.getAttribute('href');
    if (href === '#') return;
    e.preventDefault();
    const target = document.querySelector(href);
    if (target) target.scrollIntoView({ behavior: 'smooth' });
  });
});
// Splash screen timer
window.addEventListener("load", () => {
  const splash = document.getElementById("splash-screen");
  const login = document.getElementById("login-screen");

  setTimeout(() => {
    splash.style.opacity = "0";
    setTimeout(() => {
      splash.style.display = "none";
      login.classList.remove("hidden");
    }, 1000); // wait for fade out

  }, 2000); // 2 seconds
});
