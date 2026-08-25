/* ==========================================================================
   req-wizard.js — Abrir/Editar Requerimento (7 etapas)
   Depende de req-core.js (window.Req).

   Validação: aqui é apenas experiência de uso. O servidor revalida tudo
   (core/req_service.validar) — o JavaScript nunca é a fonte da verdade.
   ========================================================================== */
(function () {
    "use strict";

    const form = document.getElementById("form-req");
    if (!form) return;

    const CATALOGOS = JSON.parse(document.getElementById("dados-catalogos").textContent || "{}");
    const DOMINIO = JSON.parse(document.getElementById("dados-dominio").textContent || "{}");
    const INICIAL = JSON.parse(document.getElementById("dados-requerimento").textContent || "{}");

    const TOTAL_ETAPAS = (DOMINIO.etapas || []).length || 7;

    const estado = {
        id: form.dataset.reqId ? parseInt(form.dataset.reqId, 10) : null,
        etapa: parseInt(form.dataset.etapaInicial || "1", 10) || 1,
        itens: (INICIAL.itens || []).map(normalizarItem),
        localizacoes: (INICIAL.localizacoes || []).slice(),
        complementos: (INICIAL.complementos || []).slice(),
        cotacoes: (INICIAL.cotacoes || []).slice(),
        anexos: (INICIAL.anexos || []).slice(),
        sujo: false
    };

    function normalizarItem(item) {
        return Object.assign({}, item, {
            quantidade: item.quantidade ?? 1,
            unidade: item.unidade || "UN"
        });
    }

    /* ------------------------------------------------------------------ */
    /* Helpers de catálogo                                                */
    /* ------------------------------------------------------------------ */
    function itensCatalogo(nome) {
        return (CATALOGOS[nome] && CATALOGOS[nome].itens) || [];
    }

    function selectCatalogo(nome, valor, atributos) {
        const opcoes = itensCatalogo(nome).map(function (item) {
            const sel = item.descricao === valor ? " selected" : "";
            return `<option value="${Req.escapar(item.descricao)}"${sel}>` +
                   `${Req.escapar(item.codigo)} — ${Req.escapar(item.descricao)}</option>`;
        });
        const conhecido = itensCatalogo(nome).some((i) => i.descricao === valor);
        if (valor && !conhecido) {
            opcoes.push(`<option value="${Req.escapar(valor)}" selected>${Req.escapar(valor)}</option>`);
        }
        return `<select ${atributos || ""}><option value="">Selecione...</option>${opcoes.join("")}</select>`;
    }

    function selectItens(valor) {
        const opcoes = estado.itens.map(function (item, indice) {
            const seq = indice + 1;
            const sel = String(valor || "") === String(seq) ? " selected" : "";
            const rotulo = `${seq} — ${item.produto_descricao || "(sem descrição)"}`;
            return `<option value="${seq}"${sel}>${Req.escapar(rotulo)}</option>`;
        });
        return `<option value="">Todo o requerimento</option>${opcoes.join("")}`;
    }

    function selectSimples(mapa, valor) {
        return Object.keys(mapa).map(function (chave) {
            const sel = chave === valor ? " selected" : "";
            return `<option value="${chave}"${sel}>${Req.escapar(mapa[chave])}</option>`;
        }).join("");
    }

    /* ------------------------------------------------------------------ */
    /* Renderização das listas dinâmicas                                  */
    /* ------------------------------------------------------------------ */
    function cabecalho(titulo, indice, colecao, extra) {
        return `<div class="linha-cabecalho">
            <span class="linha-titulo"><span class="indice">${indice + 1}</span> ${titulo}</span>
            <span style="display:flex;align-items:center;gap:10px;">
                ${extra || ""}
                <button type="button" class="botao-icone perigo" data-remover="${colecao}" data-indice="${indice}"
                        title="Remover" aria-label="Remover ${titulo} ${indice + 1}">
                    <i data-lucide="trash-2"></i>
                </button>
            </span>
        </div>`;
    }

    function renderItens() {
        const alvo = document.getElementById("lista-itens");
        alvo.innerHTML = estado.itens.map(function (item, i) {
            const total = Req.numero(item.quantidade) * Req.numero(item.valor_referencia);
            return `<div class="linha-dinamica" data-linha="itens" data-indice="${i}">
                ${cabecalho("Item", i, "itens",
                    `<span class="linha-total">${Req.moeda(total)}</span>`)}
                <div class="grade-campos">
                    <div class="campo">
                        <label>Código do produto</label>
                        <input type="text" data-campo="produto_codigo" maxlength="40"
                               value="${Req.escapar(item.produto_codigo || "")}" list="lista-produtos">
                    </div>
                    <div class="campo" style="grid-column: span 2; min-width:0;">
                        <label>Descrição <span class="obrigatorio">*</span></label>
                        <input type="text" data-campo="produto_descricao" maxlength="200" required
                               value="${Req.escapar(item.produto_descricao || "")}">
                    </div>
                    <div class="campo">
                        <label>Quantidade <span class="obrigatorio">*</span></label>
                        <input type="number" step="0.0001" min="0.0001" data-campo="quantidade"
                               value="${item.quantidade ?? ""}">
                    </div>
                    <div class="campo">
                        <label>Unidade</label>
                        ${selectCatalogo("unidades_medida", item.unidade || "UN", 'data-campo="unidade"')}
                    </div>
                    <div class="campo">
                        <label>Valor de referência (R$)</label>
                        <input type="number" step="0.01" min="0" data-campo="valor_referencia"
                               value="${item.valor_referencia ?? ""}">
                    </div>
                    <div class="campo">
                        <label>Data de necessidade</label>
                        <input type="date" data-campo="data_necessidade"
                               value="${item.data_necessidade || ""}">
                    </div>
                    <div class="campo largo">
                        <label>Descrição complementar</label>
                        <textarea data-campo="descricao_complementar" rows="2">${Req.escapar(item.descricao_complementar || "")}</textarea>
                    </div>
                </div>
            </div>`;
        }).join("");

        document.getElementById("vazio-itens").hidden = estado.itens.length > 0;
        atualizarTotais();
    }

    function renderLocalizacoes() {
        const alvo = document.getElementById("lista-localizacoes");
        alvo.innerHTML = estado.localizacoes.map(function (loc, i) {
            return `<div class="linha-dinamica" data-linha="localizacoes" data-indice="${i}">
                ${cabecalho("Localização", i, "localizacoes")}
                <div class="grade-campos">
                    <div class="campo">
                        <label>Item</label>
                        <select data-campo="item_sequencia">${selectItens(loc.item_sequencia)}</select>
                    </div>
                    <div class="campo">
                        <label>Filial</label>
                        ${selectCatalogo("filiais", loc.filial || "", 'data-campo="filial"')}
                    </div>
                    <div class="campo">
                        <label>Almoxarifado</label>
                        ${selectCatalogo("almoxarifados", loc.almoxarifado || "", 'data-campo="almoxarifado"')}
                    </div>
                    <div class="campo">
                        <label>Setor</label>
                        ${selectCatalogo("setores", loc.setor || "", 'data-campo="setor"')}
                    </div>
                    <div class="campo">
                        <label>Local / prédio</label>
                        <input type="text" data-campo="local" maxlength="120" value="${Req.escapar(loc.local || "")}">
                    </div>
                    <div class="campo">
                        <label>Departamento</label>
                        <input type="text" data-campo="departamento" maxlength="80" value="${Req.escapar(loc.departamento || "")}">
                    </div>
                    <div class="campo">
                        <label>Centro de custo</label>
                        ${selectCatalogo("centros_custo", loc.centro_custo || "", 'data-campo="centro_custo"')}
                    </div>
                    <div class="campo">
                        <label>Responsável pelo recebimento</label>
                        <input type="text" data-campo="responsavel_recebimento" maxlength="120"
                               value="${Req.escapar(loc.responsavel_recebimento || "")}">
                    </div>
                    <div class="campo largo">
                        <label>Endereço de entrega</label>
                        <input type="text" data-campo="endereco" maxlength="200" value="${Req.escapar(loc.endereco || "")}">
                    </div>
                    <div class="campo largo">
                        <label>Observação</label>
                        <textarea data-campo="observacao" rows="2">${Req.escapar(loc.observacao || "")}</textarea>
                    </div>
                </div>
            </div>`;
        }).join("");
        document.getElementById("vazio-localizacoes").hidden = estado.localizacoes.length > 0;
    }

    function renderComplementos() {
        const alvo = document.getElementById("lista-complementos");
        const tipos = DOMINIO.tipos_movimento || {};
        alvo.innerHTML = estado.complementos.map(function (comp, i) {
            return `<div class="linha-dinamica" data-linha="complementos" data-indice="${i}">
                ${cabecalho("Registro", i, "complementos")}
                <div class="grade-campos">
                    <div class="campo">
                        <label>Tipo de movimento</label>
                        <select data-campo="tipo_movimento">
                            <option value="">Selecione...</option>
                            ${selectSimples(tipos, comp.tipo_movimento || "")}
                        </select>
                    </div>
                    <div class="campo">
                        <label>Item</label>
                        <select data-campo="item_sequencia">${selectItens(comp.item_sequencia)}</select>
                    </div>
                    <div class="campo">
                        <label>Documento de origem</label>
                        <input type="text" data-campo="documento_origem" maxlength="60"
                               value="${Req.escapar(comp.documento_origem || "")}">
                    </div>
                    <div class="campo">
                        <label>Quantidade</label>
                        <input type="number" step="0.0001" min="0" data-campo="quantidade"
                               value="${comp.quantidade ?? ""}">
                    </div>
                    <div class="campo">
                        <label>Data do movimento</label>
                        <input type="date" data-campo="data_movimento" value="${comp.data_movimento || ""}">
                    </div>
                    <div class="campo">
                        <label>Almoxarifado</label>
                        ${selectCatalogo("almoxarifados", comp.almoxarifado || "", 'data-campo="almoxarifado"')}
                    </div>
                    <div class="campo largo">
                        <div class="linha-checkbox">
                            <input type="checkbox" data-campo="confirmado" id="conf-${i}"
                                   ${comp.confirmado ? "checked" : ""}>
                            <label for="conf-${i}">Movimento confirmado</label>
                        </div>
                    </div>
                    <div class="campo largo">
                        <label>Observação</label>
                        <textarea data-campo="observacao" rows="2">${Req.escapar(comp.observacao || "")}</textarea>
                    </div>
                </div>
            </div>`;
        }).join("");
        document.getElementById("vazio-complementos").hidden = estado.complementos.length > 0;
    }

    function renderCotacoes() {
        const alvo = document.getElementById("lista-cotacoes");
        const precos = estado.cotacoes.map((c) => Req.numero(c.quantidade) * Req.numero(c.preco_unitario));
        const menor = precos.length ? Math.min.apply(null, precos.filter((v) => v > 0)) : null;
        const prazos = estado.cotacoes
            .map((c) => (c.prazo_entrega_dias === "" || c.prazo_entrega_dias === null ? null : parseInt(c.prazo_entrega_dias, 10)))
            .filter((v) => v !== null && !isNaN(v));
        const melhorPrazo = prazos.length ? Math.min.apply(null, prazos) : null;

        alvo.innerHTML = estado.cotacoes.map(function (cot, i) {
            const total = Req.numero(cot.quantidade) * Req.numero(cot.preco_unitario);
            const marcas = [];
            if (menor !== null && total === menor && total > 0) {
                marcas.push('<span class="badge-status" style="--badge-cor:#10b981;"><i data-lucide="trending-down"></i>Menor preço</span>');
            }
            if (melhorPrazo !== null && parseInt(cot.prazo_entrega_dias, 10) === melhorPrazo) {
                marcas.push('<span class="badge-status" style="--badge-cor:#14B1E7;"><i data-lucide="timer"></i>Melhor prazo</span>');
            }
            return `<div class="linha-dinamica ${cot.selecionada ? "selecionada" : ""}"
                         data-linha="cotacoes" data-indice="${i}">
                ${cabecalho("Cotação", i, "cotacoes",
                    marcas.join(" ") + `<span class="linha-total">${Req.moeda(total)}</span>`)}
                <div class="grade-campos">
                    <div class="campo" style="grid-column: span 2; min-width:0;">
                        <label>Fornecedor <span class="obrigatorio">*</span></label>
                        <input type="text" data-campo="fornecedor" maxlength="150" list="lista-fornecedores"
                               value="${Req.escapar(cot.fornecedor || "")}">
                    </div>
                    <div class="campo">
                        <label>CNPJ / CPF</label>
                        <input type="text" data-campo="fornecedor_documento" maxlength="20"
                               value="${Req.escapar(cot.fornecedor_documento || "")}">
                    </div>
                    <div class="campo">
                        <label>Item</label>
                        <select data-campo="item_sequencia">${selectItens(cot.item_sequencia)}</select>
                    </div>
                    <div class="campo">
                        <label>Quantidade <span class="obrigatorio">*</span></label>
                        <input type="number" step="0.0001" min="0.0001" data-campo="quantidade"
                               value="${cot.quantidade ?? 1}">
                    </div>
                    <div class="campo">
                        <label>Preço unitário (R$) <span class="obrigatorio">*</span></label>
                        <input type="number" step="0.0001" min="0" data-campo="preco_unitario"
                               value="${cot.preco_unitario ?? ""}">
                    </div>
                    <div class="campo">
                        <label>Prazo de entrega (dias)</label>
                        <input type="number" min="0" step="1" data-campo="prazo_entrega_dias"
                               value="${cot.prazo_entrega_dias ?? ""}">
                    </div>
                    <div class="campo">
                        <label>Validade da proposta</label>
                        <input type="date" data-campo="validade" value="${cot.validade || ""}">
                    </div>
                    <div class="campo">
                        <label>Condição de pagamento</label>
                        ${selectCatalogo("condicoes_pagamento", cot.condicao_pagamento || "", 'data-campo="condicao_pagamento"')}
                    </div>
                    <div class="campo largo">
                        <div class="linha-checkbox">
                            <input type="radio" name="cotacao-vencedora" id="venc-${i}"
                                   data-selecionar="${i}" ${cot.selecionada ? "checked" : ""}>
                            <label for="venc-${i}">Fornecedor vencedor (escolha manual)</label>
                        </div>
                    </div>
                    <div class="campo largo">
                        <label>Observação</label>
                        <textarea data-campo="observacao" rows="2">${Req.escapar(cot.observacao || "")}</textarea>
                    </div>
                </div>
            </div>`;
        }).join("");
        document.getElementById("vazio-cotacoes").hidden = estado.cotacoes.length > 0;
        atualizarTotais();
    }

    function renderAnexos() {
        const alvo = document.getElementById("lista-anexos");
        alvo.innerHTML = estado.anexos.map(function (anexo) {
            const url = `/requerimento/${estado.id}/anexo/${anexo.id}`;
            return `<div class="item-anexo">
                <span class="icone"><i data-lucide="file-text"></i></span>
                <span class="dados">
                    <span class="nome">${Req.escapar(anexo.nome_original)}</span>
                    <span class="meta">${Req.escapar(anexo.tamanho_legivel || "")} ·
                        enviado por ${Req.escapar(anexo.enviado_por || "—")}</span>
                </span>
                <a class="botao-icone" href="${url}" title="Baixar"><i data-lucide="download"></i></a>
                <button type="button" class="botao-icone perigo" data-remover-anexo="${anexo.id}" title="Remover">
                    <i data-lucide="trash-2"></i>
                </button>
            </div>`;
        }).join("");
        document.getElementById("vazio-anexos").hidden = estado.anexos.length > 0;
        if (window.lucide) lucide.createIcons();
    }

    function atualizarTotais() {
        const totalItens = estado.itens.reduce(function (soma, item) {
            return soma + Req.numero(item.quantidade) * Req.numero(item.valor_referencia);
        }, 0);
        document.getElementById("total-itens").textContent = Req.moeda(totalItens);

        const selecionada = estado.cotacoes.filter((c) => c.selecionada);
        const base = selecionada.length ? selecionada : [];
        const totalCot = base.reduce(function (soma, c) {
            return soma + Req.numero(c.quantidade) * Req.numero(c.preco_unitario);
        }, 0);
        document.getElementById("total-cotacoes").textContent = Req.moeda(totalCot);
    }

    function renderTudo() {
        renderItens();
        renderLocalizacoes();
        renderComplementos();
        renderCotacoes();
        renderAnexos();
        if (window.lucide) lucide.createIcons();
    }

    /* ------------------------------------------------------------------ */
    /* Coleta de dados                                                    */
    /* ------------------------------------------------------------------ */
    function valor(id) {
        const el = document.getElementById(id);
        if (!el) return null;
        return el.type === "checkbox" ? el.checked : el.value;
    }

    function coletar() {
        return {
            geral: {
                tipo: valor("tipo"),
                prioridade: valor("prioridade"),
                data_referencia: valor("data_referencia"),
                data_limite: valor("data_limite"),
                tipo_requisicao: valor("tipo_requisicao"),
                solicitante_nome: valor("solicitante_nome"),
                solicitante_email: valor("solicitante_email"),
                solicitante_telefone: valor("solicitante_telefone"),
                funcionario: valor("funcionario"),
                filial: valor("filial"),
                setor: valor("setor"),
                responsavel: valor("responsavel"),
                unidade_negocio: valor("unidade_negocio"),
                centro_gasto: valor("centro_gasto"),
                centro_custo: valor("centro_custo"),
                classe_sintetica: valor("classe_sintetica"),
                classe_analitica: valor("classe_analitica"),
                categoria: valor("categoria"),
                justificativa: valor("justificativa"),
                observacao: valor("observacao"),
                necessita_cotacao: valor("necessita_cotacao")
            },
            itens: estado.itens,
            localizacoes: estado.localizacoes,
            complementos: estado.complementos,
            cotacoes: estado.cotacoes,
            etapa_atual: estado.etapa
        };
    }

    /* Sincroniza edições feitas nas linhas dinâmicas com o estado */
    form.addEventListener("input", function (ev) {
        const linha = ev.target.closest("[data-linha]");
        if (linha && ev.target.dataset.campo) {
            const colecao = linha.dataset.linha;
            const indice = parseInt(linha.dataset.indice, 10);
            const campo = ev.target.dataset.campo;
            const registro = estado[colecao][indice];
            if (!registro) return;
            registro[campo] = ev.target.type === "checkbox" ? ev.target.checked : ev.target.value;

            if (colecao === "itens" && (campo === "quantidade" || campo === "valor_referencia")) {
                atualizarLinhaTotal(linha, registro.quantidade, registro.valor_referencia);
                atualizarTotais();
            }
            if (colecao === "cotacoes" && (campo === "quantidade" || campo === "preco_unitario")) {
                atualizarLinhaTotal(linha, registro.quantidade, registro.preco_unitario);
                atualizarTotais();
            }
            if (colecao === "itens" && campo === "produto_codigo") preencherPorCodigo(registro, linha);
        }
        estado.sujo = true;
        marcarNaoSalvo();
    });

    function atualizarLinhaTotal(linha, a, b) {
        const alvo = linha.querySelector(".linha-total");
        if (alvo) alvo.textContent = Req.moeda(Req.numero(a) * Req.numero(b));
    }

    function preencherPorCodigo(registro, linha) {
        const produto = itensCatalogo("produtos").find(
            (p) => String(p.codigo).toUpperCase() === String(registro.produto_codigo || "").toUpperCase()
        );
        if (!produto) return;
        registro.produto_descricao = produto.descricao;
        registro.unidade = produto.unidade || registro.unidade;
        const campoDesc = linha.querySelector('[data-campo="produto_descricao"]');
        const campoUn = linha.querySelector('[data-campo="unidade"]');
        if (campoDesc) campoDesc.value = produto.descricao;
        if (campoUn) campoUn.value = registro.unidade;
    }

    /* Adicionar / remover linhas */
    form.addEventListener("click", function (ev) {
        const adicionar = ev.target.closest("[data-adicionar]");
        if (adicionar) {
            const colecao = adicionar.dataset.adicionar;
            const novos = {
                itens: { produto_codigo: "", produto_descricao: "", quantidade: 1, unidade: "UN" },
                localizacoes: { item_sequencia: "", filial: document.getElementById("filial").value || "" },
                complementos: { tipo_movimento: "", item_sequencia: "" },
                cotacoes: { fornecedor: "", quantidade: 1, preco_unitario: "" }
            };
            estado[colecao].push(Object.assign({}, novos[colecao]));
            renderTudo();
            const linhas = document.querySelectorAll(`[data-linha="${colecao}"]`);
            const ultima = linhas[linhas.length - 1];
            if (ultima) {
                ultima.scrollIntoView({ behavior: "smooth", block: "center" });
                const primeiro = ultima.querySelector("input, select");
                if (primeiro) primeiro.focus();
            }
            estado.sujo = true;
            return;
        }

        const remover = ev.target.closest("[data-remover]");
        if (remover) {
            const colecao = remover.dataset.remover;
            const indice = parseInt(remover.dataset.indice, 10);
            estado[colecao].splice(indice, 1);
            renderTudo();
            estado.sujo = true;
            Req.toast("Registro removido da lista.", "info", 2200);
            return;
        }

        const selecionar = ev.target.closest("[data-selecionar]");
        if (selecionar) {
            const indice = parseInt(selecionar.dataset.selecionar, 10);
            estado.cotacoes.forEach((c, i) => { c.selecionada = i === indice; });
            renderCotacoes();
            if (window.lucide) lucide.createIcons();
            estado.sujo = true;
            return;
        }

        const removerAnexo = ev.target.closest("[data-remover-anexo]");
        if (removerAnexo) {
            excluirAnexo(parseInt(removerAnexo.dataset.removerAnexo, 10));
        }
    });

    /* ------------------------------------------------------------------ */
    /* Navegação entre etapas                                             */
    /* ------------------------------------------------------------------ */
    function irPara(n, silencioso) {
        estado.etapa = Math.min(Math.max(n, 1), TOTAL_ETAPAS);

        document.querySelectorAll(".etapa").forEach(function (secao) {
            secao.classList.toggle("ativa", parseInt(secao.dataset.etapa, 10) === estado.etapa);
        });
        document.querySelectorAll(".step").forEach(function (passo) {
            const numero = parseInt(passo.dataset.etapa, 10);
            passo.classList.toggle("ativa", numero === estado.etapa);
            passo.setAttribute("aria-selected", numero === estado.etapa ? "true" : "false");
        });

        const pct = (estado.etapa / TOTAL_ETAPAS) * 100;
        document.getElementById("progresso").style.width = pct + "%";
        document.getElementById("progresso-texto").textContent =
            `Etapa ${estado.etapa} de ${TOTAL_ETAPAS}`;

        document.getElementById("btn-voltar").disabled = estado.etapa === 1;
        document.getElementById("btn-proximo").hidden = estado.etapa === TOTAL_ETAPAS;
        document.getElementById("btn-enviar").hidden = estado.etapa !== TOTAL_ETAPAS;

        if (estado.etapa === TOTAL_ETAPAS) montarRevisao();
        if (estado.etapa === 5 && !estado.id) {
            Req.toast("Salve o rascunho para habilitar o envio de anexos.", "alerta", 5000);
        }
        if (!silencioso) window.scrollTo({ top: 0, behavior: "smooth" });
        if (window.lucide) lucide.createIcons();
    }

    document.querySelectorAll(".step").forEach(function (passo) {
        passo.addEventListener("click", function () {
            irPara(parseInt(passo.dataset.etapa, 10));
        });
    });

    document.getElementById("btn-voltar").addEventListener("click", function () {
        irPara(estado.etapa - 1);
    });

    document.getElementById("btn-proximo").addEventListener("click", async function () {
        if (!validarEtapaAtual()) return;
        const ok = await salvar({ silencioso: true });
        if (ok !== false) irPara(estado.etapa + 1);
    });

    /* ------------------------------------------------------------------ */
    /* Validação de tela (o servidor revalida)                            */
    /* ------------------------------------------------------------------ */
    const OBRIGATORIOS_GERAL = [
        ["tipo", "Selecione o tipo do requerimento."],
        ["solicitante_nome", "Informe o solicitante."],
        ["solicitante_email", "Informe o e-mail do solicitante."],
        ["filial", "Selecione a filial."],
        ["setor", "Selecione o setor."],
        ["centro_custo", "Selecione o centro de custo."],
        ["data_limite", "Informe a data limite de entrega."]
    ];

    function validarEtapaAtual() {
        Req.limparErros(form);
        const problemas = [];

        if (estado.etapa === 1) {
            OBRIGATORIOS_GERAL.forEach(function ([id, mensagem]) {
                const el = document.getElementById(id);
                if (el && !String(el.value || "").trim()) {
                    Req.marcarErro(el, mensagem);
                    problemas.push(mensagem);
                }
            });
            const email = document.getElementById("solicitante_email");
            if (email.value && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.value)) {
                Req.marcarErro(email, "E-mail inválido.");
                problemas.push("E-mail do solicitante inválido.");
            }
            const just = document.getElementById("justificativa");
            if (String(just.value || "").trim().length < 10) {
                Req.marcarErro(just, "Descreva a justificativa com pelo menos 10 caracteres.");
                problemas.push("Justificativa muito curta.");
            }
            const ref = document.getElementById("data_referencia").value;
            const lim = document.getElementById("data_limite").value;
            if (ref && lim && lim < ref) {
                Req.marcarErro(document.getElementById("data_limite"),
                    "A data limite não pode ser anterior à data de referência.");
                problemas.push("Data limite anterior à data de referência.");
            }
        }

        if (estado.etapa === 2) {
            if (!estado.itens.length) problemas.push("Adicione pelo menos um item.");
            estado.itens.forEach(function (item, i) {
                const linha = document.querySelector(`[data-linha="itens"][data-indice="${i}"]`);
                if (!String(item.produto_descricao || "").trim()) {
                    Req.marcarErro(linha.querySelector('[data-campo="produto_descricao"]'), "Obrigatório.");
                    problemas.push(`Item ${i + 1}: informe a descrição.`);
                }
                if (Req.numero(item.quantidade) <= 0) {
                    Req.marcarErro(linha.querySelector('[data-campo="quantidade"]'), "Deve ser maior que zero.");
                    problemas.push(`Item ${i + 1}: quantidade deve ser maior que zero.`);
                }
            });
        }

        if (estado.etapa === 6) {
            estado.cotacoes.forEach(function (cot, i) {
                const linha = document.querySelector(`[data-linha="cotacoes"][data-indice="${i}"]`);
                if (!String(cot.fornecedor || "").trim()) {
                    Req.marcarErro(linha.querySelector('[data-campo="fornecedor"]'), "Obrigatório.");
                    problemas.push(`Cotação ${i + 1}: informe o fornecedor.`);
                }
                if (Req.numero(cot.quantidade) <= 0) {
                    Req.marcarErro(linha.querySelector('[data-campo="quantidade"]'), "Deve ser maior que zero.");
                    problemas.push(`Cotação ${i + 1}: quantidade inválida.`);
                }
            });
        }

        if (problemas.length) {
            Req.toast(problemas[0] + (problemas.length > 1 ? ` (+${problemas.length - 1} pendência(s))` : ""), "erro");
            const primeiro = form.querySelector('[aria-invalid="true"]');
            if (primeiro) primeiro.focus();
            return false;
        }
        return true;
    }

    /* ------------------------------------------------------------------ */
    /* Salvamento                                                         */
    /* ------------------------------------------------------------------ */
    function marcarSalvo() {
        const el = document.getElementById("estado-salvamento");
        const agora = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
        el.innerHTML = `<i data-lucide="check"></i> Rascunho salvo às ${agora}`;
        estado.sujo = false;
        if (window.lucide) lucide.createIcons();
    }

    function marcarNaoSalvo() {
        const el = document.getElementById("estado-salvamento");
        if (estado.sujo && el.dataset.pendente !== "1") {
            el.dataset.pendente = "1";
            el.innerHTML = '<i data-lucide="circle-dot"></i> Alterações não salvas';
            if (window.lucide) lucide.createIcons();
        }
    }

    async function salvar(opcoes) {
        opcoes = opcoes || {};
        const dados = coletar();
        const botoes = form.querySelectorAll(".wizard-rodape .btn");
        botoes.forEach((b) => (b.disabled = true));

        try {
            let resposta;
            if (estado.id) {
                resposta = await Req.api(`/api/requerimentos/${estado.id}`, { method: "PUT", corpo: dados });
            } else {
                resposta = await Req.api("/api/requerimentos", { method: "POST", corpo: dados });
                estado.id = resposta.id;
                form.dataset.reqId = resposta.id;
                history.replaceState(null, "", `/requerimento/${resposta.id}/editar`);
                const codigo = document.getElementById("codigo");
                if (resposta.requerimento && resposta.requerimento.codigo) {
                    codigo.value = resposta.requerimento.codigo;
                }
            }
            document.getElementById("estado-salvamento").dataset.pendente = "0";
            marcarSalvo();
            if (!opcoes.silencioso) Req.toast("Rascunho salvo com sucesso.", "sucesso");
            return true;
        } catch (erro) {
            Req.toast(erro.erro || "Não foi possível salvar o rascunho.", "erro", 6000);
            return false;
        } finally {
            botoes.forEach((b) => (b.disabled = false));
            document.getElementById("btn-voltar").disabled = estado.etapa === 1;
        }
    }

    document.getElementById("btn-rascunho").addEventListener("click", function () { salvar(); });

    /* ------------------------------------------------------------------ */
    /* Revisão + envio                                                    */
    /* ------------------------------------------------------------------ */
    function linhaRevisao(rotulo, texto) {
        return `<div class="revisao-item"><label>${rotulo}</label>
                <span>${Req.escapar(texto || "—")}</span></div>`;
    }

    function montarRevisao() {
        const g = coletar().geral;
        const tiposLabel = {};
        document.querySelectorAll("#tipo option").forEach((o) => (tiposLabel[o.value] = o.textContent.trim()));
        const totalItens = estado.itens.reduce(
            (s, i) => s + Req.numero(i.quantidade) * Req.numero(i.valor_referencia), 0);

        let html = `<div class="revisao-secao">
            <div class="cartao-cabecalho"><h3><i data-lucide="file-plus"></i> Geral</h3>
                <button type="button" class="btn btn-neutro btn-pequeno" data-ir="1">
                    <i data-lucide="pencil"></i> Editar</button></div>
            <div class="revisao-grade">
                ${linhaRevisao("Tipo", tiposLabel[g.tipo] || g.tipo)}
                ${linhaRevisao("Prioridade", document.getElementById("prioridade").selectedOptions[0].textContent.trim())}
                ${linhaRevisao("Data de referência", Req.dataBR(g.data_referencia))}
                ${linhaRevisao("Data limite", Req.dataBR(g.data_limite))}
                ${linhaRevisao("Solicitante", g.solicitante_nome)}
                ${linhaRevisao("E-mail", g.solicitante_email)}
                ${linhaRevisao("Filial", g.filial)}
                ${linhaRevisao("Setor", g.setor)}
                ${linhaRevisao("Centro de custo", g.centro_custo)}
                ${linhaRevisao("Categoria", g.categoria)}
                ${linhaRevisao("Necessita cotação", g.necessita_cotacao ? "Sim" : "Não")}
            </div>
            <div class="revisao-grade" style="margin-top:12px;">
                ${linhaRevisao("Justificativa", g.justificativa)}
            </div>
        </div>`;

        html += `<div class="revisao-secao">
            <div class="cartao-cabecalho"><h3><i data-lucide="package"></i> Itens (${estado.itens.length})</h3>
                <button type="button" class="btn btn-neutro btn-pequeno" data-ir="2">
                    <i data-lucide="pencil"></i> Editar</button></div>`;
        if (estado.itens.length) {
            html += `<div class="tabela-wrapper"><table class="tabela"><thead><tr>
                <th>#</th><th>Produto</th><th class="numerico">Qtde</th><th>Un.</th>
                <th class="numerico">Vl. ref.</th><th class="numerico">Total</th></tr></thead><tbody>`;
            estado.itens.forEach(function (item, i) {
                const total = Req.numero(item.quantidade) * Req.numero(item.valor_referencia);
                html += `<tr><td>${i + 1}</td>
                    <td class="celula-truncada" title="${Req.escapar(item.produto_descricao)}">
                        ${Req.escapar(item.produto_descricao)}</td>
                    <td class="numerico">${Req.decimal(item.quantidade, 2)}</td>
                    <td>${Req.escapar(item.unidade)}</td>
                    <td class="numerico">${item.valor_referencia ? Req.moeda(item.valor_referencia) : "—"}</td>
                    <td class="numerico">${Req.moeda(total)}</td></tr>`;
            });
            html += `</tbody></table></div>
                <div class="resumo-total"><span>Valor estimado</span><strong>${Req.moeda(totalItens)}</strong></div>`;
        } else {
            html += `<p style="color:#b91c1c;font-size:.85rem;margin:0;">Nenhum item adicionado.</p>`;
        }
        html += `</div>`;

        html += `<div class="revisao-secao">
            <div class="cartao-cabecalho">
                <h3><i data-lucide="map-pin"></i> Localizações (${estado.localizacoes.length})</h3>
                <button type="button" class="btn btn-neutro btn-pequeno" data-ir="3">
                    <i data-lucide="pencil"></i> Editar</button></div>
            <div class="revisao-grade">` +
            (estado.localizacoes.length
                ? estado.localizacoes.map((l, i) => linhaRevisao(
                    "Local " + (i + 1),
                    [l.filial, l.almoxarifado, l.local, l.setor, l.endereco].filter(Boolean).join(" · ")
                  )).join("")
                : `<span style="color:#b91c1c;font-size:.85rem;">Nenhuma localização informada.</span>`) +
            `</div></div>`;

        html += `<div class="revisao-secao">
            <div class="cartao-cabecalho">
                <h3><i data-lucide="clipboard-list"></i> Complementos (${estado.complementos.length})</h3>
                <button type="button" class="btn btn-neutro btn-pequeno" data-ir="4">
                    <i data-lucide="pencil"></i> Editar</button></div>
            <div class="revisao-grade">` +
            (estado.complementos.length
                ? estado.complementos.map((c, i) => linhaRevisao(
                    "Registro " + (i + 1),
                    [(DOMINIO.tipos_movimento || {})[c.tipo_movimento] || c.tipo_movimento,
                     c.documento_origem, c.almoxarifado].filter(Boolean).join(" · ")
                  )).join("")
                : linhaRevisao("Complementos", "Nenhum registro (etapa opcional)")) +
            `</div></div>`;

        html += `<div class="revisao-secao">
            <div class="cartao-cabecalho">
                <h3><i data-lucide="paperclip"></i> Anexos (${estado.anexos.length})</h3>
                <button type="button" class="btn btn-neutro btn-pequeno" data-ir="5">
                    <i data-lucide="pencil"></i> Editar</button></div>
            <div class="revisao-grade">` +
            (estado.anexos.length
                ? estado.anexos.map((a) => linhaRevisao(a.nome_original, a.tamanho_legivel)).join("")
                : linhaRevisao("Anexos", "Nenhum anexo (opcional)")) +
            `</div></div>`;

        const venc = estado.cotacoes.find((c) => c.selecionada);
        html += `<div class="revisao-secao">
            <div class="cartao-cabecalho">
                <h3><i data-lucide="calculator"></i> Cotações (${estado.cotacoes.length})</h3>
                <button type="button" class="btn btn-neutro btn-pequeno" data-ir="6">
                    <i data-lucide="pencil"></i> Editar</button></div>
            <div class="revisao-grade">
                ${linhaRevisao("Fornecedor vencedor", venc ? venc.fornecedor : "Não selecionado")}
                ${linhaRevisao("Total da proposta escolhida",
                    venc ? Req.moeda(Req.numero(venc.quantidade) * Req.numero(venc.preco_unitario)) : "—")}
            </div></div>`;

        document.getElementById("revisao").innerHTML = html;
        if (window.lucide) lucide.createIcons();
    }

    document.getElementById("revisao").addEventListener("click", function (ev) {
        const ir = ev.target.closest("[data-ir]");
        if (ir) irPara(parseInt(ir.dataset.ir, 10));
    });

    document.getElementById("btn-enviar").addEventListener("click", async function () {
        const confirmado = await Req.modal({
            titulo: "Enviar requerimento",
            texto: "Depois do envio o requerimento não pode mais ser editado, apenas acompanhado. Deseja enviar agora?",
            rotuloConfirmar: "Enviar",
            classeConfirmar: "btn-sucesso"
        });
        if (!confirmado) return;

        const botoes = form.querySelectorAll(".wizard-rodape .btn");
        botoes.forEach((b) => (b.disabled = true));
        try {
            if (!estado.id) {
                const ok = await salvar({ silencioso: true });
                if (!ok) return;
            }
            const resposta = await Req.api(`/api/requerimentos/${estado.id}/enviar`,
                { method: "POST", corpo: coletar() });
            Req.toast(`Requerimento ${resposta.codigo} enviado.`, "sucesso");
            estado.sujo = false;
            setTimeout(() => (window.location.href = resposta.url_detalhe), 700);
        } catch (erro) {
            Req.toast(erro.erro || "Não foi possível enviar o requerimento.", "erro", 7000);
            if (erro.campos) {
                Object.keys(erro.campos).forEach(function (campo) {
                    const el = document.getElementById(campo);
                    if (el) Req.marcarErro(el, erro.campos[campo]);
                });
            }
        } finally {
            botoes.forEach((b) => (b.disabled = false));
            document.getElementById("btn-voltar").disabled = estado.etapa === 1;
        }
    });

    document.getElementById("btn-cancelar").addEventListener("click", async function () {
        if (!estado.id) {
            const sair = await Req.confirmar(
                "Descartar este requerimento? Nada foi salvo ainda.", "Cancelar requerimento");
            if (sair) { estado.sujo = false; window.location.href = "/requerimento"; }
            return;
        }
        const motivo = await Req.modal({
            titulo: "Cancelar requerimento",
            texto: "O requerimento será marcado como cancelado e mantido no histórico (nada é apagado).",
            html: '<div class="campo"><label for="motivo">Motivo do cancelamento</label>' +
                  '<textarea id="motivo" data-retorno rows="3" placeholder="Ex.: solicitado em duplicidade"></textarea></div>',
            rotuloConfirmar: "Cancelar requerimento",
            classeConfirmar: "btn-perigo",
            rotuloCancelar: "Voltar"
        });
        if (!motivo) return;
        try {
            await Req.api(`/api/requerimentos/${estado.id}/cancelar`,
                { method: "POST", corpo: { motivo: typeof motivo === "string" ? motivo : "" } });
            Req.toast("Requerimento cancelado.", "sucesso");
            estado.sujo = false;
            setTimeout(() => (window.location.href = `/requerimento/${estado.id}`), 600);
        } catch (erro) {
            Req.toast(erro.erro || "Não foi possível cancelar.", "erro");
        }
    });

    /* ------------------------------------------------------------------ */
    /* Anexos                                                             */
    /* ------------------------------------------------------------------ */
    const areaUpload = document.getElementById("area-upload");
    const inputAnexo = document.getElementById("input-anexo");

    document.getElementById("btn-anexo").addEventListener("click", () => inputAnexo.click());
    inputAnexo.addEventListener("change", () => enviarAnexos(inputAnexo.files));

    ["dragenter", "dragover"].forEach(function (evento) {
        areaUpload.addEventListener(evento, function (ev) {
            ev.preventDefault();
            areaUpload.classList.add("arrastando");
        });
    });
    ["dragleave", "drop"].forEach(function (evento) {
        areaUpload.addEventListener(evento, function (ev) {
            ev.preventDefault();
            areaUpload.classList.remove("arrastando");
        });
    });
    areaUpload.addEventListener("drop", (ev) => enviarAnexos(ev.dataTransfer.files));

    async function enviarAnexos(arquivos) {
        if (!arquivos || !arquivos.length) return;
        if (!estado.id) {
            const ok = await salvar({ silencioso: true });
            if (!ok) {
                Req.toast("Salve o rascunho antes de anexar arquivos.", "alerta");
                return;
            }
        }
        const dados = new FormData();
        Array.from(arquivos).forEach((arquivo) => dados.append("arquivos", arquivo));
        try {
            const resposta = await Req.api(`/api/requerimentos/${estado.id}/anexos`,
                { method: "POST", body: dados });
            estado.anexos = estado.anexos.concat(resposta.anexos);
            renderAnexos();
            Req.toast(resposta.mensagem, "sucesso");
            (resposta.falhas || []).forEach((f) => Req.toast(`${f.arquivo}: ${f.erro}`, "erro", 6000));
        } catch (erro) {
            Req.toast(erro.erro || "Falha no envio do anexo.", "erro", 6000);
        } finally {
            inputAnexo.value = "";
        }
    }

    async function excluirAnexo(id) {
        const ok = await Req.confirmar("Remover este anexo?", "Remover anexo");
        if (!ok) return;
        try {
            await Req.api(`/api/requerimentos/${estado.id}/anexos/${id}`, { method: "DELETE" });
            estado.anexos = estado.anexos.filter((a) => a.id !== id);
            renderAnexos();
            Req.toast("Anexo removido.", "sucesso");
        } catch (erro) {
            Req.toast(erro.erro || "Não foi possível remover o anexo.", "erro");
        }
    }

    /* ------------------------------------------------------------------ */
    /* Busca de produtos no catálogo                                      */
    /* ------------------------------------------------------------------ */
    document.getElementById("btn-buscar-produto").addEventListener("click", async function () {
        const escolha = await Req.modal({
            titulo: "Buscar produto no catálogo",
            html: `<div class="campo">
                     <label for="busca-produto">Código ou descrição</label>
                     <input type="text" id="busca-produto" placeholder="Ex.: papel, toner, P0003">
                   </div>
                   <div id="resultado-produto" style="margin-top:12px;max-height:240px;overflow:auto;"></div>`,
            rotuloConfirmar: "Fechar",
            rotuloCancelar: "Voltar"
        });
        void escolha;
    });

    document.addEventListener("input", Req.debounce(async function (ev) {
        if (ev.target.id !== "busca-produto") return;
        const alvo = document.getElementById("resultado-produto");
        try {
            const resposta = await Req.api("/api/catalogos/produtos?q=" + encodeURIComponent(ev.target.value));
            if (!resposta.itens.length) {
                alvo.innerHTML = '<p style="margin:0;font-size:.84rem;">Nenhum produto encontrado.</p>';
                return;
            }
            alvo.innerHTML = resposta.itens.map(function (p) {
                return `<button type="button" class="btn btn-neutro" style="width:100%;justify-content:flex-start;margin-bottom:6px;"
                        data-produto="${Req.escapar(p.codigo)}" data-descricao="${Req.escapar(p.descricao)}"
                        data-unidade="${Req.escapar(p.unidade || "UN")}">
                        <i data-lucide="plus"></i>
                        <span style="text-align:left;">${Req.escapar(p.codigo)} — ${Req.escapar(p.descricao)}</span>
                        </button>`;
            }).join("");
            if (window.lucide) lucide.createIcons();
        } catch (erro) {
            alvo.innerHTML = '<p style="margin:0;font-size:.84rem;color:#b91c1c;">Falha ao buscar produtos.</p>';
        }
    }, 300));

    document.addEventListener("click", function (ev) {
        const botao = ev.target.closest("[data-produto]");
        if (!botao) return;
        estado.itens.push({
            produto_codigo: botao.dataset.produto,
            produto_descricao: botao.dataset.descricao,
            quantidade: 1,
            unidade: botao.dataset.unidade
        });
        renderItens();
        if (window.lucide) lucide.createIcons();
        estado.sujo = true;
        Req.toast(`Item "${botao.dataset.descricao}" adicionado.`, "sucesso", 2500);
    });

    /* ------------------------------------------------------------------ */
    /* Datalists auxiliares + inicialização                               */
    /* ------------------------------------------------------------------ */
    function montarDatalists() {
        const produtos = itensCatalogo("produtos")
            .map((p) => `<option value="${Req.escapar(p.codigo)}">${Req.escapar(p.descricao)}</option>`).join("");
        const fornecedores = itensCatalogo("fornecedores")
            .map((f) => `<option value="${Req.escapar(f.descricao || f.nome || "")}"></option>`).join("");
        const div = document.createElement("div");
        div.innerHTML = `<datalist id="lista-produtos">${produtos}</datalist>
                         <datalist id="lista-fornecedores">${fornecedores}</datalist>`;
        document.body.appendChild(div);
    }

    window.addEventListener("beforeunload", function (ev) {
        if (estado.sujo) {
            ev.preventDefault();
            ev.returnValue = "";
        }
    });

    montarDatalists();
    renderTudo();
    irPara(estado.etapa, true);
})();
