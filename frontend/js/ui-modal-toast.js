(function (DocForge) {
  "use strict";
  const { Utils, State, Icons } = DocForge;

  const Toast = {
    show(type, message) {
      const region = type === "error"
        ? document.getElementById("toastRegionAssertive")
        : document.getElementById("toastRegionPolite");
      if (!region) return;

      const toast = document.createElement("div");
      toast.className = `toast is-${type}`;
      toast.setAttribute("role", type === "error" ? "alert" : "status");

      const icon = Icons.el(type === "error" ? "alert" : "check");

      const text = document.createElement("span");
      Utils.setText(text, message);

      const close = document.createElement("button");
      close.type = "button";
      close.className = "toast-close";
      close.setAttribute("aria-label", "Закрыть уведомление");
      close.appendChild(Icons.el("close"));

      toast.append(icon, text, close);
      region.appendChild(toast);

      const remove = () => toast.remove();
      close.addEventListener("click", remove);
      setTimeout(remove, 6000);
    },
  };

  const KeyModal = {
    overlay: null, modal: null, input: null, lastFocused: null,

    init() {
      this.overlay = document.getElementById("keyModalOverlay");
      this.modal = document.getElementById("keyModal");
      this.input = document.getElementById("apiKeyInput");
      this.statusEl = document.getElementById("keyStatus");
      if (!this.overlay) return;

      document.getElementById("keyModalCloseBtn").addEventListener("click", () => this.close());
      document.getElementById("keyModalCancelBtn").addEventListener("click", () => this.close());
      document.getElementById("saveKeyBtn").addEventListener("click", () => this.save());
      document.getElementById("removeKeyBtn").addEventListener("click", () => this.remove());
      document.querySelectorAll("[data-open-key-modal]").forEach((btn) => btn.addEventListener("click", () => this.open()));

      this.overlay.addEventListener("click", (e) => { if (e.target === this.overlay) this.close(); });

      document.addEventListener("keydown", (e) => {
        if (!this.overlay.classList.contains("is-open")) return;
        if (e.key === "Escape") { this.close(); return; }
        if (e.key === "Tab") this.trapFocus(e);
      });

      this.refreshStatus();
    },

    refreshStatus() {
      const has = Boolean(State.apiKey);
      this.statusEl.hidden = !has;
      this.input.value = "";
    },

    open() {
      this.lastFocused = document.activeElement;
      this.overlay.classList.add("is-open");
      this.refreshStatus();
      this.input.focus();
    },

    close() {
      this.overlay.classList.remove("is-open");
      if (this.lastFocused) this.lastFocused.focus();
    },

    save() {
      const value = this.input.value.trim();
      if (!value) { this.input.focus(); return; }
      State.setApiKey(value);
      Toast.show("success", "Ключ сохранён в этом браузере");
      this.close();
    },

    remove() {
      State.setApiKey("");
      this.refreshStatus();
      Toast.show("success", "Ключ удалён из этого браузера");
    },

    /** Focus trap: Tab не должен уходить за пределы модалки, пока она открыта. */
    trapFocus(e) {
      const focusables = this.modal.querySelectorAll('button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])');
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    },
  };

  DocForge.Toast = Toast;
  DocForge.KeyModal = KeyModal;
})(window.DocForge);
