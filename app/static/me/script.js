document.addEventListener('DOMContentLoaded', () => {

    // --- CONFIGURATION ---
    // REMPLACER par l'URL de base de votre API
    const API_BASE_URL = 'https://votre-api.com';
    // REMPLACER par le véritable ID du contact à charger
    const CONTACT_ID = 'remplacer-par-un-vrai-uuid';

    // --- DONNÉES FICTIVES (MOCK) ---
    // À utiliser pour le développement ou si l'API n'est pas prête.
    // La structure correspond à vos modèles ORM.
    const MOCK_DATA = {
        contact: {
            contact_id: "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6",
            first_name: "Alex",
            last_name: "Martin",
            email: "alex.martin@example.com",
            phone: "+1 555 123 4567",
            status: "Active",
            lang: "fr",
        },
        subscriptions: [
            {
                subs_id: "sub-uuid-1",
                contact: "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6",
                content: { content_id: 'news-uuid', name: 'Infolettre Hebdomadaire' },
                subs_status: "Active",
                preferred_method: "Email",
            },
            {
                subs_id: "sub-uuid-2",
                contact: "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6",
                content: { content_id: 'promo-uuid', name: 'Offres Promotionnelles' },
                subs_status: "Active",
                preferred_method: "Email",
            },
            {
                subs_id: "sub-uuid-3",
                contact: "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6",
                content: { content_id: 'notif-uuid', name: 'Notifications de Sécurité' },
                subs_status: "Active",
                preferred_method: "SMS",
            }
        ]
    };
    
    // --- ÉLÉMENTS DU DOM ---
    const contactDetailsContent = document.getElementById('contact-details-content');
    const subscriptionsList = document.getElementById('subscriptions-list');
    const themeToggle = document.getElementById('theme-toggle');

    // --- LOGIQUE DE L'API ---

    /**
     * Se désabonner d'un contenu.
     * @param {string} contactId - L'ID du contact.
     * @param {string} contentId - L'ID du contenu de l'abonnement (subs_content).
     */
    async function unsubscribeFromContent(contactId, contentId) {
        // REMPLACER PAR LE VRAI APPEL API
        try {
            /*
            const response = await fetch(`${API_BASE_URL}/content-unsubscribe/${contactId}?subs_content=${contentId}`, {
                method: 'DELETE',
                headers: {
                    // Inclure les en-têtes d'authentification si nécessaire
                    // 'Authorization': 'Bearer votre_token'
                }
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "Échec de la désinscription.");
            }
            return await response.json();
            */
            // Simulation d'un appel réussi
            console.log(`SIMULATION: DELETE /content-unsubscribe/${contactId}?subs_content=${contentId}`);
            return Promise.resolve({ detail: "Désinscription réussie." });

        } catch (error) {
            console.error("Erreur de désinscription:", error);
            alert(error.message);
        }
    }

    // --- FONCTIONS D'AFFICHAGE ---

    /**
     * Affiche les détails du contact dans la page.
     * @param {object} contact - L'objet contact.
     */
    function renderContactDetails(contact) {
        if (!contact) {
            contactDetailsContent.innerHTML = `<p class="placeholder">Impossible de charger les informations du contact.</p>`;
            return;
        }
        contactDetailsContent.innerHTML = `
            <p><strong>Nom :</strong> ${contact.first_name} ${contact.last_name}</p>
            <p><strong>Email :</strong> ${contact.email || 'Non fourni'}</p>
            <p><strong>Téléphone :</strong> ${contact.phone || 'Non fourni'}</p>
            <p><strong>Statut :</strong> ${contact.status}</p>
        `;
    }

    /**
     * Affiche la liste des abonnements et les boutons d'action.
     * @param {Array<object>} subscriptions - La liste des abonnements.
     */
    function renderSubscriptions(subscriptions) {
        if (!subscriptions || subscriptions.length === 0) {
            subscriptionsList.innerHTML = `<p class="placeholder">Aucun abonnement trouvé.</p>`;
            return;
        }

        subscriptionsList.innerHTML = subscriptions.map(sub => `
            <div class="subscription-item" id="sub-${sub.subs_id}">
                <div class="subscription-details">
                    <strong>${sub.content.name}</strong>
                    <p>Méthode préférée : ${sub.preferred_method}</p>
                </div>
                <div class="subscription-actions">
                    <button class="btn btn-delete" data-contact-id="${sub.contact}" data-content-id="${sub.content.content_id}" data-subs-id="${sub.subs_id}">
                        Se désabonner
                    </button>
                </div>
            </div>
        `).join('');
        
        // Attacher les écouteurs d'événements aux nouveaux boutons
        addSubscriptionEventListeners();
    }
    
    // --- GESTIONNAIRES D'ÉVÉNEMENTS ---

    /**
     * Gère le clic sur le bouton "Se désabonner".
     */
    function addSubscriptionEventListeners() {
        subscriptionsList.querySelectorAll('.btn-delete').forEach(button => {
            button.addEventListener('click', async (e) => {
                const { contactId, contentId, subsId } = e.currentTarget.dataset;
                
                if (confirm("Êtes-vous sûr de vouloir vous désabonner de ce contenu ?")) {
                    button.textContent = '...';
                    button.disabled = true;
                    
                    await unsubscribeFromContent(contactId, contentId);
                    
                    // En cas de succès, retirer l'élément de l'interface
                    const itemToRemove = document.getElementById(`sub-${subsId}`);
                    if (itemToRemove) {
                        itemToRemove.style.opacity = '0';
                        setTimeout(() => itemToRemove.remove(), 300);
                    }
                }
            });
        });
    }

    /**
     * Gère le changement de thème (clair/sombre).
     */
    function handleThemeToggle() {
        document.body.classList.toggle('dark-theme');
        const isDarkMode = document.body.classList.contains('dark-theme');
        themeToggle.checked = isDarkMode;
        localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
    }

    /**
     * Initialise le thème au chargement de la page.
     */
    function initializeTheme() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-theme');
            themeToggle.checked = true;
        }
    }

    // --- INITIALISATION DE L'APPLICATION ---
    async function initializeApp() {
        initializeTheme();
        themeToggle.addEventListener('change', handleThemeToggle);

        // REMPLACER PAR UN VRAI APPEL API pour obtenir toutes les données
        try {
            /*
            const response = await fetch(`${API_BASE_URL}/data-for-contact/${CONTACT_ID}`);
            if (!response.ok) throw new Error("Erreur réseau");
            const data = await response.json();
            renderContactDetails(data.contact);
            renderSubscriptions(data.subscriptions);
            */

            // Utilisation des données fictives pour l'exemple
            renderContactDetails(MOCK_DATA.contact);
            renderSubscriptions(MOCK_DATA.subscriptions);

        } catch (error) {
            console.error("Erreur d'initialisation:", error);
            contactDetailsContent.innerHTML = `<p class="placeholder" style="color: var(--danger-color);">Impossible de charger les données. Veuillez réessayer plus tard.</p>`;
            subscriptionsList.innerHTML = '';
        }
    }

    // Lancer l'application
    initializeApp();
});