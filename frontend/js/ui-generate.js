(function (DocForge) {
  "use strict";
  const { Utils, Api, Validation, Toast, KeyModal, State, Icons } = DocForge;

  const UIGenerate = {
    init() {
      this.bindTabs();
      this.bindForms();
      this.bindMoneyFields();
    },

    /* ------------------------------- Табы ------------------------------- */
    bindTabs() {
      const tablist = document.getElementById("genTablist");
      if (!tablist) return;
      const tabs = Array.from(tablist.querySelectorAll(".tab"));

      const activate = (tab, moveFocus) => {
        tabs.forEach((t) => {
          const selected = t === tab;
          t.setAttribute("aria-selected", String(selected));
          t.tabIndex = selected ? 0 : -1;
          const panel = document.getElementById(t.getAttribute("aria-controls"));
          panel.classList.toggle("is-active", selected);
          panel.hidden = !selected;
        });
        State.generation.activeTab = tab.dataset.tab;
        if (moveFocus) tab.focus();
      };

      tabs.forEach((tab, i) => {
        tab.addEventListener("click", () => activate(tab, false));
        tab.addEventListener("keydown", (e) => {
          let targetIndex = null;
          if (e.key === "ArrowRight") targetIndex = (i + 1) % tabs.length;
          else if (e.key === "ArrowLeft") targetIndex = (i - 1 + tabs.length) % tabs.length;
          else if (e.key === "Home") targetIndex = 0;
          else if (e.key === "End") targetIndex = tabs.length - 1;
          if (targetIndex !== null) { e.preventDefault(); activate(tabs[targetIndex], true); }
        });
      });
    },

    /* ------------------------------- Формы ------------------------------- */
    bindForms() {
      document.querySelectorAll("[data-form]").forEach((form) => this.bindOneForm(form));
    },

    bindOneForm(form) {
      const endpoint = form.dataset.endpoint;
      const submitBtn = form.querySelector("[data-submit]");
      let controller = null;
      const fields = Array.from(form.querySelectorAll("[data-field]"));

      const validateOne = (fieldEl) => {
        const name = fieldEl.dataset.field;
        const input = fieldEl.querySelector("input");
        const err = Validation.validateField(name, input.value);
        const errorSpan = fieldEl.querySelector(".field-error span");
        fieldEl.classList.toggle("is-invalid", Boolean(err));
        if (errorSpan) errorSpan.textContent = err || "";
        return !err;
      };

      fields.forEach((fieldEl) => {
        fieldEl.querySelector("input").addEventListener("blur", () => validateOne(fieldEl));
      });

      form.addEventListener("submit", async (e) => {
        e.preventDefault();

        let firstInvalid = null;
        fields.forEach((fieldEl) => {
          const ok = validateOne(fieldEl);
          if (!ok && !firstInvalid) firstInvalid = fieldEl.querySelector("input");
        });
        if (firstInvalid) { firstInvalid.focus(); return; }

        const payload = {};
        fields.forEach((fieldEl) => {
          const name = fieldEl.dataset.field;
          const input = fieldEl.querySelector("input");
          if (input.dataset.money !== undefined) {
            const digits = input.value.replace(/\D/g, "");
            if (digits) payload[name] = Number(digits);
          } else if (input.value.trim()) {
            payload[name] = input.value.trim();
          }
        });

        if (controller) controller.abort();
        controller = new AbortController();
        submitBtn.disabled = true;
        submitBtn.dataset.originalLabel = submitBtn.innerHTML;
        submitBtn.innerHTML = Icons.markup("spinner", "icon-spin") + " Формируем…";

        const result = await Api.generate(endpoint, payload, controller.signal);

        submitBtn.disabled = false;
        submitBtn.innerHTML = submitBtn.dataset.originalLabel;
        this.handleResult(fields, result);
      });
    },

    handleResult(fields, result) {
      if (result.kind === "success") {
        const url = URL.createObjectURL(result.blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = result.filename || "document.docx";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url); // освобождаем память сразу после клика по временной ссылке
        Toast.show("success", `Документ «${result.filename}» готов и скачан`);
        return;
      }

      if (result.kind === "validation") {
        let firstInvalid = null;
        fields.forEach((fieldEl) => {
          const name = fieldEl.dataset.field;
          const err = result.errors[name];
          const input = fieldEl.querySelector("input");
          const errorSpan = fieldEl.querySelector(".field-error span");
          fieldEl.classList.toggle("is-invalid", Boolean(err));
          if (errorSpan) errorSpan.textContent = err || "";
          if (err && !firstInvalid) firstInvalid = input;
        });
        if (firstInvalid) firstInvalid.focus();
        Toast.show("error", "Сервер отклонил часть полей — проверьте форму");
        return;
      }

      if (result.kind === "auth") { Toast.show("error", "Нужен API-ключ для генерации документа"); KeyModal.open(); return; }
      if (result.kind === "rate_limit") {
        const when = result.retryAfterSeconds ? `через ${result.retryAfterSeconds} с` : "чуть позже";
        Toast.show("error", `Превышен лимит запросов. Повторите ${when}.`);
        return;
      }
      if (result.kind === "timeout") { Toast.show("error", "Сервер не ответил за 30 секунд — повторите запрос"); return; }
      if (result.kind === "network") { Toast.show("error", `Нет соединения с ${Api.BASE}. Проверьте, что бэкенд запущен.`); return; }
      if (result.kind === "aborted") return;

      Toast.show("error", "Внутренняя ошибка сервера при генерации документа");
    },

    /* ------------------------------- Суммы ------------------------------- */
    bindMoneyFields() {
      document.querySelectorAll("[data-money]").forEach((input) => {
        const hint = document.getElementById(input.getAttribute("aria-describedby").split(" ")[1]);
        const update = () => {
          const digitsOnly = input.value.replace(/\D/g, "");
          if (input.value !== digitsOnly) input.value = digitsOnly;
          if (hint) hint.textContent = digitsOnly ? `= ${Utils.formatMoney(digitsOnly)}` : "0 ₽";
        };
        input.addEventListener("input", update);
        update();
      });
    },
  };

  DocForge.UIGenerate = UIGenerate;
})(window.DocForge);
