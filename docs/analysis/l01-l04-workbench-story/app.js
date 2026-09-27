(() => {
  "use strict";

  const toast = document.querySelector(".toast");
  let toastTimer;

  function announce(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("is-visible");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 1800);
  }

  document.querySelectorAll("[data-copy-target]").forEach((button) => {
    button.addEventListener("click", async () => {
      const target = document.getElementById(button.dataset.copyTarget);
      if (!target) {
        announce("未找到可复制内容");
        return;
      }

      const text = target.innerText;
      try {
        if (!navigator.clipboard || !window.isSecureContext) throw new Error("clipboard unavailable");
        await navigator.clipboard.writeText(text);
        const original = button.textContent;
        button.textContent = "已复制";
        announce("内容已复制到剪贴板");
        window.setTimeout(() => { button.textContent = original; }, 1600);
      } catch (_error) {
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(target);
        selection.removeAllRanges();
        selection.addRange(range);
        announce("浏览器未开放剪贴板，已选中内容，请手动复制");
      }
    });
  });

  const navLinks = Array.from(document.querySelectorAll(".desktop-nav a"));
  const sections = Array.from(document.querySelectorAll("[data-section]"));

  if ("IntersectionObserver" in window && navLinks.length && sections.length) {
    const observer = new IntersectionObserver(() => {
      const probe = window.innerHeight * 0.25;
      const active = sections.find((section) => {
        const rect = section.getBoundingClientRect();
        return rect.top <= probe && rect.bottom > probe;
      });
      if (!active) return;
      navLinks.forEach((link) => {
        if (link.getAttribute("href") === `#${active.id}`) {
          link.setAttribute("aria-current", "location");
        } else {
          link.removeAttribute("aria-current");
        }
      });
    }, { rootMargin: "-25% 0px -74% 0px", threshold: 0 });
    sections.forEach((section) => observer.observe(section));
  }

  document.querySelectorAll(".mobile-nav a").forEach((link) => {
    link.addEventListener("click", () => {
      const menu = link.closest("details");
      if (menu) menu.open = false;
    });
  });

  document.querySelectorAll("[data-checklist]").forEach((checklist) => {
    const inputs = Array.from(checklist.querySelectorAll('input[type="checkbox"]'));
    const status = checklist.querySelector(".check-status");
    const storageKey = `workbench-story:${checklist.dataset.checklist}`;

    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "[]");
      inputs.forEach((input, index) => { input.checked = Boolean(saved[index]); });
    } catch (_error) {
      // 本地存储不可用时，自测仍可在当前页面内使用。
    }

    const update = () => {
      const checked = inputs.filter((input) => input.checked).length;
      if (status) {
        const suffix = checklist.dataset.checklist === "final"
          ? "这只表示页面内自测，不上传任何数据。"
          : "这只表示页面内自测，不代表课程通过。";
        status.textContent = `已勾选 ${checked} / ${inputs.length}。${suffix}`;
      }
      try {
        localStorage.setItem(storageKey, JSON.stringify(inputs.map((input) => input.checked)));
      } catch (_error) {
        // 不上传、不报错，也不阻断正文阅读。
      }
    };

    inputs.forEach((input) => input.addEventListener("change", update));
    update();
  });
})();
