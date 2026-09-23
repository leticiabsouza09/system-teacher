import { useEffect, useState } from "react";
import { getPainelRisco } from "../api";

export default function PainelRisco({ turma, bimestre }) {
  const [linhas, setLinhas] = useState(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let cancelado = false;
    setLinhas(null);
    setErro("");
    getPainelRisco(turma.id, bimestre)
      .then((dados) => !cancelado && setLinhas(dados))
      .catch((err) => !cancelado && setErro(err.message));
    return () => { cancelado = true; };
  }, [turma.id, bimestre]);

  if (erro) return <p className="status-msg erro">{erro}</p>;
  if (linhas === null) return <p className="dica">Carregando painel...</p>;
  if (linhas.length === 0) return <p className="dica">Nenhum aluno em risco neste bimestre. 🎉</p>;

  return (
    <div className="painel">
      <ul className="lista-risco">
        {linhas.map((l) => (
          <li key={l.aluno_id} className={`risco-${l.nivel_risco}`}>
            <div className="risco-cabecalho">
              <strong>{l.username}</strong>
              {l.matricula && <span className="matricula"> · {l.matricula}</span>}
              <span className={`tag-risco tag-${l.nivel_risco}`}>{l.nivel_risco}</span>
            </div>
            <p className="risco-motivos">{l.alertas}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
