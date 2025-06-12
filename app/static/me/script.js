document.addEventListener('DOMContentLoaded', () => {

    const themeToggle = document.getElementById('theme-toggle');
    const docElement = document.documentElement;

    /**
     * Applique le thème (clair ou sombre).
     * @param {string} theme - Le thème à appliquer ('light' ou 'dark').
     */
    function applyTheme(theme) {
        docElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        themeToggle.checked = (theme === 'dark');
    }

    /**
     * Gère le clic sur l'interrupteur de thème.
     */
    function handleThemeToggle() {
        const currentTheme = localStorage.getItem('theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        applyTheme(newTheme);
    }

    /**
     * Initialise le thème au chargement de la page en se basant sur les préférences
     * de l'utilisateur ou les paramètres du système.
     */
    function initializeTheme() {
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        // Priorité : thème sauvegardé > préférence système > thème par défaut (clair)
        const initialTheme = savedTheme || (prefersDark ? 'dark' : 'light');
        applyTheme(initialTheme);
        
        // Écoute les changements de préférence système
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (!localStorage.getItem('theme')) { // Ne change que si l'utilisateur n'a pas fait de choix explicite
                applyTheme(e.matches ? 'dark' : 'light');
            }
        });
    }

    // --- INITIALISATION ---
    
    initializeTheme();
    themeToggle.addEventListener('change', handleThemeToggle);

    console.log("Page initialisée. Le rendu des données a été fait côté serveur.");

    // NOTE : Si vous ajoutez des boutons pour des actions (ex: modifier un statut),
    // vous ajouteriez les écouteurs d'événements et les fonctions d'appel API ici.
    // Exemple :
    // document.getElementById('mon-bouton-action').addEventListener('click', async () => {
    //     const contactId = '{{ contact.contact_id }}'; // L'ID serait injecté par Jinja
    //     // await maFonctionApi(contactId, ...);
    //     // alert('Action réussie !');
    // });
});