import { useEffect, useState } from "react";
import { adicionarAlunoNaTurma, criarClassroom, getClassrooms, removerAlunoDaTurma } from "../api";

// Gerenciamento de turma pelo próprio professor: cria a turma (o backend
// já vincula ele mesmo como responsável automaticamente) e adiciona/
// remove aluno digitando o username — de propósito NÃO existe uma lista
// navegável de "todos os alunos do sistema" aqui, pela mesma razão que o
// resto do projeto nunca deixa um professor folhear o cadastro inteiro.
export default function MinhasTurmas({ onTurmasAtualizadas }) {
  const [turmas, setTurmas] = useState(null);
  const [erro, setErro] = useState("");
  const [nomeNovaTurma, setNomeNovaTurma] = useState("");
  const [usernamesPorTurma, setUsernamesPorTurma] = useState({});
  const [statusPorTurma, setStatusPorTurma] = useState({});

  async function recarregar() {
    try {
      const resp = await getClassrooms();
      setTurmas(resp.results ?? resp);
    } catch (err) {
      setErro(err.message);
    }
  }

  useEffect(() => { recarregar(); }, []);

  async function handleCriarTurma(e) {
    e.preventDefault();
    if (!nomeNovaTurma.trim()) return;
    try {
      await criarClassroom(nomeNovaTurma.trim());
      setNomeNovaTurma("");
      await recarregar();
      onTurmasAtualizadas?.();
    } catch (err) {
      setErro(err.message);
    }
  }

  async function handleAdicionar(turmaId) {
    const username = (usernamesPorTurma[turmaId] || "").trim();
    if (!username) return;
    setStatusPorTurma((prev) => ({ ...prev, [turmaId]: null }));
    try {
      await adicionarAlunoNaTurma(turmaId, username);
      setUsernamesPorTurma((prev) => ({ ...prev, [turmaId]: "" }));
      await recarregar();
      onTurmasAtualizadas?.();
    } catch (err) {
      setStatusPorTurma((prev) => ({ ...prev, [turmaId]: err.message }));
    }
  }

  async function handleRemover(turmaId, username) {
    try {
      await removerAlunoDaTurma(turmaId, username);
      await recarregar();
      onTurmasAtualizadas?.();
    } catch (err) {
      setStatusPorTurma((prev) => ({ ...prev, [turmaId]: err.message }));
    }
  }

  if (erro) return <p className="status-msg erro">{erro}</p>;
  if (turmas === null) return <p className="dica">Carregando turmas...</p>;

  return (
    <div className="painel">
      <form className="linha-topo" onSubmit={handleCriarTurma}>
        <label style={{ flex: 1 }}>
          Nova turma
          <input
            type="text" placeholder="Ex.: 7º Ano B"
            value={nomeNovaTurma} onChange={(e) => setNomeNovaTurma(e.target.value)}
          />
        </label>
        <button type="submit" className="btn-primario">Criar turma</button>
      </form>

      {turmas.length === 0 && <p className="dica">Você ainda não leciona nenhuma turma. Crie uma acima.</p>}

      <ul className="lista-turmas">
        {turmas.map((turma) => (
          <li key={turma.id} className="cartao-turma">
            <h3>{turma.name}</h3>
            <ul className="lista-alunos-turma">
              {turma.students_detail.length === 0 && <li className="dica">Nenhum aluno ainda.</li>}
              {turma.students_detail.map((aluno) => (
                <li key={aluno.id}>
                  {aluno.username}
                  <button className="btn-remover" onClick={() => handleRemover(turma.id, aluno.username)}>
                    remover
                  </button>
                </li>
              ))}
            </ul>
            <div className="linha-adicionar">
              <input
                type="text" placeholder="username do aluno"
                value={usernamesPorTurma[turma.id] || ""}
                onChange={(e) => setUsernamesPorTurma((prev) => ({ ...prev, [turma.id]: e.target.value }))}
              />
              <button onClick={() => handleAdicionar(turma.id)}>Adicionar aluno</button>
            </div>
            {statusPorTurma[turma.id] && <p className="status-msg erro">{statusPorTurma[turma.id]}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
