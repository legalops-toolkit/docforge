/**
 * DocForge — общий неймспейс.
 * Каждый файл в js/ расширяет window.DocForge своим под-объектом.
 * В window попадает только один символ (DocForge), точка входа — main.js.
 */
window.DocForge = window.DocForge || {};

(function (DocForge) {
  "use strict";

  const Utils = {
    /** @param {Function} fn @param {number} wait */
    debounce(fn, wait) {
      let t;
      return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), wait);
      };
    },

    /** Форматирует число как "500 000 ₽" — только для отображения, не для парсинга обратно. */
    formatMoney(raw) {
      const digits = String(raw ?? "").replace(/\D/g, "");
      if (!digits) return "0 ₽";
      return digits.replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " ₽";
    },

    /** Безопасно проставляет текст без риска XSS — используется вместо innerHTML для любых данных с API. */
    setText(el, text) {
      el.textContent = text == null || text === "" ? "" : String(text);
    },

    sleep(ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    },

    uid() {
      return Math.random().toString(36).slice(2, 10);
    },

    prefersReducedMotion() {
      return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    },

    clamp(value, min, max) {
      return Math.min(Math.max(value, min), max);
    },
  };

  DocForge.Utils = Utils;
})(window.DocForge);
