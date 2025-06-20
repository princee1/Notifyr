document.addEventListener('DOMContentLoaded', () => {

    // --- LOGIQUE D'ÉDITION DU PROFIL ---
    const profileCard = document.getElementById('profile-card');
    if (profileCard) {
        const editBtn = document.getElementById('edit-btn');
        const cancelBtn = document.getElementById('cancel-btn');
        const editProfileForm = document.getElementById('edit-profile-form');
        const viewModeDiv = profileCard.querySelector('.profile-view');
        const editModeDiv = profileCard.querySelector('.profile-edit');
        
        // Passer en mode édition
        editBtn.addEventListener('click', () => {
            viewModeDiv.style.display = 'none';
            editModeDiv.style.display = 'block';
        });

        // Annuler et revenir au mode consultation
        cancelBtn.addEventListener('click', () => {
            editModeDiv.style.display = 'none';
            viewModeDiv.style.display = 'block';
            editProfileForm.reset(); // Réinitialise les champs aux valeurs initiales du HTML
        });

        // Gérer la sauvegarde du formulaire
        editProfileForm.addEventListener('submit', async (e) => {
            e.preventDefault(); // Empêche le rechargement de la page
            
            const formData = new FormData(editProfileForm);
            const data = Object.fromEntries(formData.entries());
            const contactId = profileCard.dataset.contactId;

            const saveButton = document.getElementById('save-btn');
            saveButton.disabled = true;
            saveButton.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sauvegarde...';

            try {
                // Appel API pour mettre à jour le contact
                const response = await fetch(`/contacts/${contactId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                });

                if (!response.ok) {
                    throw new Error("La sauvegarde a échoué.");
                }
                const updatedContact = await response.json();

                // Mettre à jour les champs en mode consultation avec les nouvelles valeurs
                document.querySelectorAll('.info-group span[data-key]').forEach(span => {
                    const key = span.dataset.key;
                    if (updatedContact[key]) {
                        span.textContent = updatedContact[key];
                    }
                });

                // Revenir au mode consultation
                editModeDiv.style.display = 'none';
                viewModeDiv.style.display = 'block';

            } catch (error) {
                console.error(error);
                alert("Une erreur est survenue. Veuillez réessayer.");
            } finally {
                saveButton.disabled = false;
                saveButton.innerHTML = '<i class="fa-solid fa-save"></i> Enregistrer';
            }
        });
    }

    // --- Danger Zone Logic ---
    const deleteConfirmInput = document.getElementById('delete-confirm-input');
    const deleteContactBtn = document.getElementById('delete-contact-btn');
    const contactName = profileCard.dataset.contactName; // Get the full contact name from data attribute

    if (deleteConfirmInput && deleteContactBtn && contactName) {
        deleteConfirmInput.addEventListener('input', () => {
            // Enable delete button only if the input matches the contact name
            deleteContactBtn.disabled = deleteConfirmInput.value !== contactName;
        });

        deleteContactBtn.addEventListener('click', async () => {
            // Show a final confirmation dialog
            const isConfirmed = confirm(`Êtes-vous sûr de vouloir supprimer définitivement le contact "${contactName}" ? Cette action est irréversible.`);

            if (isConfirmed) {
                const contactId = profileCard.dataset.contactId;

                try {
                    // Appel API pour supprimer le contact
                    const response = await fetch(`/api/contacts/${contactId}`, {
                        method: 'DELETE',
                    });

                    if (!response.ok) {
                        throw new Error("La suppression a échoué.");
                    }

                    alert(`Le contact "${contactName}" a été supprimé avec succès.`);
                    // Rediriger ou mettre à jour l'interface utilisateur après la suppression
                    window.location.href = '/dashboard'; // Exemple : redirection vers le tableau de bord
                } catch (error) {
                    console.error(error);
                    alert("Une erreur est survenue. Veuillez réessayer.");
                }
            }
        });
    }

    // --- INITIALISATION ---
    const themeToggle = document.getElementById('theme-toggle');
    const docElement = document.documentElement;

    function applyTheme(theme) {
        docElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        themeToggle.checked = (theme === 'dark');
    }

    function handleThemeToggle() {
        const currentTheme = localStorage.getItem('theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        applyTheme(newTheme);
    }

    function initializeTheme() {
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        const initialTheme = savedTheme || (prefersDark ? 'dark' : 'light');
        applyTheme(initialTheme);

        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (!localStorage.getItem('theme')) {
                applyTheme(e.matches ? 'dark' : 'light');
            }
        });
    }

    initializeTheme();
    themeToggle.addEventListener('change', handleThemeToggle);

    console.log("Page initialisée. Le rendu des données a été fait côté serveur.");
});