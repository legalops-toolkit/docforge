(function (DocForge) {
  "use strict";
  const { Utils } = DocForge;

  const ScrollAnimations = {
    init() {
      this.bindHeaderCondense();
      this.splitHeroHeadline();
      this.bindHeroLoadIn();
      this.bindScrollReveal();
      this.bindSectionRail();
    },

    /* ---- Заголовок hero разбивается на слова для покаскадного проявления ---- */
    splitHeroHeadline() {
      const heading = document.querySelector("[data-split-text]");
      if (!heading) return;
      const words = heading.textContent.trim().split(/\s+/);
      heading.innerHTML = words
        .map((word, i) => `<span class="split-word" style="--word-delay:${60 + i * 45}ms"><span>${word}</span></span>`)
        .join(" ");
    },

    /* ---- Шапка уплотняется по IntersectionObserver, не по scroll-листенеру ---- */
    bindHeaderCondense() {
      const header = document.getElementById("siteHeader");
      const sentinel = document.getElementById("headerSentinel");
      if (!header || !sentinel) return;
      const observer = new IntersectionObserver(
        ([entry]) => header.classList.toggle("is-condensed", !entry.isIntersecting),
        { threshold: 0 }
      );
      observer.observe(sentinel);
    },

    /* ---- Заголовок hero проявляется каскадом сразу после загрузки ---- */
    bindHeroLoadIn() {
      const hero = document.querySelector(".hero");
      if (!hero) return;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => hero.classList.add("is-loaded"));
      });
    },

    /* ---- Универсальный scroll-reveal: [data-reveal] проявляется один раз при входе во вьюпорт ---- */
    bindScrollReveal() {
      const items = Array.from(document.querySelectorAll("[data-reveal]"));
      if (!items.length) return;

      // Внутри общего .reveal-stagger — каскадная задержка по порядку следования.
      document.querySelectorAll(".reveal-stagger").forEach((group) => {
        Array.from(group.children).forEach((child, i) => {
          child.style.setProperty("--reveal-delay", `${Utils.clamp(i, 0, 8) * 80}ms`);
        });
      });

      if (Utils.prefersReducedMotion()) {
        items.forEach((el) => el.classList.add("is-in"));
        return;
      }

      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-in");
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.16, rootMargin: "0px 0px -8% 0px" }
      );
      items.forEach((el) => observer.observe(el));
    },

    /* ---- Боковая шкала «01/04»: текущий смысловой блок + общий прогресс прокрутки ---- */
    bindSectionRail() {
      const rail = document.getElementById("sectionRail");
      if (!rail) return;
      const currentEl = rail.querySelector(".rail-current");
      const totalEl = rail.querySelector(".rail-total");
      const labelEl = rail.querySelector(".rail-label");
      const fillEl = rail.querySelector(".rail-fill");

      const sections = Array.from(document.querySelectorAll("[data-rail-index]"));
      if (!sections.length) return;
      const maxIndex = Math.max(...sections.map((el) => Number(el.dataset.railIndex)));
      Utils.setText(totalEl, String(maxIndex).padStart(2, "0"));

      const setCurrent = (index, label) => {
        Utils.setText(currentEl, String(index).padStart(2, "0"));
        Utils.setText(labelEl, label);
      };
      setCurrent(1, sections[0].dataset.railLabel || "");

      const observer = new IntersectionObserver(
        (entries) => {
          const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
          if (visible) {
            setCurrent(Number(visible.target.dataset.railIndex), visible.target.dataset.railLabel || "");
          }
        },
        { threshold: [0.25, 0.5, 0.75] }
      );
      sections.forEach((el) => observer.observe(el));

      // Прогресс — доля прокрученного документа. transform: scaleY — не триггерит layout.
      let ticking = false;
      const updateProgress = () => {
        const scrollable = document.documentElement.scrollHeight - window.innerHeight;
        const fraction = scrollable > 0 ? Utils.clamp(window.scrollY / scrollable, 0, 1) : 0;
        fillEl.style.setProperty("--rail-progress", fraction.toFixed(4));
        ticking = false;
      };
      window.addEventListener(
        "scroll",
        () => {
          if (!ticking) {
            requestAnimationFrame(updateProgress);
            ticking = true;
          }
        },
        { passive: true }
      );
      updateProgress();
    },
  };

  DocForge.ScrollAnimations = ScrollAnimations;
})(window.DocForge);
