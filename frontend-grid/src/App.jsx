import { useEffect, useState, useCallback } from "react";
import Login from "./components/Login";
import FrequenciaGrid from "./components/FrequenciaGrid";
import NotasGrid from "./components/NotasGrid";
import PainelRisco from "./components/PainelRisco";
import MinhasTurmas from "./components/MinhasTurmas";
import { clearToken, getDisciplinas, getMinhasTurmas, getToken } from "./api";

const ABAS = [
  { chave: "frequencia", rotulo: "Frequência" },
  { chave: "notas", rotulo: "Notas" },
  { chave: "risco", rotulo: "Painel de Risco" },
  { chave: "turmas", rotulo: "Minhas Turmas" },
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

  const carregarTudo = useCallback(async () => {
    const [turmasResp, disciplinasResp] = await Promise.all([getMinhasTurmas(), getDisciplinas()]);
    setTurmas(turmasResp);
    const listaDisciplinas = disciplinasResp.results ?? disciplinasResp;
    setDisciplinas(listaDisciplinas);
    // Só define a turma/disciplina padrão se ainda não houver uma selecionada
    // (senão, recarregar depois de criar uma turma nova reverteria a seleção
    // do professor de volta pra primeira da lista toda vez).
    setTurmaId((atual) => atual ?? (turmasResp.length ? turmasResp[0].id : null));
    setDisciplinaId((atual) => atual ?? (listaDisciplinas.length ? listaDisciplinas[0].id : null));
    return turmasResp;
  }, []);

  useEffect(() => {
    if (!logado) { setCarregandoInicial(false); return; }
    let cancelado = false;
    carregarTudo()
      .catch((err) => !cancelado && setErroInicial(err.message))
      .finally(() => !cancelado && setCarregandoInicial(false));
    return () => { cancelado = true; };
  }, [logado, carregarTudo]);

  function handleLogout() {
    clearToken();
    setLogado(false);
    setTurmas([]);
    setDisciplinas([]);
    setTurmaId(null);
    setDisciplinaId(null);
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

      <div className="controles">
        <label>
          Turma
          <select
            value={turmaId ?? ""}
            onChange={(e) => setTurmaId(Number(e.target.value))}
            disabled={turmas.length === 0}
          >
            {turmas.length === 0 && <option value="">Nenhuma turma ainda</option>}
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

      <main>
        {/* As abas ficam sempre montadas, só escondidas com CSS — se
            desmontar ao trocar de aba, o React descarta o estado do
            componente (ex.: a marcação de falta que ainda não foi salva),
            fazendo o trabalho em andamento sumir sem aviso quando o
            professor só dá uma olhada em outra aba. */}
        <div style={{ display: aba === "frequencia" ? "block" : "none" }}>
          {turmaAtual
            ? <FrequenciaGrid turma={turmaAtual} disciplinaId={disciplinaId} bimestre={bimestre} />
            : <p className="dica">Crie uma turma na aba "Minhas Turmas" pra começar.</p>}
        </div>
        <div style={{ display: aba === "notas" ? "block" : "none" }}>
          {turmaAtual
            ? <NotasGrid turma={turmaAtual} disciplinaId={disciplinaId} bimestre={bimestre} />
            : <p className="dica">Crie uma turma na aba "Minhas Turmas" pra começar.</p>}
        </div>
        <div style={{ display: aba === "risco" ? "block" : "none" }}>
          {turmaAtual
            ? <PainelRisco turma={turmaAtual} bimestre={bimestre} />
            : <p className="dica">Crie uma turma na aba "Minhas Turmas" pra começar.</p>}
        </div>
        <div style={{ display: aba === "turmas" ? "block" : "none" }}>
          <MinhasTurmas onTurmasAtualizadas={carregarTudo} />
        </div>
      </main>
    </div>
  );
}
