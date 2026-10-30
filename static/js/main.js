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

        const gridSelector = ".benefits-grid, .category-grid, .steps-grid, .order-guide-steps";

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

// Повторні повідомлення об'єднуємо; одночасно показуємо максимум два.
const messageMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const siteMessageControls = new WeakMap();

function trimSiteMessages(container) {
    const messages = Array.from(container.querySelectorAll(".site-message"));
    messages.slice(0, Math.max(0, messages.length - 2)).forEach((message) => {
        const controls = siteMessageControls.get(message);
        if (controls) {
            controls.remove();
        } else {
            message.remove();
        }
    });
}

function enhanceSiteMessage(message) {
    if (siteMessageControls.has(message)) {
        return;
    }

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "site-message-close";
    closeButton.setAttribute("aria-label", "Закрити повідомлення");
    closeButton.textContent = "×";
    let dismissTimer;
    const removeMessage = () => {
        clearTimeout(dismissTimer);
        siteMessageControls.delete(message);
        message.remove();
    };
    const dismissMessage = () => {
        clearTimeout(dismissTimer);
        if (closeButton.disabled) {
            return;
        }
        closeButton.disabled = true;
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
    const restartTimer = () => {
        clearTimeout(dismissTimer);
        dismissTimer = setTimeout(dismissMessage, 60000);
    };
    siteMessageControls.set(message, {
        refresh: restartTimer,
        remove: () => {
            clearTimeout(dismissTimer);
            message.getAnimations?.().forEach((animation) => animation.cancel());
            removeMessage();
        }
    });
    closeButton.addEventListener("click", dismissMessage);
    message.append(closeButton);
    restartTimer();

    if (!messageMotion.matches && message.animate) {
        message.animate([
            { opacity: 0, transform: "translateY(12px)" },
            { opacity: 1, transform: "translateY(0)" }
        ], { duration: 220, easing: "ease-out" });
    }
}

document.querySelectorAll(".site-messages").forEach((container) => {
    const seen = new Map();
    container.querySelectorAll(".site-message").forEach((message) => {
        const text = message.querySelector(".site-message-text")?.textContent.trim() || "";
        const key = message.className + ":" + text;
        seen.get(key)?.remove();
        seen.set(key, message);
    });
    trimSiteMessages(container);
    container.querySelectorAll(".site-message").forEach(enhanceSiteMessage);
});

messageMotion.addEventListener("change", (event) => {
    if (event.matches) {
        document.querySelectorAll(".site-message, .cart-flight, .cart-count").forEach((message) => {
            message.getAnimations().forEach((animation) => animation.finish());
        });
    }
});

function showSiteMessage(text, kind = "success") {
    kind = kind === "error" ? "error" : "success";
    let container = document.querySelector(".site-messages");
    if (!container) {
        container = document.createElement("div");
        container.className = "site-messages container";
        container.setAttribute("aria-label", "Повідомлення сайту");
        document.querySelector("main").prepend(container);
    }

    const existing = Array.from(container.querySelectorAll(".site-message")).find((message) => {
        return message.classList.contains(kind) &&
            message.querySelector(".site-message-text")?.textContent === text &&
            !message.querySelector(".site-message-close")?.disabled;
    });
    if (existing) {
        enhanceSiteMessage(existing);
        siteMessageControls.get(existing).refresh();
        container.append(existing);
        return;
    }

    const message = document.createElement("div");
    message.className = "site-message " + kind;
    message.setAttribute("role", kind === "error" ? "alert" : "status");
    const icon = document.createElement("span");
    icon.className = "site-message-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = kind === "error" ? "!" : "✓";
    const content = document.createElement("span");
    content.className = "site-message-text";
    content.textContent = text;
    message.append(icon, content);
    container.append(message);
    enhanceSiteMessage(message);
    trimSiteMessages(container);
}

function animateCartAddition(form) {
    if (messageMotion.matches || !Element.prototype.animate) {
        return;
    }
    const counter = document.querySelector("#cart-count");
    if (!counter) {
        return;
    }
    counter.animate([
        { transform: "scale(1)" },
        { transform: "scale(1.2)" },
        { transform: "scale(1)" }
    ], { duration: 320, easing: "ease-out" });

    const product = form.closest(".product-card, .product-detail");
    const image = product?.querySelector(".product-card-image img, .product-detail-photo img");
    if (!image) {
        return;
    }
    const imageBounds = image.getBoundingClientRect();
    const imageCenterY = imageBounds.top + imageBounds.height / 2;
    const headerBottom = document.querySelector(".site-header")?.getBoundingClientRect().bottom || 0;
    const origin = imageCenterY < headerBottom || imageCenterY > innerHeight
        ? form.querySelector('button[type="submit"]').getBoundingClientRect()
        : imageBounds;
    const destination = counter.getBoundingClientRect();
    if (destination.bottom < 0 || destination.top > innerHeight) {
        return;
    }
    const startX = Math.max(40, Math.min(innerWidth - 40, origin.left + origin.width / 2));
    const startY = Math.max(50, Math.min(innerHeight - 50, origin.top + origin.height / 2));
    const deltaX = destination.left + destination.width / 2 - startX;
    const deltaY = destination.top + destination.height / 2 - startY;
    const flight = document.createElement("img");
    flight.src = image.currentSrc || image.src;
    flight.alt = "";
    flight.setAttribute("aria-hidden", "true");
    flight.className = "cart-flight";
    flight.style.left = (startX - 40) + "px";
    flight.style.top = (startY - 50) + "px";
    document.body.append(flight);
    flight.animate([
        { transform: "translate(0, 0) scale(1)", opacity: 0.95 },
        { transform: `translate(${deltaX * 0.5}px, ${deltaY * 0.5 - 40}px) scale(0.65)`, opacity: 0.8 },
        { transform: `translate(${deltaX}px, ${deltaY}px) scale(0.15)`, opacity: 0 }
    ], { duration: 650, easing: "ease-in-out", fill: "forwards" })
        .finished.then(() => flight.remove(), () => flight.remove());
}

// Одна черга запитів запобігає одночасному перезаписуванню сесії кошика.
let cartAddQueue = Promise.resolve();
if (window.fetch && window.FormData) {
    document.querySelectorAll(".product-card-cart, .product-request-form").forEach((form) => {
        form.addEventListener("submit", (event) => {
            event.preventDefault();
            if (form.dataset.submitting === "true") {
                return;
            }
            const button = event.submitter || form.querySelector('button[type="submit"]');
            const body = new FormData(form);
            const originalText = button.textContent;
            form.dataset.submitting = "true";
            form.setAttribute("aria-busy", "true");
            button.disabled = true;
            button.textContent = "Додаємо…";

            cartAddQueue = cartAddQueue.then(async () => {
                const response = await fetch(form.action, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Accept": "application/json",
                        "X-CSRFToken": body.get("csrfmiddlewaretoken")
                    },
                    body
                });
                if (!response.headers.get("Content-Type")?.includes("application/json")) {
                    showSiteMessage(response.status === 404
                        ? "Товар більше недоступний. Оновіть каталог."
                        : "Не вдалося додати товар. Оновіть сторінку та перевірте кошик.", "error");
                    return;
                }
                const result = await response.json();
                if (!response.ok || !result.ok) {
                    showSiteMessage(result.message || "Не вдалося додати товар.", "error");
                    return;
                }
                const counter = document.querySelector("#cart-count");
                if (counter) {
                    counter.textContent = String(result.cart_count);
                }
                document.querySelector(".cart-link")?.setAttribute(
                    "aria-label", "Кошик заявки. Кількість позицій: " + result.cart_count
                );
                showSiteMessage(result.message);
                animateCartAddition(form);
            }).catch(() => {
                showSiteMessage(
                    "Не вдалося підтвердити додавання. Перевірте кошик перед повторною спробою.",
                    "error"
                );
            }).finally(() => {
                button.disabled = false;
                button.textContent = originalText;
                form.removeAttribute("aria-busy");
                delete form.dataset.submitting;
            });
        });
    });
}


