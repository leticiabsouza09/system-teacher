/**
 * Autenticação do System Teacher — chama a API REST real (os mesmos
 * endpoints /api/auth/login/, /api/auth/register/ já testados via
 * Postman). Token e dados do usuário ficam em localStorage; não há
 * sessão de servidor nem cookie envolvido nesta camada.
 */
const ST = {
  TOKEN_KEY: "st_token",
  USER_KEY: "st_user",

  getToken() {
    return localStorage.getItem(this.TOKEN_KEY);
  },

  getUser() {
    const raw = localStorage.getItem(this.USER_KEY);
    return raw ? JSON.parse(raw) : null;
  },

  setSession(token, user) {
    localStorage.setItem(this.TOKEN_KEY, token);
    localStorage.setItem(this.USER_KEY, JSON.stringify(user));
  },

  logout() {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
    window.location.href = "/";
  },

  /** Redireciona pro dashboard certo conforme o papel do usuário. */
  redirectToDashboard(user) {
    if (user.role === "teacher") {
      window.location.href = "/dashboard/professor/";
    } else if (user.role === "student") {
      window.location.href = "/dashboard/aluno/";
    } else {
      // admin — ainda não tem dashboard próprio nesta versão; usa o Django Admin.
      window.location.href = "/admin/";
    }
  },

  /** fetch autenticado — adiciona o header Token automaticamente. */
  async apiFetch(path, options = {}) {
    const token = this.getToken();
    const headers = Object.assign(
      { "Content-Type": "application/json" },
      token ? { Authorization: `Token ${token}` } : {},
      options.headers || {}
    );
    const resp = await fetch(path, Object.assign({}, options, { headers }));
    if (resp.status === 401) {
      this.logout();
      throw new Error("Sessão expirada.");
    }
    return resp;
  },

  /** Garante que a página atual só é vista por quem está autenticado. */
  requireAuth() {
    if (!this.getToken()) {
      window.location.href = "/";
    }
  },
};

// --- Modais de login/registro (usados na landing page) ---
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-open-modal]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const modal = document.getElementById(`modal-${btn.dataset.openModal}`);
      if (modal) modal.classList.add("open");
    });
  });
  document.querySelectorAll("[data-close-modal]").forEach((btn) => {
    btn.addEventListener("click", () => {
      btn.closest(".modal-backdrop").classList.remove("open");
    });
  });
  document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) backdrop.classList.remove("open");
    });
  });
  document.querySelectorAll("[data-switch-modal]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".modal-backdrop").forEach((m) => m.classList.remove("open"));
      const modal = document.getElementById(`modal-${btn.dataset.switchModal}`);
      if (modal) modal.classList.add("open");
    });
  });
});
