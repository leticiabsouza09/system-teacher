import { useEffect, useRef, useState } from "react";
import { getGridNotas, salvarGridNotas } from "../api";

// Autosave por célula, com debounce — evita salvar a cada tecla digitada,
// mas também não obriga o professor a clicar em "salvar" depois de cada
// aluno. Validação de 0-10 acontece no próprio <input> (client-side) E de
// novo no backend (nunca confia só na validação do navegador).
const DEBOUNCE_MS = 700;

export default function NotasGrid({ turma, disciplinaId, bimestre }) {
  const [notas, setNotas] = useState({}); // { alunoId: valor }
  const [statusPorAluno, setStatusPorAluno] = useState({}); // { alunoId: "salvando"|"ok"|"erro" }
  const [carregando, setCarregando] = useState(true);
  const [erroCarregamento, setErroCarregamento] = useState("");

  useEffect(() => {
    let cancelado = false;
    setCarregando(true);
    setErroCarregamento("");
    getGridNotas(turma.id, bimestre)
      .then((resp) => {
        if (cancelado) return;
        const iniciais = {};
        resp.celulas
          .filter((c) => c.disciplina_id === disciplinaId)
          .forEach((c) => { iniciais[c.aluno_id] = c.nota; });
        setNotas(iniciais);
      })
      .catch((err) => !cancelado && setErroCarregamento(err.message))
      .finally(() => !cancelado && setCarregando(false));
    return () => { cancelado = true; };
  }, [turma.id, disciplinaId, bimestre]);

  const timersRef = useRef({});

  useEffect(() => {
    return () => Object.values(timersRef.current).forEach(clearTimeout);
  }, []);

  function handleChange(alunoId, valorTexto) {
    setNotas((prev) => ({ ...prev, [alunoId]: valorTexto }));
    agendarSalvamento(alunoId, valorTexto);
  }

  function agendarSalvamento(alunoId, valorTexto) {
    clearTimeout(timersRef.current[alunoId]);
    timersRef.current[alunoId] = setTimeout(() => salvarCelula(alunoId, valorTexto), DEBOUNCE_MS);
  }

  async function salvarCelula(alunoId, valorTexto) {
    const nota = parseFloat(valorTexto.replace(",", "."));
    if (valorTexto === "" || Number.isNaN(nota) || nota < 0 || nota > 10) {
      setStatusPorAluno((prev) => ({ ...prev, [alunoId]: valorTexto === "" ? null : "erro" }));
      return;
    }
    setStatusPorAluno((prev) => ({ ...prev, [alunoId]: "salvando" }));
    try {
      await salvarGridNotas([{ aluno_id: alunoId, disciplina_id: disciplinaId, bimestre, nota }]);
      setStatusPorAluno((prev) => ({ ...prev, [alunoId]: "ok" }));
    } catch {
      setStatusPorAluno((prev) => ({ ...prev, [alunoId]: "erro" }));
    }
  }

  if (carregando) return <p className="dica">Carregando notas...</p>;
  if (erroCarregamento) return <p className="status-msg erro">{erroCarregamento}</p>;

  return (
    <div className="painel">
      <p className="dica">A nota salva sozinha ao sair do campo (autosave) — não precisa clicar em nada.</p>
      <table className="grid-notas">
        <thead>
          <tr><th>Aluno</th><th>Nota (0-10)</th><th></th></tr>
        </thead>
        <tbody>
          {turma.students.map((aluno) => {
            const status = statusPorAluno[aluno.id];
            return (
              <tr key={aluno.id}>
                <td>{aluno.username}{aluno.matricula && <span className="matricula"> · {aluno.matricula}</span>}</td>
                <td>
                  <input
                    type="text"
                    inputMode="decimal"
                    className={status === "erro" ? "celula-erro" : ""}
                    value={notas[aluno.id] ?? ""}
                    onChange={(e) => handleChange(aluno.id, e.target.value)}
                    onBlur={(e) => salvarCelula(aluno.id, e.target.value)}
                  />
                </td>
                <td className="celula-status">
                  {status === "salvando" && "salvando..."}
                  {status === "ok" && "✓ salvo"}
                  {status === "erro" && "nota inválida (0-10)"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