// Добірка: керування кнопками, клавіатурою та звичайним свайпом.
document.querySelectorAll(".selection-track").forEach((track) => {
    const section = track.closest("section");
    const controls = section.querySelector("[data-selection-controls]");
    const position = section.querySelector(".selection-position");
    const cards = Array.from(track.children);
    if (!controls || !cards.length) return;
    const previous = controls.querySelector('[data-selection-direction="-1"]');
    const next = controls.querySelector('[data-selection-direction="1"]');
    let updateFrame = 0;
    const update = () => {
        const maximum = Math.max(0, track.scrollWidth - track.clientWidth);
        controls.hidden = maximum < 2;
        previous.disabled = track.scrollLeft <= 8;
        next.disabled = track.scrollLeft >= maximum - 2;
        const bounds = track.getBoundingClientRect();
        const visible = cards.map((card, index) => ({ bounds: card.getBoundingClientRect(), index }))
            .filter((card) => card.bounds.right > bounds.left + 12 && card.bounds.left < bounds.right - 12);
        if (visible.length) position.textContent = `Показано товари ${visible[0].index + 1}–${visible[visible.length - 1].index + 1} із ${cards.length}`;
    };
    const schedule = () => { cancelAnimationFrame(updateFrame); updateFrame = requestAnimationFrame(update); };
    const move = (direction) => {
        const gap = parseFloat(getComputedStyle(track).columnGap) || 0;
        const cardWidth = cards[0].getBoundingClientRect().width + gap;
        const pageSize = Math.max(1, Math.floor((track.clientWidth + gap) / cardWidth));
        const target = Math.max(0, Math.min(track.scrollWidth - track.clientWidth, track.scrollLeft + direction * pageSize * cardWidth));
        track.scrollTo({ left: target, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
    };
    previous.addEventListener("click", () => move(-1));
    next.addEventListener("click", () => move(1));
    track.addEventListener("scroll", schedule, { passive: true });
    track.addEventListener("keydown", (event) => {
        if (event.target !== track) return;
        if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
            event.preventDefault(); move(event.key === "ArrowLeft" ? -1 : 1);
        } else if (event.key === "Home" || event.key === "End") {
            event.preventDefault();
            track.scrollTo({ left: event.key === "Home" ? 0 : track.scrollWidth, behavior: "instant" });
        }
    });
    if (window.ResizeObserver) new ResizeObserver(schedule).observe(track);
    window.addEventListener("resize", schedule, { passive: true });
    if (document.fonts) document.fonts.ready.then(schedule);
    update();
});

// Лічильники запускаються один раз; доступний текст завжди містить кінцеве число.
(() => {
    document.documentElement.classList.add("js-enabled");
    const motion = matchMedia("(prefers-reduced-motion: reduce)");
    const counters = Array.from(document.querySelectorAll("[data-count]"));
    const running = new Map();
    let observer;
    const finish = () => {
        observer?.disconnect();
        running.forEach((state, element) => {
            cancelAnimationFrame(state.frame);
            state.value.textContent = element.dataset.count;
        });
        running.clear();
    };
    const animateCounter = (element) => {
        const target = Number(element.dataset.count);
        if (!Number.isFinite(target) || target < 0) return;
        const accessible = document.createElement("span");
        accessible.className = "visually-hidden";
        accessible.textContent = String(target);
        const value = document.createElement("span");
        value.setAttribute("aria-hidden", "true");
        value.textContent = "0";
        element.replaceChildren(accessible, value);
        const state = { frame: 0, value };
        running.set(element, state);
        let started;
        const tick = (time) => {
            if (started === undefined) started = time;
            const progress = Math.min(1, (time - started) / 1600);
            value.textContent = String(Math.round(target * (1 - Math.pow(1 - progress, 3))));
            if (progress < 1 && !motion.matches) state.frame = requestAnimationFrame(tick);
            else { value.textContent = String(target); running.delete(element); }
        };
        state.frame = requestAnimationFrame(tick);
    };
    if (!motion.matches && window.IntersectionObserver) {
        observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) { observer.unobserve(entry.target); animateCounter(entry.target); }
            });
        }, { threshold: 0.4 });
        counters.forEach((element) => observer.observe(element));
    }
    motion.addEventListener("change", () => { if (motion.matches) finish(); });

    // Пройдені відрізки шкали заявки заповнюються послідовно.
    if (!motion.matches && Element.prototype.animate) {
        document.querySelectorAll(".order-progress").forEach((progress) => {
            const animations = [];
            progress.classList.add("motion-ready");
            progress.querySelectorAll(".is-reached, .is-current").forEach((step, index) => {
                const fill = document.createElement("span");
                fill.className = "order-step-fill";
                fill.setAttribute("aria-hidden", "true");
                step.append(fill);
                animations.push(fill.animate([{ transform: "scaleX(0)" }, { transform: "scaleX(1)" }], {
                    duration: 450, delay: index * 140, easing: "ease-out", fill: "backwards"
                }));
            });
            motion.addEventListener("change", () => {
                if (motion.matches) {
                    animations.forEach((animation) => animation.cancel());
                    progress.classList.remove("motion-ready");
                    progress.querySelectorAll(".order-step-fill").forEach((fill) => fill.remove());
                }
            });
        });
    }
})();
