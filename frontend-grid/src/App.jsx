import { useEffect, useState } from "react";
import Login from "./components/Login";
import FrequenciaGrid from "./components/FrequenciaGrid";
import NotasGrid from "./components/NotasGrid";
import PainelRisco from "./components/PainelRisco";
import { clearToken, getDisciplinas, getMinhasTurmas, getToken } from "./api";

const ABAS = [
  { chave: "frequencia", rotulo: "Frequência" },
  { chave: "notas", rotulo: "Notas" },
  { chave: "risco", rotulo: "Painel de Risco" },
];

export default function App() {
  const [logado, setLogado] = useState(!!getToken());
  const [carregandoInicial, setCarregandoInicial] = useState(true);
  const [erroInicial, setErroInicial] = useState("");

  const [turmas, setTurmas] = useState([]);
  const [disciplinas, setDisciplinas] = useState([]);
  const [turmaId, setTurmaId] = useState(null);
  const [disciplinaId, setDisciplinaId] = useState(null);
  const [bimestre, setBimestre] = useState(1);
  const [aba, setAba] = useState("frequencia");

  useEffect(() => {
    if (!logado) { setCarregandoInicial(false); return; }
    let cancelado = false;
    Promise.all([getMinhasTurmas(), getDisciplinas()])
      .then(([turmasResp, disciplinasResp]) => {
        if (cancelado) return;
        setTurmas(turmasResp);
        setDisciplinas(disciplinasResp.results ?? disciplinasResp);
        if (turmasResp.length) setTurmaId(turmasResp[0].id);
        const listaDisciplinas = disciplinasResp.results ?? disciplinasResp;
        if (listaDisciplinas.length) setDisciplinaId(listaDisciplinas[0].id);
      })
      .catch((err) => !cancelado && setErroInicial(err.message))
      .finally(() => !cancelado && setCarregandoInicial(false));
    return () => { cancelado = true; };
  }, [logado]);

  function handleLogout() {
    clearToken();
    setLogado(false);
    setTurmas([]);
    setDisciplinas([]);
  }

  if (!logado) return <Login onLogin={() => setLogado(true)} />;
  if (carregandoInicial) return <p className="dica" style={{ padding: 40 }}>Carregando...</p>;
  if (erroInicial) return <p className="status-msg erro" style={{ margin: 40 }}>{erroInicial}</p>;

  const turmaAtual = turmas.find((t) => t.id === turmaId);

  return (
    <div className="app">
      <header className="topo">
        <h1>System Teacher — Grid do professor</h1>
        <button className="btn-sair" onClick={handleLogout}>Sair</button>
      </header>

      {turmas.length === 0 ? (
        <p className="dica" style={{ padding: 24 }}>
          Você ainda não leciona nenhuma turma vinculada. Peça a um administrador
          para te vincular a uma turma no Django Admin.
        </p>
      ) : (
        <>
          <div className="controles">
            <label>
              Turma
              <select value={turmaId ?? ""} onChange={(e) => setTurmaId(Number(e.target.value))}>
                {turmas.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </label>
            <label>
              Disciplina
              <select value={disciplinaId ?? ""} onChange={(e) => setDisciplinaId(Number(e.target.value))}>
                {disciplinas.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </label>
            <label>
              Bimestre
              <select value={bimestre} onChange={(e) => setBimestre(Number(e.target.value))}>
                {[1, 2, 3, 4].map((b) => <option key={b} value={b}>{b}º bimestre</option>)}
              </select>
            </label>
          </div>

          <nav className="abas">
            {ABAS.map((a) => (
              <button
                key={a.chave}
                className={aba === a.chave ? "aba-ativa" : ""}
                onClick={() => setAba(a.chave)}
              >
                {a.rotulo}
              </button>
            ))}
          </nav>

          {turmaAtual && (
            <main>
              {/* As 3 abas ficam sempre montadas, só escondidas com CSS —
                  se desmontar ao trocar de aba, o React descarta o estado
                  do componente (ex.: a marcação de falta que ainda não foi
                  salva), fazendo o trabalho em andamento sumir sem aviso
                  quando o professor só dá uma olhada em outra aba. */}
              <div style={{ display: aba === "frequencia" ? "block" : "none" }}>
                <FrequenciaGrid turma={turmaAtual} disciplinaId={disciplinaId} bimestre={bimestre} />
              </div>
              <div style={{ display: aba === "notas" ? "block" : "none" }}>
                <NotasGrid turma={turmaAtual} disciplinaId={disciplinaId} bimestre={bimestre} />
              </div>
              <div style={{ display: aba === "risco" ? "block" : "none" }}>
                <PainelRisco turma={turmaAtual} bimestre={bimestre} />
              </div>
            </main>
          )}
        </>
      )}
    </div>
  );
}
