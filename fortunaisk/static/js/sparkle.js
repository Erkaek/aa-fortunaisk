// fortunaisk/static/js/sparkle.js
document.addEventListener('DOMContentLoaded', () => {
    console.log("Sparkle.js loaded");
    const title = document.querySelector('.lottery-title');
    console.log("Looking for .lottery-title, found:", title);
    if (!title) return;

    // Conteneur pour les animations
    const container = document.createElement('div');
    container.style.position = 'absolute';
    container.style.top = '-80px';  // Plus d'espace au-dessus
    container.style.left = '-50px'; // Plus d'espace sur les côtés
    container.style.width = 'calc(100% + 100px)';
    container.style.height = 'calc(100% + 200px)'; // Beaucoup d'espace en bas pour la chute
    container.style.pointerEvents = 'none';
    container.style.overflow = 'hidden';
    container.style.zIndex = '999';
    title.style.position = 'relative';
    title.appendChild(container);

    // Jetons et pièces
    const coinTypes = [
        { char: '🪙', color: '#FFD700', size: '24px' }, // Pièce d'or
        { char: '💰', color: '#FFD700', size: '28px' }, // Sac d'argent
        { char: '💸', color: '#85bb65', size: '30px' }, // Argent avec ailes
        { char: '💵', color: '#85bb65', size: '26px' }  // Billet
    ];

    function createCoin() {
        const type = coinTypes[Math.floor(Math.random() * coinTypes.length)];
        const coin = document.createElement('div');

        coin.innerText = type.char;
        coin.style.position = 'absolute';
        coin.style.fontSize = type.size;
        coin.style.textShadow = `0 0 10px ${type.color}`;
        coin.style.filter = 'drop-shadow(0 0 2px rgba(255,215,0,0.7))';

        // Position initiale (en haut, position X aléatoire)
        const startX = Math.random() * container.offsetWidth;
        coin.style.left = `${startX}px`;
        coin.style.top = '0px';

        // Rotation initiale aléatoire
        const rotation = Math.random() * 360;
        coin.style.transform = `rotate(${rotation}deg)`;

        container.appendChild(coin);

        // Animation de chute avec rebonds
        const duration = 3000 + Math.random() * 2000; // 3-5 secondes
        const finalY = container.offsetHeight - 20;

        // Animation de chute
        coin.animate([
            { top: '0px', transform: `rotate(${rotation}deg)` },
            { top: `${finalY * 0.5}px`, transform: `rotate(${rotation + 180}deg)`, offset: 0.5 },
            { top: `${finalY * 0.7}px`, transform: `rotate(${rotation + 270}deg)`, offset: 0.7 },
            { top: `${finalY}px`, transform: `rotate(${rotation + 360}deg)` }
        ], {
            duration: duration,
            easing: 'cubic-bezier(.17,.67,.83,.67)',
            iterations: 1
        }).onfinish = () => coin.remove();
    }

    // Démarrer avec quelques pièces
    for (let i = 0; i < 5; i++) {
        setTimeout(() => createCoin(), i * 300);
    }

    // Créer des pièces périodiquement
    setInterval(() => {
        const count = 1 + Math.floor(Math.random() * 2);
        for (let i = 0; i < count; i++) {
            setTimeout(() => createCoin(), i * 200);
        }
    }, 2000);
});
