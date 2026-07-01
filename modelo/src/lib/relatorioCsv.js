// Monta e baixa o relatório de inconsistências em .csv a partir dos `grupos`
// reais do /api/validar (gerado no navegador).
// Separador ";" e BOM UTF-8 para abrir certo no Excel em pt-BR.

const VERSAO_DATA = "23/06/2026";

// Aspas só quando necessário (campo com ; " ou quebra de linha).
function campo(v) {
  const s = String(v ?? "");
  return /[;"\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function linhasDetalhe(grupos) {
  const sev = (s) => (s === "err" ? "Erro" : "Aviso");
  const out = [];
  for (const g of grupos) {
    for (const r of g.rows) {
      out.push([sev(g.sev), g.title, r.loc, r.field, r.problem, r.sug]);
    }
  }
  return out;
}

export function buildRelatorioCsv(contrato, uf, grupos) {
  const detalhe = linhasDetalhe(grupos);
  const linhas = [
    ["Relatório de Inconsistências - Painel de Monitoramento (Anexo V)"],
    ["Contrato", `${contrato.numero} - ${contrato.tipo_contrato}, ${contrato.tranche}`],
    ["UF", `${uf.sigla} (${uf.nome})`],
    ["Versão da planilha", VERSAO_DATA],
    ["Inconsistências neste relatório", String(detalhe.length)],
    [],
    ["Severidade", "Regra", "Linha", "Campo", "Problema", "Sugestão"],
    ...detalhe,
  ];
  return linhas.map((cols) => cols.map(campo).join(";")).join("\r\n");
}

export function baixarRelatorioCsv(contrato, uf, grupos) {
  const csv = buildRelatorioCsv(contrato, uf, grupos);
  // BOM (﻿) para o Excel pt-BR exibir acentos corretamente.
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `relatorio_inconsistencias_${contrato.numero.replace(/[^\w]+/g, "_")}.csv`;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  // Adia a limpeza: revogar o ObjectURL na hora pode cancelar o download.
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 0);
}
