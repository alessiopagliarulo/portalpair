document.addEventListener('DOMContentLoaded', async () => {
  const user = await checkAuth();
  if (user?.email) {
    window.location.href = 'dashboard.html';
  }
});
