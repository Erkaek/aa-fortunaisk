// static/js/sparkle.js

document.addEventListener('DOMContentLoaded', () => {
  const title = document.querySelector('.lottery-title');
  if (!title) return;

  // Génère une étincelle toutes les 300ms
  setInterval(() => {
    const sparkle = document.createElement('span');
    sparkle.className = 'sparkle';
    const x = Math.random() * title.clientWidth;
    const y = Math.random() * title.clientHeight;
    sparkle.style.left = `${x}px`;
    sparkle.style.top  = `${y}px`;
    title.appendChild(sparkle);
    sparkle.addEventListener('animationend', () => sparkle.remove());
  }, 300);
});
