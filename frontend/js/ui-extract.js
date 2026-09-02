(function (DocForge) {
  "use strict";
  const { Utils, State, Api, Validation, Toast, KeyModal, Icons } = DocForge;

  const LABELS = {
    court: "Суд", judge: "Судья", case_number: "Номер дела",
    plaintiff: "Истец", defendant: "Ответчик", claim_amount: "Сумма",
  };
  const EXAMPLE_TEXT = "Арбитражный суд города Москвы в составе судьи Иванова И.И. рассмотрел дело № А40-12345/2024 по иску ООО «Ромашка» к ИП Петрову П.П. о взыскании 500000 рублей.";
  const LIMIT = 50000;
  const WARNING_ZONE = 500;

  const UIExtract = {
    init() {
      this.form = document.getElementById("extractForm");
      if (!this.form) return;
      this.textarea = document.getElementById("extractText");
      this.counter = document.getElementById("extractCharCounter");
      this.field = document.getElementById("extractTextField");
      this.errorMsg = document.getElementById("extractTextErrorMsg");
      this.submitBtn = document.getElementById("extractSubmitBtn");
      this.currentController = null;

      document.getElementById("fillExampleBtn").addEventListener("click", () => this.fillExample());
      document.getElementById("emptyTryExampleBtn").addEventListener("click", () => this.fillExample());
      document.getElementById("clearExtractBtn").addEventListener("click", () => this.clear());
      document.getElementById("useInGenerationBtn").addEventListener("click", () => this.sendToGeneration());

      const validateLive = Utils.debounce(() => {
        this.setFieldError(Validation.extractionText(this.textarea.value));
      }, 350);

      this.textarea.addEventListener("input", () => { this.updateCounter(); validateLive(); });
      this.textarea.addEventListener("blur", () => this.setFieldError(Validation.extractionText(this.textarea.value)));
      this.form.addEventListener("submit", (e) => this.onSubmit(e));

      this.updateCounter();
    },

    updateCounter() {
      const len = this.textarea.value.length;
      this.counter.textContent = `${len} / ${LIMIT}`;
      this.counter.classList.toggle("is-warning", len > LIMIT - WARNING_ZONE && len <= LIMIT);
      this.counter.classList.toggle("is-limit", len > LIMIT);
    },

    setFieldError(message) {
      this.field.classList.toggle("is-invalid", Boolean(message));
      this.errorMsg.textContent = message || "";
    },

    fillExample() {
      this.textarea.value = EXAMPLE_TEXT;
      this.updateCounter();
      this.setFieldError(null);
      this.textarea.focus();
    },

    clear() {
      this.textarea.value = "";
      this.updateCounter();
      this.setFieldError(null);
      this.setState("idle");
      this.textarea.focus();
    },

    async onSubmit(e) {
      e.preventDefault();
      const err = Validation.extractionText(this.textarea.value);
      this.setFieldError(err);
      if (err) { this.textarea.focus(); return; }

      if (this.currentController) this.currentController.abort();
      this.currentController = new AbortController();
      const requestId = Utils.uid();
      State.extraction.activeRequestId = requestId;

      this.submitBtn.disabled = true;
      this.setState("loading");

      const result = await Api.extract(this.textarea.value.trim(), this.currentController.signal);

      if (State.extraction.activeRequestId !== requestId || result.kind === "aborted") {
        this.submitBtn.disabled = false;
        return;
      }
      this.submitBtn.disabled = false;
      this.renderResult(result);
    },

    setState(name) {
      document.querySelectorAll("#extractResultPanel .result-state").forEach((el) => {
        el.classList.toggle("is-active", el.dataset.state === name);
      });
      document.getElementById("extractResultPanel").setAttribute("aria-busy", name === "loading" ? "true" : "false");
    },

    renderResult(result) {
      if (result.kind === "success") return this.renderSuccess(result);
      if (result.kind === "timeout") return this.renderError(
        "Сервер не ответил за 30 секунд",
        "Похоже, бэкенд перегружен или недоступен. Повторите попытку — запрос будет отправлен заново.",
        [this.makeRetryBtn(() => this.form.requestSubmit())]
      );
      if (result.kind === "network") return this.renderError(
        "Нет соединения с сервером",
        `Проверьте, что DocForge API запущен и доступен по адресу ${Api.BASE}, и что сеть не блокирует запрос.`,
        [this.makeRetryBtn(() => this.form.requestSubmit())]
      );
      if (result.kind === "auth") return this.renderError(
        "Нужен API-ключ",
        "Этот инстанс DocForge требует X-API-Key. Укажите ключ и повторите запрос.",
        [this.makeActionBtn("Указать ключ", () => KeyModal.open())]
      );
      if (result.kind === "rate_limit") {
        const when = result.retryAfterSeconds ? `через ${result.retryAfterSeconds} с` : "чуть позже";
        return this.renderError("Превышен лимит запросов", `Сервер ограничивает частоту запросов. Повторите ${when}.`, []);
      }
      if (result.kind === "validation") {
        const firstMsg = Object.values(result.errors)[0] || "Проверьте текст и повторите.";
        return this.renderError("Сервер отклонил запрос", firstMsg, [this.makeActionBtn("Показать пример текста", () => this.fillExample())]);
      }
      return this.renderError(
        "Ошибка на стороне сервера",
        "Сервер вернул внутреннюю ошибку при обработке текста. Это не связано с вашим вводом — попробуйте ещё раз.",
        [this.makeRetryBtn(() => this.form.requestSubmit())]
      );
    },

    renderSuccess(result) {
      const entities = result.data?.entities || result.data || {};
      State.extraction.lastEntities = entities;
      const foundAny = Object.values(entities).some((v) => v !== null && v !== undefined && v !== "" && v !== "Не найден");

      if (!foundAny) { this.setState("empty"); return; }

      const list = document.getElementById("entityList");
      list.innerHTML = ""; // элементы формируются через createElement/textContent — без интерполяции строк
      Object.entries(LABELS).forEach(([key, label]) => {
        const value = entities[key];
        const row = document.createElement("div");
        row.className = "entity-row";
        const dt = document.createElement("dt");
        Utils.setText(dt, label);
        const dd = document.createElement("dd");
        const isMissing = value === null || value === undefined || value === "" || value === "Не найден";
        if (isMissing) { dd.classList.add("is-missing"); Utils.setText(dd, "не найдено"); }
        else if (key === "claim_amount") Utils.setText(dd, Utils.formatMoney(value));
        else Utils.setText(dd, value);
        row.append(dt, dd);
        list.appendChild(row);
      });
      this.setState("success");
      Toast.show("success", "Извлечение завершено");
    },

    renderError(title, body, actions) {
      Utils.setText(document.getElementById("errorTitle"), title);
      Utils.setText(document.getElementById("errorBody"), body);
      const actionsEl = document.getElementById("errorActions");
      actionsEl.innerHTML = "";
      actions.forEach((btn) => actionsEl.appendChild(btn));
      this.setState("error");
      Toast.show("error", title);
    },

    makeRetryBtn(onClick) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-ghost btn-sm";
      btn.appendChild(Icons.el("retry"));
      btn.appendChild(document.createTextNode(" Повторить"));
      btn.addEventListener("click", onClick);
      return btn;
    },

    makeActionBtn(label, onClick) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-ghost btn-sm";
      Utils.setText(btn, label);
      btn.addEventListener("click", onClick);
      return btn;
    },

    sendToGeneration() {
      document.getElementById("generate").scrollIntoView({ behavior: "smooth", block: "start" });
      const entities = State.extraction.lastEntities || {};
      const map = {
        "claim-plaintiff": entities.plaintiff, "claim-defendant": entities.defendant,
        "claim-case_number": entities.case_number, "claim-claim_amount": entities.claim_amount,
        "appeal-plaintiff": entities.plaintiff, "appeal-defendant": entities.defendant,
        "appeal-case_number": entities.case_number, "appeal-claim_amount": entities.claim_amount,
      };
      Object.entries(map).forEach(([id, value]) => {
        if (!value || value === "Не найден") return;
        const input = document.getElementById(id);
        if (!input) return;
        input.value = input.dataset.money !== undefined ? String(value).replace(/\D/g, "") : String(value);
        input.dispatchEvent(new Event("input", { bubbles: true }));
      });
    },
  };

  DocForge.UIExtract = UIExtract;
})(window.DocForge);
