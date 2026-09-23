// Cliente da API — mesmo padrão de token do resto do System Teacher
// (Authorization: Token <valor>, guardado em localStorage).

const TOKEN_KEY = "st_pedagogico_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (token) headers.Authorization = `Token ${token}`;

  const resp = await fetch(`/api${path}`, { ...options, headers });
  if (resp.status === 401) {
    clearToken();
    throw new Error("Sessão expirada — faça login de novo.");
  }
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail || JSON.stringify(data));
  }
  return data;
}

export async function login(username, password) {
  const data = await apiFetch("/auth/login/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setToken(data.token);
  return data.user;
}

export const getMinhasTurmas = () => apiFetch("/pedagogico/minhas-turmas/");
export const getDisciplinas = () => apiFetch("/subjects/");

export const getClassrooms = () => apiFetch("/classrooms/");
export const criarClassroom = (name) =>
  apiFetch("/classrooms/", { method: "POST", body: JSON.stringify({ name }) });
export const adicionarAlunoNaTurma = (turmaId, username) =>
  apiFetch(`/classrooms/${turmaId}/add-student/`, { method: "POST", body: JSON.stringify({ username }) });
export const removerAlunoDaTurma = (turmaId, username) =>
  apiFetch(`/classrooms/${turmaId}/remove-student/`, { method: "POST", body: JSON.stringify({ username }) });

export const getGridNotas = (turmaId, bimestre) =>
  apiFetch(`/pedagogico/notas/grid/?turma=${turmaId}&bimestre=${bimestre}`);

export const salvarGridNotas = (notas) =>
  apiFetch("/pedagogico/notas/grid/", { method: "POST", body: JSON.stringify({ notas }) });

export const lancarFrequenciaEmLote = (payload) =>
  apiFetch("/pedagogico/frequencia/em-lote/", { method: "POST", body: JSON.stringify(payload) });

export const getPainelRisco = (turmaId, bimestre) =>
  apiFetch(`/pedagogico/painel-risco/?turma=${turmaId}&bimestre=${bimestre}`);
