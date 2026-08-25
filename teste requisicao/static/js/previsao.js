/* ============================================================
   MÓDULO: PREVISÃO DE GASTOS
   BLOCO: INTERAÇÕES
   ============================================================ */

// FUNÇÃO: moedaBR | Formata valores para apresentação brasileira.
function moedaBR(valor){return Number(valor||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});}

// BLOCO: CADASTRO MANUAL | Envia dados e exibe o retorno sem recarregar a página.
document.addEventListener('DOMContentLoaded',()=>{
  const form=document.getElementById('formPrevisao');
  if(form) form.addEventListener('submit',async e=>{
    e.preventDefault();
    const payload=Object.fromEntries(new FormData(form).entries());
    const r=await fetch('/previsao/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await r.json();
    if(!data.ok){alert((data.erros||[]).join('\n')||data.erro||'Não foi possível salvar.');return;}
    if(data.anomalia && data.anomalia.nivel==='ANOMALIA') alert('Atenção: '+data.anomalia.mensagem);
    window.location.href='/previsao/';
  });

  // BLOCO: IMPORTAÇÃO | Primeira etapa somente analisa; a confirmação é separada.
  const imp=document.getElementById('formImportacao');
  if(imp) imp.addEventListener('submit',async e=>{
    e.preventDefault();
    const r=await fetch('/previsao/api/importar',{method:'POST',body:new FormData(imp)});
    const data=await r.json();
    if(!data.ok){alert(data.erro||'Falha na análise.');return;}
    window.previsaoImportacao=data.linhas||[];
    document.getElementById('resultadoImportacao').hidden=false;
    document.getElementById('resumoImportacao').textContent=`${data.resumo.total} registros | ${data.resumo.erros} erros | ${data.resumo.alertas} alertas`;
    document.getElementById('tabelaImportacao').innerHTML=(data.linhas||[]).map(x=>`<tr><td>${x.linha_planilha}</td><td>${x.cia||'—'}</td><td>${x.fornecedor||'—'}</td><td>${x.vencimento||'—'}</td><td>${moedaBR(x.valor)}</td><td>${x.referencia||'—'}</td><td>${x.classificacao||'—'}</td><td class="prev-${String(x.anomalia?.nivel||'normal').toLowerCase()}">${x.anomalia?.mensagem||'Normal'}</td></tr>`).join('');
    document.getElementById('alertasImportacao').innerHTML=(data.alertas||[]).map(x=>`<div class="prev-alerta">Linha ${x.linha}: ${x.mensagem}</div>`).join('')+(data.erros||[]).map(x=>`<div class="prev-erro">Linha ${x.linha}: ${x.mensagem}</div>`).join('');
  });

  // BLOCO: CONFIRMAÇÃO | Só esta ação grava a prévia analisada no banco.
  const confirmar=document.getElementById('confirmarImportacao');
  if(confirmar) confirmar.addEventListener('click',async()=>{
    if(!window.previsaoImportacao?.length){alert('Nenhum dado para confirmar.');return;}
    const r=await fetch('/previsao/api/importar/confirmar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({linhas:window.previsaoImportacao})});
    const data=await r.json();
    if(!data.ok){alert(data.erro||'Importação cancelada.');return;}
    alert(`${data.quantidade} lançamento(s) importado(s) com sucesso.`);window.location.href='/previsao/';
  });
});

// BLOCO: REPLICAÇÃO | O modal nativo é propositalmente simples nesta primeira versão.
async function abrirReplicacao(id){
  const competencia=prompt('Informe a competência destino (AAAA-MM-DD):');
  if(!competencia)return;
  const percentual=prompt('Percentual de reajuste (0 para manter):','0');
  const r=await fetch(`/previsao/api/${id}/replicar`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({competencia,percentual:Number(percentual||0)})});
  const data=await r.json();
  if(r.status===409){if(confirm(data.mensagem+'\n\nCriar mesmo assim?')){const r2=await fetch(`/previsao/api/${id}/replicar`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({competencia,percentual:Number(percentual||0),acao:'criar'})});if(r2.ok)location.reload();}return;}
  if(!data.ok){alert(data.erro||'Falha na replicação.');return;}location.reload();
}
