// static/js/clover.js

document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('clover-explosion-container');
    if (!container) return;

    const count     = 80;
    const startX    = window.innerWidth  / 2;
    const startY    = window.innerHeight / 4;
    const maxBurst  = 600;

    for (let i = 0; i < count; i++) {
      const elm = document.createElement('i');
      elm.className = 'fas fa-clover clover-particle';

      const angle = Math.random() * 2 * Math.PI;
      const dist  = 200 + Math.random() * (maxBurst - 200);
      const dx    = Math.cos(angle) * dist;
      const dy    = Math.sin(angle) * dist;
      elm.style.setProperty('--dx', `${dx}px`);
      elm.style.setProperty('--dy', `${dy}px`);

      elm.style.left = `${startX}px`;
      elm.style.top  = `${startY}px`;

      container.appendChild(elm);
    }
});
