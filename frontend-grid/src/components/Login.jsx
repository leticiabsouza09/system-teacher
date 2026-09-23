import { useState } from "react";
import { login } from "../api";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setErro("");
    setCarregando(true);
    try {
      const user = await login(username, password);
      if (user.role !== "teacher") {
        setErro("Este grid é só para professores.");
        return;
      }
      onLogin(user);
    } catch (err) {
      setErro(err.message || "Usuário ou senha inválidos.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="login-box">
      <h1>System Teacher</h1>
      <p className="sub">Grid de frequência e notas — área do professor</p>
      <form onSubmit={handleSubmit}>
        <label>
          Usuário
          <input value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
        </label>
        <label>
          Senha
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {erro && <p className="erro">{erro}</p>}
        <button type="submit" disabled={carregando}>{carregando ? "Entrando..." : "Entrar"}</button>
      </form>
    </div>
  );
}
