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

        const hero = document.querySelector(".hero");
        if (!revealedElements.has(hero)) {
            gsap.from(hero.querySelectorAll(".hero-word"), {
                y: 24,
                opacity: 0,
                duration: 0.75,
                stagger: 0.12,
                ease: "power2.out",
                clearProps: "transform,opacity",
                onComplete: () => revealedElements.add(hero)
            });
        }

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

    revealMedia.add(
        "(min-width: 1001px) and (prefers-reduced-motion: no-preference)",
        () => {
            gsap.fromTo(".hero-banner", {
                scale: 1.08,
                y: -12
            }, {
                scale: 1.08,
                y: 12,
                ease: "none",
                scrollTrigger: {
                    trigger: ".hero",
                    start: "top top",
                    end: "bottom top",
                    scrub: 0.5
                }
            });
        }
    );
}

// Безперервний рядок: однакові групи без розтягування проміжків.
document.querySelectorAll("[data-category-marquee]").forEach((marquee) => {
    const viewport = marquee.querySelector(".category-marquee-viewport");
    const group = marquee.querySelector(".category-marquee-group");
    const copy = marquee.querySelector(".category-marquee-copy");
    if (!viewport || !group || !copy || !group.children.length) {
        return;
    }

    const originalItems = Array.from(group.children, (item) => item.cloneNode(true));
    const motion = window.matchMedia("(prefers-reduced-motion: no-preference)");
    let resizeFrame = 0;

    const updateMarquee = () => {
        group.replaceChildren(...originalItems.map((item) => item.cloneNode(true)));
        copy.replaceChildren(...originalItems.map((item) => item.cloneNode(true)));
        if (!motion.matches || !document.documentElement.classList.contains("js-enabled") || !viewport.clientWidth) {
            return;
        }

        while (group.getBoundingClientRect().width < viewport.clientWidth) {
            group.append(...originalItems.map((item) => item.cloneNode(true)));
        }
        copy.replaceChildren(...Array.from(group.children, (item) => item.cloneNode(true)));
    };

    const scheduleUpdate = () => {
        cancelAnimationFrame(resizeFrame);
        resizeFrame = requestAnimationFrame(updateMarquee);
    };

    window.addEventListener("resize", scheduleUpdate, { passive: true });
    motion.addEventListener("change", scheduleUpdate);
    new MutationObserver(scheduleUpdate).observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["class"]
    });
    if (document.fonts) {
        document.fonts.ready.then(scheduleUpdate);
    }
    updateMarquee();
});

// Сповіщення можна закрити; без JavaScript текст залишається видимим.
const messageMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

function enhanceSiteMessage(message) {
    if (message.querySelector(".site-message-close")) {
        return;
    }

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "site-message-close";
    closeButton.setAttribute("aria-label", "Закрити повідомлення");
    closeButton.textContent = "×";
    let dismissTimer;
    const dismissMessage = () => {
        clearTimeout(dismissTimer);
        if (closeButton.disabled) {
            return;
        }
        closeButton.disabled = true;
        const removeMessage = () => message.remove();
        if (messageMotion.matches || !message.animate) {
            removeMessage();
            return;
        }

        message.animate([
            { opacity: 1, transform: "translateY(0)" },
            { opacity: 0, transform: "translateY(12px)" }
        ], { duration: 180, easing: "ease-in", fill: "forwards" })
            .finished.then(removeMessage, removeMessage);
    };
    closeButton.addEventListener("click", dismissMessage);
    dismissTimer = setTimeout(dismissMessage, 60000);
    message.append(closeButton);

    if (!messageMotion.matches && message.animate) {
        message.animate([
            { opacity: 0, transform: "translateY(12px)" },
            { opacity: 1, transform: "translateY(0)" }
        ], { duration: 220, easing: "ease-out" });
    }
}

document.querySelectorAll(".site-message").forEach(enhanceSiteMessage);
messageMotion.addEventListener("change", (event) => {
    if (event.matches) {
        document.querySelectorAll(".site-message").forEach((message) => {
            message.getAnimations().forEach((animation) => animation.finish());
        });
    }
});
