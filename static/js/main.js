// Nav toggle for mobile
const navToggle = document.getElementById('navToggle');
const navLinks = document.getElementById('navLinks');
const navbarEl = document.querySelector('.navbar');

if (navToggle && navLinks) {
  navToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    navLinks.classList.toggle('open');
  });

  // Close when clicking a link
  navLinks.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => navLinks.classList.remove('open'));
  });
}

// Close when clicking outside
document.addEventListener('click', (e) => {
  if (!navLinks || !navLinks.classList.contains('open')) return;
  const clickedInside = navbarEl && navbarEl.contains(e.target);
  if (!clickedInside) navLinks.classList.remove('open');
});

// Admin sidebar: toggle backdrop & close on backdrop click
const adminSidebar = document.getElementById('adminSidebar');
const adminBackdrop = document.querySelector('.admin-backdrop');

if (adminSidebar && adminBackdrop) {
  const syncBackdrop = () => {
    adminBackdrop.classList.toggle('open', adminSidebar.classList.contains('open'));
  };

  // Initial state
  syncBackdrop();

  // Observe class changes
  const obs = new MutationObserver(syncBackdrop);
  obs.observe(adminSidebar, { attributes: true, attributeFilter: ['class'] });

  adminBackdrop.addEventListener('click', () => {
    adminSidebar.classList.remove('open');
  });

}

// Auto-dismiss flash messages
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => el.remove(), 5000);
});


// Active nav link highlight
const currentPath = window.location.pathname;
document.querySelectorAll('.nav-links a').forEach(a => {
  if (a.getAttribute('href') === currentPath) a.classList.add('active');
});
