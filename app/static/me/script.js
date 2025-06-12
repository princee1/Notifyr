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
                  // *** SIMULATION D'APPEL API ***
                  // Dans une vraie application, vous feriez un appel fetch ici :
                  /*
                  const response = await fetch(`/api/contacts/${contactId}`, {
                      method: 'PATCH', // ou 'POST'/'PUT' selon votre API
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify(data),
                  });
  
                  if (!response.ok) {
                      throw new Error("La sauvegarde a échoué.");
                  }
                  const updatedContact = await response.json();
                  */
  
                  // Pour la démo, on simule une attente et on utilise les données du formulaire
                  await new Promise(resolve => setTimeout(resolve, 1000));
                  console.log("Données à envoyer à l'API:", data);
                  const updatedContact = data; // On utilise les données locales comme si elles venaient du serveur
  
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
    // --- Danger Zone Logic ---
    const deleteConfirmInput = document.getElementById('delete-confirm-input');
    const deleteContactBtn = document.getElementById('delete-contact-btn');
    const contactName = profileCard.dataset.contactName; // Get the full contact name from data attribute

    if (deleteConfirmInput && deleteContactBtn && contactName) {
        deleteConfirmInput.addEventListener('input', () => {
            // Enable delete button only if the input matches the contact name
            deleteContactBtn.disabled = deleteConfirmInput.value !== contactName;
        });

        deleteContactBtn.addEventListener('click', () => {
            // Show a final confirmation dialog
            const isConfirmed = confirm(`Êtes-vous sûr de vouloir supprimer définitivement le contact "${contactName}" ? Cette action est irréversible.`);

            if (isConfirmed) {
                // In a real application, you'd send a DELETE request to your backend
                const contactId = profileCard.dataset.contactId;
                console.log(`Deleting contact with ID: ${contactId}`);
                
                // Simulate API call
                deleteContactBtn.textContent = 'Suppression...';
                deleteContactBtn.disabled = true;

                setTimeout(() => {
                    alert(`Le contact "${contactName}" a été supprimé avec succès.`);
                    // Redirect or update UI after successful deletion
                    window.location.href = '/dashboard'; // Example: redirect to dashboard
                }, 1500);
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