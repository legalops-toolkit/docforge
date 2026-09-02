(function (DocForge) {
  "use strict";
  const { Utils, State } = DocForge;

  // Локальный/продакшен бэкенд. TODO: перед деплоем указать реальный домен продакшена
  // (и синхронно обновить connect-src в CSP-мете в <head> index.html).
  const API_BASE = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://localhost:8000"
    : "https://TODO-укажите-домен-продакшена.example"; // TODO: домен реального деплоя (Render/Railway/Fly.io)

  const REQUEST_TIMEOUT_MS = 30000;
  const MAX_NETWORK_RETRIES = 2;

  /**
   * Слой доступа к API. Ничего не знает про DOM — только формирует запросы
   * и возвращает размеченный по типу результат, который рендерит UI-слой.
   */
  const Api = {
    BASE: API_BASE,

    async request(path, { method = "GET", body, signal, expectBlob = false } = {}) {
      const headers = { "Content-Type": "application/json" };
      if (State.apiKey) headers["X-API-Key"] = State.apiKey;

      // Ссылка на контроллер текущей попытки: внешний сигнал отмены (повторный клик
      // пользователя) всегда бьёт по актуальной попытке, даже после ретрая.
      const ref = { controller: null };
      const onExternalAbort = () => ref.controller?.abort(signal?.reason);
      if (signal) signal.addEventListener("abort", onExternalAbort);

      let attempt = 0;
      try {
        while (true) {
          const controller = new AbortController();
          ref.controller = controller;
          if (signal?.aborted) return { kind: "aborted" };

          const timeoutId = setTimeout(
            () => controller.abort(new DOMException("timeout", "TimeoutError")),
            REQUEST_TIMEOUT_MS
          );

          try {
            const res = await fetch(API_BASE + path, {
              method,
              headers,
              body: body ? JSON.stringify(body) : undefined,
              signal: controller.signal,
            });
            clearTimeout(timeoutId);
            return await Api._handleResponse(res, expectBlob);
          } catch (err) {
            clearTimeout(timeoutId);
            const isTimeout = controller.signal.aborted && controller.signal.reason?.name === "TimeoutError";
            const isExternalAbort = controller.signal.aborted && !isTimeout;
            if (isExternalAbort) return { kind: "aborted" };

            const isNetwork = err instanceof TypeError; // fetch бросает TypeError при обрыве сети/CORS/недоступности хоста
            if ((isNetwork || isTimeout) && attempt < MAX_NETWORK_RETRIES) {
              attempt += 1;
              await Utils.sleep(400 * 2 ** (attempt - 1)); // экспоненциальный backoff: 400мс, 800мс…
              continue;
            }
            return { kind: isTimeout ? "timeout" : "network" };
          }
        }
      } finally {
        if (signal) signal.removeEventListener("abort", onExternalAbort);
      }
    },

    async _handleResponse(res, expectBlob) {
      if (res.status === 200 || res.status === 201) {
        if (expectBlob) {
          const blob = await res.blob();
          const filename = Api._filenameFromDisposition(res.headers.get("Content-Disposition"));
          return { kind: "success", blob, filename };
        }
        const data = await res.json().catch(() => ({}));
        return { kind: "success", data };
      }
      if (res.status === 422) {
        const data = await res.json().catch(() => ({}));
        return { kind: "validation", errors: Api._parseValidationErrors(data) };
      }
      if (res.status === 401 || res.status === 403) return { kind: "auth" };
      if (res.status === 429) {
        const retryAfter = res.headers.get("Retry-After");
        return { kind: "rate_limit", retryAfterSeconds: retryAfter ? Number(retryAfter) : null };
      }
      return { kind: "server", status: res.status };
    },

    /** FastAPI/pydantic отдаёт detail: [{loc: ["body","field"], msg: "..."}] */
    _parseValidationErrors(data) {
      const out = {};
      const detail = Array.isArray(data?.detail) ? data.detail : [];
      for (const item of detail) {
        const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : null;
        if (field) out[field] = item.msg || "Некорректное значение";
      }
      return out;
    },

    _filenameFromDisposition(header) {
      if (!header) return "document.docx";
      const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header);
      return match ? decodeURIComponent(match[1]) : "document.docx";
    },

    extract(text, signal) {
      return this.request("/extract", { method: "POST", body: { text }, signal });
    },

    generate(endpoint, payload, signal) {
      return this.request(endpoint, { method: "POST", body: payload, signal, expectBlob: true });
    },
  };

  DocForge.Api = Api;
})(window.DocForge);
