const menuButton = document.querySelector(".menu-toggle");
const navigation = document.querySelector("#main-navigation");

if (menuButton && navigation) {
    navigation.classList.add("is-collapsible");

    menuButton.addEventListener("click", () => {
        const isOpen = navigation.classList.toggle("is-open");

        menuButton.setAttribute("aria-expanded", String(isOpen));
        menuButton.setAttribute(
            "aria-label",
            isOpen ? "Закрити меню" : "Відкрити меню"
        );
    });
}

const productQuantityInput = document.querySelector("#product-quantity");
const productUnitSelect = document.querySelector("#product-unit");

if (productQuantityInput && productUnitSelect) {
    const updateQuantityRules = () => {
        const isPieces = productUnitSelect.value === "pcs";

        productQuantityInput.min = isPieces ? "1" : "0.01";
        productQuantityInput.step = isPieces ? "1" : "0.01";
        productQuantityInput.inputMode = isPieces ? "numeric" : "decimal";

        if (isPieces) {
            const quantity = productQuantityInput.valueAsNumber;

            if (!Number.isInteger(quantity) || quantity < 1) {
                productQuantityInput.value = "1";
            }
        }
    };

    updateQuantityRules();
    productUnitSelect.addEventListener("change", updateQuantityRules);
    window.addEventListener("pageshow", updateQuantityRules);
}

// Кнопки кількості в кошику використовують min, max і step самого поля.
document.querySelectorAll("[data-quantity-control]").forEach((control) => {
    const input = control.querySelector('input[type="number"]');
    const decrease = control.querySelector('[data-quantity-change="-1"]');
    const increase = control.querySelector('[data-quantity-change="1"]');

    if (!input || !decrease || !increase) {
        return;
    }

    const updateButtons = () => {
        const value = input.valueAsNumber;
        decrease.disabled = Number.isFinite(value) && value <= Number(input.min);
        increase.disabled = Number.isFinite(value) && value >= Number(input.max);
    };

    [decrease, increase].forEach((button) => {
        button.addEventListener("click", () => {
            if (!Number.isFinite(input.valueAsNumber)) {
                input.value = input.min;
            } else {
                input.stepUp(Number(button.dataset.quantityChange));
            }
            input.dispatchEvent(new Event("input", { bubbles: true }));
        });
        button.hidden = false;
    });

    control.classList.add("is-enhanced");
    input.addEventListener("input", updateButtons);
    input.addEventListener("change", updateButtons);
    window.addEventListener("pageshow", updateButtons);
    updateButtons();
});

// Компактна шапка без зміни висоти елемента в потоці сторінки.
const siteHeader = document.querySelector(".site-header");

if (siteHeader) {
    const desktopHeader = window.matchMedia("(min-width: 1001px)");
    const updateHeader = () => {
        siteHeader.classList.toggle(
            "is-compact",
            desktopHeader.matches && window.scrollY > 160
        );
    };

    window.addEventListener("scroll", updateHeader, { passive: true });
    window.addEventListener("pageshow", updateHeader);
    desktopHeader.addEventListener("change", updateHeader);
    updateHeader();
}

// Поява блоків головної. Без бібліотек контент залишається видимим.
if (document.querySelector(".hero") && window.gsap && window.ScrollTrigger) {
    gsap.registerPlugin(ScrollTrigger);
    const revealMedia = gsap.matchMedia();
    const revealedElements = new WeakSet();

    revealMedia.add("(prefers-reduced-motion: no-preference)", () => {
        document.documentElement.classList.add("js-enabled");
        const gridSelector = ".benefits-grid, .category-grid, " +
            "#featured-products .catalog-products, .order-guide-steps";

        const reveal = (element, staggerChildren = false) => {
            if (revealedElements.has(element)) {
                return;
            }

            const timeline = gsap.timeline({
                scrollTrigger: {
                    trigger: element,
                    start: "top 92%",
                    once: true
                },
                onComplete: () => revealedElements.add(element)
            });

            timeline.from(element, {
                y: 20,
                opacity: 0,
                duration: 0.6,
                ease: "power2.out",
                clearProps: "transform,opacity"
            });

            if (staggerChildren) {
                timeline.from(element.children, {
                    opacity: 0,
                    duration: 0.4,
                    stagger: 0.06,
                    ease: "power2.out",
                    clearProps: "opacity"
                }, 0);
            }
        };

        document.querySelectorAll(gridSelector).forEach((grid) => reveal(grid, true));
        document.querySelectorAll("main .section").forEach((section) => {
            if (!section.querySelector(gridSelector)) {
                reveal(section);
            }
        });

        return () => document.documentElement.classList.remove("js-enabled");
    });
}
