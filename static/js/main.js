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
