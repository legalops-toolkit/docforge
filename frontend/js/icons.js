/**
 * DocForge — собственный набор линейных иконок (24x24, stroke-based).
 * Используется вместо Font Awesome: меньше веса, нет внешней зависимости,
 * не выглядит как дефолтный шаблон.
 */
(function (DocForge) {
  "use strict";

  // Внутреннее содержимое <svg> (без обёртки) — так его можно и вписать в
  // HTML напрямую через шаблонную строку, и использовать в JS через el().
  const PATHS = {
    search: '<circle cx="10" cy="10" r="6.5"/><line x1="15" y1="15" x2="20" y2="20"/>',
    close: '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
    arrow: '<line x1="4" y1="12" x2="19" y2="12"/><polyline points="13 6 19 12 13 18"/>',
    check: '<polyline points="5 13 10 18 19 7"/>',
    alert: '<circle cx="12" cy="12" r="9"/><line x1="12" y1="7.5" x2="12" y2="13"/><circle cx="12" cy="16.5" r="0.75" fill="currentColor" stroke="none"/>',
    document: '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/><line x1="9.5" y1="12" x2="14.5" y2="12"/><line x1="9.5" y1="15.5" x2="14.5" y2="15.5"/>',
    key: '<circle cx="7.5" cy="12" r="4"/><line x1="11" y1="12" x2="20" y2="12"/><line x1="16" y1="12" x2="16" y2="15"/><line x1="19" y1="12" x2="19" y2="15"/>',
    shield: '<path d="M12 3l7 3v6c0 5-3.5 8-7 9-3.5-1-7-4-7-9V6z"/><polyline points="8.5 12 11 14.5 16 9"/>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1H5z"/><path d="M4 10h16l-1.5 8.5a2 2 0 0 1-2 1.5H7.5a2 2 0 0 1-2-1.5z"/>',
    github: '<path fill="currentColor" stroke="none" d="M12 .3a12 12 0 0 0-3.8 23.4c.6.1.8-.3.8-.6v-2.2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.4-1.8-1.4-1.8-1.1-.8.1-.8.1-.8 1.2.1 1.8 1.3 1.8 1.3 1.1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-6a4.6 4.6 0 0 1 1.3-3.2 4.3 4.3 0 0 1 .1-3.2s1-.3 3.4 1.2a11.7 11.7 0 0 1 6.2 0c2.3-1.5 3.4-1.2 3.4-1.2a4.3 4.3 0 0 1 .1 3.2 4.6 4.6 0 0 1 1.3 3.2c0 4.7-2.9 5.7-5.5 6 .4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0 0 12 .3"/>',
    spinner: '<circle cx="12" cy="12" r="8" stroke-dasharray="30 12"/>',
    retry: '<path d="M4 12a8 8 0 1 1 2.5 5.8"/><polyline points="4 17 4 12 9 12"/>',
    eye: '<path d="M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="2.6"/>',
    download: '<path d="M12 3v12"/><polyline points="7 11 12 16 17 11"/><line x1="5" y1="20" x2="19" y2="20"/>',
    question: '<circle cx="12" cy="12" r="9" stroke-dasharray="3 3"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .8-1 1.7"/><circle cx="12" cy="16.3" r="0.75" fill="currentColor" stroke="none"/>',
  };

  const Icons = {
    /** @returns {string} готовая разметка <svg> — для вставки через innerHTML/шаблон */
    markup(name, extraClass) {
      const inner = PATHS[name] || "";
      const cls = extraClass ? `icon ${extraClass}` : "icon";
      return `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${inner}</svg>`;
    },

    /** @returns {SVGSVGElement} готовый DOM-узел — для случаев вроде toast/кнопок, собираемых через createElement */
    el(name, extraClass) {
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 24 24");
      svg.setAttribute("aria-hidden", "true");
      svg.setAttribute("class", extraClass ? `icon ${extraClass}` : "icon");
      svg.innerHTML = PATHS[name] || "";
      return svg;
    },
  };

  DocForge.Icons = Icons;
})(window.DocForge);
