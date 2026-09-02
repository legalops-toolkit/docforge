(function (DocForge) {
  "use strict";

  const State = {
    apiKey: localStorage.getItem("docforge_api_key") || "",
    extraction: {
      // Токен последнего запроса — не даёт устаревшему ответу затереть актуальный UI,
      // если пользователь успел отправить новый запрос, пока первый ещё летел.
      activeRequestId: null,
      lastEntities: null,
    },
    generation: {
      activeTab: "claim",
    },

    setApiKey(value) {
      this.apiKey = value || "";
      if (this.apiKey) {
        localStorage.setItem("docforge_api_key", this.apiKey);
      } else {
        localStorage.removeItem("docforge_api_key");
      }
    },
  };

  DocForge.State = State;
})(window.DocForge);
