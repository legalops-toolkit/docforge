(function (DocForge) {
  "use strict";

  const Validation = {
    rules: {
      plaintiff: { required: true, label: "Истец" },
      defendant: { required: true, label: "Ответчик" },
      case_number: { required: true, label: "Номер дела", minLength: 3 },
      claim_amount: { required: true, label: "Сумма иска", money: true },
      court: { required: false, label: "Апелляционный суд" },
      customer: { required: true, label: "Заказчик" },
      contractor: { required: true, label: "Исполнитель" },
      contract_number: { required: true, label: "Номер договора", minLength: 3 },
      contract_amount: { required: true, label: "Сумма договора", money: true },
      contractor_representative: { required: false, label: "Представитель исполнителя" },
    },

    /** @returns {string|null} текст ошибки или null, если поле валидно */
    validateField(name, rawValue) {
      const rule = this.rules[name];
      if (!rule) return null;
      const value = (rawValue ?? "").toString().trim();

      if (rule.required && !value) return `«${rule.label}» — обязательное поле.`;
      if (rule.money && value) {
        const digits = value.replace(/\D/g, "");
        if (!digits || Number(digits) <= 0) return "Сумма должна быть положительным числом.";
      }
      if (rule.minLength && value && value.length < rule.minLength) {
        return `«${rule.label}» — слишком короткое значение.`;
      }
      return null;
    },

    extractionText(value) {
      const v = (value || "").trim();
      if (!v) return "Вставьте текст решения — поле обязательно.";
      if (v.length < 20) return "Слишком короткий текст: минимум 20 символов, иначе извлекать нечего.";
      if (v.length > 50000) return "Текст превышает лимит сервера в 50 000 символов.";
      return null;
    },
  };

  DocForge.Validation = Validation;
})(window.DocForge);
