import { useState } from "react";
import { lancarFrequenciaEmLote } from "../api";

// "Lançamento por exceção": todo aluno começa marcado como presente —
// o professor só clica em quem faltou. É bem mais rápido que marcar
// presença um por um numa turma de 30+ alunos.
export default function FrequenciaGrid({ turma, disciplinaId, bimestre }) {
  const [data, setData] = useState(() => new Date().toISOString().slice(0, 10));
  const [ausentes, setAusentes] = useState(new Set());
  const [status, setStatus] = useState(null);
  const [salvando, setSalvando] = useState(false);

  function toggleAusente(alunoId) {
    setAusentes((prev) => {
      const novo = new Set(prev);
      if (novo.has(alunoId)) novo.delete(alunoId);
      else novo.add(alunoId);
      return novo;
    });
  }

  async function salvarChamada() {
    setSalvando(true);
    setStatus(null);
    try {
      const resultado = await lancarFrequenciaEmLote({
        turma: turma.id, disciplina: disciplinaId, data, bimestre,
        ausentes: [...ausentes],
      });
      setStatus({ tipo: "ok", texto: `Chamada salva: ${resultado.presentes} presente(s), ${resultado.ausentes} ausente(s).` });
    } catch (err) {
      setStatus({ tipo: "erro", texto: err.message });
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="painel">
      <div className="linha-topo">
        <label>
          Data da aula
          <input type="date" value={data} onChange={(e) => setData(e.target.value)} />
        </label>
        <button className="btn-primario" onClick={salvarChamada} disabled={salvando}>
          {salvando ? "Salvando..." : "Salvar chamada"}
        </button>
      </div>

      <p className="dica">Todo aluno começa presente — clique em quem faltou.</p>

      <ul className="lista-chamada">
        {turma.students.map((aluno) => {
          const faltou = ausentes.has(aluno.id);
          return (
            <li
              key={aluno.id}
              className={faltou ? "aluno-ausente" : "aluno-presente"}
              onClick={() => toggleAusente(aluno.id)}
            >
              <span className="bolinha" aria-hidden="true">{faltou ? "✕" : "✓"}</span>
              {aluno.username}
              {aluno.matricula && <span className="matricula"> · {aluno.matricula}</span>}
            </li>
          );
        })}
      </ul>

      {status && <p className={`status-msg ${status.tipo}`}>{status.texto}</p>}
    </div>
  );
}
