"use strict";

/**
 * Auth Modal: open/close, login<->register tab switch, password show/hide,
 * and AJAX form submission (login/register never navigate to a full page —
 * see apps/accounts/views.py, which returns JSON when it detects the
 * X-Requested-With header set below). On success we reload the current
 * page (next=request.path) so the header/account state update; on failure
 * we render the returned field errors inline and stay on the modal.
 */
(() => {
  const modal = document.querySelector("[data-login-modal]");
  if (!modal) return; // logged-in users don't get this modal rendered at all

  const panel = modal.querySelector(".login-modal-panel");
  const closeButtons = modal.querySelectorAll("[data-login-close]");
  const openButtons = document.querySelectorAll("[data-login-open]");

  const tabs = modal.querySelectorAll("[data-auth-tab]");
  const authPanels = modal.querySelectorAll("[data-auth-panel]");
  const switchToRegisterLinks = modal.querySelectorAll("[data-switch-to-register]");
  const switchToLoginLinks = modal.querySelectorAll("[data-switch-to-login]");

  let lastFocusedEl = null;

  const focusFirstInput = () => {
    requestAnimationFrame(() => {
      const activePanel = modal.querySelector('[data-auth-panel]:not([hidden])');
      activePanel?.querySelector("input")?.focus();
    });
  };

  const openModal = (tabName) => {
    lastFocusedEl = document.activeElement;
    if (tabName === "login" || tabName === "register") {
      activateTab(tabName);
    }
    modal.classList.add("active");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    focusFirstInput();
  };

  const closeModal = () => {
    modal.classList.remove("active");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    lastFocusedEl?.focus();
  };

  openButtons.forEach((btn) =>
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      openModal(btn.dataset.loginOpen);
    })
  );

  closeButtons.forEach((btn) => btn.addEventListener("click", closeModal));

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal.classList.contains("active")) {
      closeModal();
    }
  });

  panel?.addEventListener("click", (e) => e.stopPropagation());

  const activateTab = (targetName) => {
    tabs.forEach((tab) => {
      const isTarget = tab.dataset.authTab === targetName;
      tab.classList.toggle("active", isTarget);
      tab.setAttribute("aria-selected", isTarget ? "true" : "false");
    });

    authPanels.forEach((p) => {
      const isTarget = p.dataset.authPanel === targetName;
      p.classList.toggle("active", isTarget);
      p.hidden = !isTarget;
    });

    focusFirstInput();
  };

  tabs.forEach((tab) =>
    tab.addEventListener("click", () => activateTab(tab.dataset.authTab))
  );

  switchToRegisterLinks.forEach((link) =>
    link.addEventListener("click", (e) => {
      e.preventDefault();
      activateTab("register");
    })
  );

  switchToLoginLinks.forEach((link) =>
    link.addEventListener("click", (e) => {
      e.preventDefault();
      activateTab("login");
    })
  );

  modal.querySelectorAll("[data-password-toggle]").forEach((btn) => {
    const targetInput = document.getElementById(btn.dataset.target);
    if (!targetInput) return;

    btn.addEventListener("click", () => {
      const isHidden = targetInput.type === "password";
      targetInput.type = isHidden ? "text" : "password";

      btn.setAttribute("aria-pressed", isHidden ? "true" : "false");
      btn.setAttribute("aria-label", isHidden ? "Şifreyi gizle" : "Şifreyi göster");

      const icon = btn.querySelector("i");
      icon?.classList.toggle("fa-eye-slash", isHidden);
      icon?.classList.toggle("fa-eye", !isHidden);
    });
  });

  // --- AJAX form submission (login + register) ---------------------------

  const clearFormErrors = (form) => {
    form.querySelectorAll("[data-field-error]").forEach((el) => {
      el.textContent = "";
    });
    form.querySelectorAll("input.input-error").forEach((el) => {
      el.classList.remove("input-error");
    });
    const formError = form.querySelector("[data-form-error]");
    if (formError) formError.textContent = "";
  };

  const showFormErrors = (form, errors) => {
    Object.entries(errors || {}).forEach(([field, messages]) => {
      const text = Array.isArray(messages) ? messages.join(" ") : String(messages);
      if (field === "__all__") {
        const formError = form.querySelector("[data-form-error]");
        if (formError) formError.textContent = text;
        return;
      }
      const errorEl = form.querySelector(`[data-field-error="${field}"]`);
      if (errorEl) errorEl.textContent = text;
      const input = form.querySelector(`[name="${field}"]`);
      input?.classList.add("input-error");
    });
  };

  // OTP adımında yanlış numara yazan / kodu alamayan kullanıcı geri dönebilsin.
  modal.querySelectorAll("[data-otp-back]").forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const otpForm = link.closest("[data-otp-form]");
      const firstForm = otpForm
        ?.closest("[data-auth-panel]")
        ?.querySelector("form[data-auth-form]:not([data-otp-form])");
      if (!otpForm || !firstForm) return;
      clearFormErrors(otpForm);
      otpForm.setAttribute("hidden", "true");
      firstForm.removeAttribute("hidden");
      firstForm.querySelector("input")?.focus();
    });
  });

  modal.querySelectorAll("form[data-auth-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      clearFormErrors(form);

      const submitBtn = form.querySelector("button[type=submit]");
      submitBtn?.setAttribute("disabled", "true");
      let navigating = false;

      try {
        const response = await fetch(form.action, {
          method: "POST",
          headers: { "X-Requested-With": "XMLHttpRequest" },
          body: new FormData(form),
        });

        // Non-JSON (e.g. an unexpected 500 page) means something on the
        // server broke outside the normal validation flow.
        const contentType = response.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
          throw new Error("unexpected-response");
        }

        const data = await response.json();

        if (data.success && data.step === "verify") {
          // Works for either panel: hide the form that was just submitted
          // (login's phone form, or register's sign-up form) and reveal
          // that same panel's own OTP form.
          const panelEl = form.closest("[data-auth-panel]");
          const otpForm = panelEl?.querySelector("[data-otp-form]");
          form.setAttribute("hidden", "true");
          otpForm?.removeAttribute("hidden");
          const message = otpForm?.querySelector("[data-form-error]");
          if (message) message.textContent = data.message || "Kod WhatsApp'a gönderildi. Lütfen WhatsApp'taki kodu yazın.";
          otpForm?.querySelector("input[name=code]")?.focus();
          return;
        }

        if (data.success) {
          navigating = true;
          window.location.href = data.redirect_url || window.location.href;
          return; // page is navigating away to reload, leave button disabled
        }

        showFormErrors(form, data.errors);
      } catch (err) {
        const formError = form.querySelector("[data-form-error]");
        if (formError) formError.textContent = "Bir şeyler ters gitti, lütfen tekrar deneyin.";
      } finally {
        if (!navigating) submitBtn?.removeAttribute("disabled");
      }
    });
  });

  // Sunucu tarafında beklenmedik bir hata olursa (ör. JS kapalıysa) formlar
  // hâlâ normal <form method="post"> olarak da çalışır — action attribute'u
  // her zaman doğru endpoint'e işaret ediyor, bu script sadece submit'i
  // fetch ile ele alıp sayfa değişimini engelliyor.
})();