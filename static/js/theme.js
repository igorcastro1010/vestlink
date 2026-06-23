// Theme management for VestLink (Forced dark mode)
document.addEventListener("DOMContentLoaded", () => {
    // Read theme preference (always dark)
    const getTheme = () => "dark";
    
    // Set theme attribute on root element
    const setTheme = (theme) => {
        document.documentElement.setAttribute("data-theme", "dark");
        localStorage.setItem("theme", "dark");
        document.querySelectorAll(".dark-mode-toggle").forEach(toggle => {
            toggle.style.display = "none";
        });
    };

    // Apply active theme to root
    setTheme(getTheme());

    // Setup toggle event listener (noop since toggles are hidden)
    const setupToggles = () => {
        const toggles = document.querySelectorAll(".dark-mode-toggle");
        toggles.forEach(toggle => {
            toggle.style.display = "none";
            // Avoid duplicate listeners if script runs multiple times
            if (toggle.dataset.themeListenerSetup) return;
            toggle.dataset.themeListenerSetup = "true";

            toggle.addEventListener("click", () => {
                setTheme("dark");
            });
        });
    };

    // Mapeamento de cores para círculos de visualização no storefront
    const colorMap = {
        "preto": "#18181b",
        "branco": "#ffffff",
        "vermelho": "#ef4444",
        "azul": "#3b82f6",
        "verde": "#10b981",
        "rosa": "#ec4899",
        "cinza": "#6b7280",
        "bege": "#f5f5dc",
        "jeans": "#4f759c"
    };

    // Injeta dinamicamente pequenos círculos de cores nos seletores do storefront
    const setupColorOptions = () => {
        document.querySelectorAll(".color-option").forEach(btn => {
            if (btn.dataset.colorBadgeSetup) return;
            btn.dataset.colorBadgeSetup = "true";

            const text = btn.textContent.trim().toLowerCase();
            const colorHex = colorMap[text];
            if (colorHex) {
                const circle = document.createElement("span");
                circle.style.cssText = `
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    background-color: ${colorHex};
                    border: 1px solid ${text === 'branco' ? '#d1d5db' : 'transparent'};
                    margin-right: 6px;
                    vertical-align: middle;
                    flex-shrink: 0;
                    transition: transform 0.15s ease;
                `;
                btn.prepend(circle);
                btn.style.display = "inline-flex";
                btn.style.alignItems = "center";
                btn.style.justifyContent = "center";
            }
        });
    };

    setupToggles();
    setupColorOptions();

    // Re-bind toggles e aplica a injeção de cores se novos componentes carregarem dinamicamente (ajax/paginação)
    const observer = new MutationObserver(() => {
        setupToggles();
        setupColorOptions();
    });
    observer.observe(document.body, { childList: true, subtree: true });
});
