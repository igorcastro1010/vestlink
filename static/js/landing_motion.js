document.addEventListener("DOMContentLoaded", () => {
    const header = document.querySelector(".lp-header");
    const menuToggle = document.querySelector(".lp-menu-toggle");
    const navigation = document.querySelector("#lp-navigation");

    if (header && menuToggle && navigation) {
        const closeMenu = () => {
            header.classList.remove("is-menu-open");
            menuToggle.setAttribute("aria-expanded", "false");
            menuToggle.setAttribute("aria-label", "Abrir menu");
        };

        menuToggle.addEventListener("click", () => {
            const willOpen = !header.classList.contains("is-menu-open");
            header.classList.toggle("is-menu-open", willOpen);
            menuToggle.setAttribute("aria-expanded", String(willOpen));
            menuToggle.setAttribute("aria-label", willOpen ? "Fechar menu" : "Abrir menu");
        });

        navigation.querySelectorAll("a").forEach((link) => {
            link.addEventListener("click", closeMenu);
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") closeMenu();
        });

        window.addEventListener("resize", () => {
            if (window.innerWidth > 760) closeMenu();
        });
    }

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (reduceMotion.matches) return;

    document.documentElement.classList.add("motion-enhanced");

    const progress = document.querySelector(".lp-scroll-progress");
    const updateProgress = () => {
        if (!progress) return;
        const scrollable = document.documentElement.scrollHeight - window.innerHeight;
        const value = scrollable > 0 ? Math.min(window.scrollY / scrollable, 1) : 0;
        progress.style.transform = `scaleX(${value})`;
    };

    updateProgress();
    window.addEventListener("scroll", updateProgress, { passive: true });
    window.addEventListener("resize", updateProgress);

    const revealGroups = document.querySelectorAll(
        ".lp-trust-row, .lp-section, .lp-cta-strip, .lp-final"
    );

    revealGroups.forEach((group) => {
        group.classList.add("lp-reveal");
        const items = group.querySelectorAll(
            ".lp-target-grid > article, .lp-card-grid > article, .lp-feature-grid > article, " +
            ".lp-proof-grid > article, .lp-demo-flow > article, .lp-comparison__table > div, " +
            ".lp-offer-points > span, .lp-faq > details, .lp-steps > li, .lp-trust-row > article"
        );

        items.forEach((item, index) => {
            item.classList.add("lp-reveal-item");
            item.style.setProperty("--reveal-order", String(index));
        });
    });

    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
            });
        },
        { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
    );

    revealGroups.forEach((group) => observer.observe(group));

    const hero = document.querySelector(".lp-hero");
    if (hero) {
        window.requestAnimationFrame(() => hero.classList.add("is-loaded"));
    }

    const preview = document.querySelector(".lp-preview");
    const finePointer = window.matchMedia("(pointer: fine)");

    if (preview && finePointer.matches) {
        preview.addEventListener("pointermove", (event) => {
            const bounds = preview.getBoundingClientRect();
            const x = (event.clientX - bounds.left) / bounds.width - 0.5;
            const y = (event.clientY - bounds.top) / bounds.height - 0.5;

            preview.style.setProperty("--preview-rotate-x", `${(-y * 4).toFixed(2)}deg`);
            preview.style.setProperty("--preview-rotate-y", `${(x * 5).toFixed(2)}deg`);
            preview.style.setProperty("--preview-shift-x", `${(x * 6).toFixed(2)}px`);
            preview.style.setProperty("--preview-shift-y", `${(y * 6).toFixed(2)}px`);
        });

        preview.addEventListener("pointerleave", () => {
            preview.style.removeProperty("--preview-rotate-x");
            preview.style.removeProperty("--preview-rotate-y");
            preview.style.removeProperty("--preview-shift-x");
            preview.style.removeProperty("--preview-shift-y");
        });
    }
});
