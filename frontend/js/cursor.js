(function (DocForge) {
  "use strict";
  const { Utils } = DocForge;

  const Cursor = {
    init() {
      const finePointer = window.matchMedia("(pointer: fine)").matches;
      if (!finePointer || Utils.prefersReducedMotion()) return;

      this.dot = document.createElement("div");
      this.dot.className = "custom-cursor";
      this.dot.setAttribute("aria-hidden", "true");
      document.body.appendChild(this.dot);

      window.addEventListener("mousemove", (e) => {
        this.dot.classList.add("is-active");
        this.dot.style.left = `${e.clientX}px`;
        this.dot.style.top = `${e.clientY}px`;
      });
      document.addEventListener("mouseleave", () => this.dot.classList.remove("is-active"));

      const hoverTargets = "a, button, input, textarea, [role='tab']";
      document.addEventListener("mouseover", (e) => {
        if (e.target.closest(hoverTargets)) this.dot.classList.add("is-hovering");
      });
      document.addEventListener("mouseout", (e) => {
        if (e.target.closest(hoverTargets)) this.dot.classList.remove("is-hovering");
      });

      this.bindMagneticButtons();
    },

    /** Кнопки с data-magnetic слегка "тянутся" за курсором в пределах своих границ. */
    bindMagneticButtons() {
      document.querySelectorAll("[data-magnetic]").forEach((btn) => {
        btn.addEventListener("mousemove", (e) => {
          const rect = btn.getBoundingClientRect();
          const relX = e.clientX - rect.left - rect.width / 2;
          const relY = e.clientY - rect.top - rect.height / 2;
          btn.style.transform = `translate(${relX * 0.25}px, ${relY * 0.3}px)`;
        });
        btn.addEventListener("mouseleave", () => {
          btn.style.transform = "";
        });
      });
    },
  };

  DocForge.Cursor = Cursor;
})(window.DocForge);
