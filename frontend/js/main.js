(function (DocForge) {
  "use strict";

  function init() {
    // Каждый модуль инициализируется независимо: если один упадёт, остальные
    // всё равно смогут отработать, а статическая разметка страницы уже
    // отрисована браузером — белого экрана быть не может.
    const modules = [
      DocForge.ScrollAnimations,
      DocForge.Cursor,
      DocForge.KeyModal,
      DocForge.UIExtract,
      DocForge.UIGenerate,
    ];
    modules.forEach((mod) => {
      try {
        mod.init();
      } catch (err) {
        console.error("DocForge module init failed:", err);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window.DocForge);
