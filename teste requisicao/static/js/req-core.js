/* ==========================================================================
   req-core.js — utilidades compartilhadas do módulo de Requerimentos
   Sem dependências externas (apenas o Lucide já usado no projeto).
   Expõe: window.Req (toast, confirmar, api, moeda, numero, dataBR, escapar)
   Também mantém toggleProfile()/toggleSidebar() funcionando nas telas novas.
   ========================================================================== */
(function () {
    "use strict";

    const Req = {};

    /* ---------------------- Toasts ------------------------------------- */
    const ICONES = {
        sucesso: "circle-check",
        erro: "circle-x",
        alerta: "triangle-alert",
        info: "info"
    };

    Req.toast = function (mensagem, tipo = "info", duracao = 4200) {
        const area = document.getElementById("toast-area");
        if (!area) { console.log(`[${tipo}] ${mensagem}`); return; }

        const el = document.createElement("div");
        el.className = "toast " + tipo;
        el.setAttribute("role", tipo === "erro" ? "alert" : "status");
        el.innerHTML =
            '<i data-lucide="' + (ICONES[tipo] || ICONES.info) + '"></i>' +
            '<div class="texto"></div>';
        el.querySelector(".texto").textContent = mensagem;
        area.appendChild(el);
        if (window.lucide) lucide.createIcons();

        const remover = () => {
            el.classList.add("saindo");
            setTimeout(() => el.remove(), 220);
        };
        el.addEventListener("click", remover);
        setTimeout(remover, duracao);
    };

    /* ---------------------- Modal de confirmação ----------------------- */
    let fecharAtual = null;

    Req.modal = function (opcoes) {
        const host = document.getElementById("modal-host");
        if (!host) return Promise.resolve(window.confirm(opcoes.texto || "Confirmar?"));

        const titulo = document.getElementById("modal-titulo");
        const corpo = document.getElementById("modal-corpo");
        const pe = document.getElementById("modal-pe");

        titulo.textContent = opcoes.titulo || "Confirmação";
        corpo.innerHTML = "";
        if (opcoes.texto) {
            const p = document.createElement("p");
            p.style.margin = "0";
            p.textContent = opcoes.texto;
            corpo.appendChild(p);
        }
        if (opcoes.html) corpo.insertAdjacentHTML("beforeend", opcoes.html);

        pe.innerHTML = "";
        host.hidden = false;
        if (window.lucide) lucide.createIcons();

        return new Promise((resolve) => {
            const encerrar = (valor) => {
                host.hidden = true;
                fecharAtual = null;
                document.removeEventListener("keydown", aoTeclar);
                resolve(valor);
            };
            const aoTeclar = (ev) => { if (ev.key === "Escape") encerrar(null); };
            fecharAtual = () => encerrar(null);
            document.addEventListener("keydown", aoTeclar);

            const btnCancelar = document.createElement("button");
            btnCancelar.type = "button";
            btnCancelar.className = "btn btn-neutro";
            btnCancelar.textContent = opcoes.rotuloCancelar || "Cancelar";
            btnCancelar.onclick = () => encerrar(null);

            const btnOk = document.createElement("button");
            btnOk.type = "button";
            btnOk.className = "btn " + (opcoes.classeConfirmar || "btn-primario");
            btnOk.textContent = opcoes.rotuloConfirmar || "Confirmar";
            btnOk.onclick = () => {
                const campo = corpo.querySelector("[data-retorno]");
                encerrar(campo ? (campo.value || true) : true);
            };

            pe.appendChild(btnCancelar);
            pe.appendChild(btnOk);
            setTimeout(() => (corpo.querySelector("[data-retorno]") || btnOk).focus(), 40);
        });
    };

    Req.confirmar = function (texto, titulo) {
        return Req.modal({ titulo: titulo || "Confirmação", texto: texto });
    };

    document.addEventListener("click", function (ev) {
        if (ev.target.closest("[data-fechar-modal]") && fecharAtual) fecharAtual();
    });

    /* ---------------------- Chamadas à API ----------------------------- */
    Req.api = async function (url, opcoes = {}) {
        const config = { headers: {}, ...opcoes };
        if (config.corpo !== undefined) {
            config.headers["Content-Type"] = "application/json";
            config.body = JSON.stringify(config.corpo);
            delete config.corpo;
        }
        config.headers["X-Requested-With"] = "fetch";

        let resposta;
        try {
            resposta = await fetch(url, config);
        } catch (erro) {
            throw { erro: "Falha de conexão com o servidor. Verifique sua rede." };
        }

        if (resposta.status === 401 || resposta.redirected && resposta.url.includes("/?")) {
            throw { erro: "Sessão expirada. Faça login novamente." };
        }

        let dados = null;
        try { dados = await resposta.json(); } catch (e) { dados = null; }

        if (!resposta.ok || (dados && dados.ok === false)) {
            throw dados || { erro: "Erro inesperado (" + resposta.status + ")." };
        }
        return dados;
    };

    /* ---------------------- Formatação -------------------------------- */
    Req.numero = function (valor) {
        if (valor === null || valor === undefined || valor === "") return 0;
        if (typeof valor === "number") return valor;
        let texto = String(valor).trim().replace(/\s|R\$/g, "");
        if (texto.includes(",")) texto = texto.replace(/\./g, "").replace(",", ".");
        const n = parseFloat(texto);
        return isNaN(n) ? 0 : n;
    };

    Req.moeda = function (valor) {
        return Req.numero(valor).toLocaleString("pt-BR", {
            style: "currency", currency: "BRL", minimumFractionDigits: 2
        });
    };

    Req.decimal = function (valor, casas = 2) {
        return Req.numero(valor).toLocaleString("pt-BR", {
            minimumFractionDigits: casas, maximumFractionDigits: casas
        });
    };

    Req.dataBR = function (iso) {
        if (!iso) return "—";
        const partes = String(iso).slice(0, 10).split("-");
        return partes.length === 3 ? `${partes[2]}/${partes[1]}/${partes[0]}` : iso;
    };

    Req.escapar = function (texto) {
        const div = document.createElement("div");
        div.textContent = texto === null || texto === undefined ? "" : texto;
        return div.innerHTML;
    };

    Req.debounce = function (fn, espera = 300) {
        let id;
        return function (...args) {
            clearTimeout(id);
            id = setTimeout(() => fn.apply(this, args), espera);
        };
    };

    /* ---------------------- Erros de campo ---------------------------- */
    Req.limparErros = function (escopo) {
        (escopo || document).querySelectorAll('[aria-invalid="true"]').forEach((el) => {
            el.removeAttribute("aria-invalid");
        });
        (escopo || document).querySelectorAll(".erro-campo").forEach((el) => el.remove());
    };

    Req.marcarErro = function (elemento, mensagem) {
        if (!elemento) return;
        elemento.setAttribute("aria-invalid", "true");
        const pai = elemento.closest(".campo") || elemento.parentElement;
        if (pai && !pai.querySelector(".erro-campo")) {
            const aviso = document.createElement("small");
            aviso.className = "erro-campo";
            aviso.textContent = mensagem;
            pai.appendChild(aviso);
        }
    };

    window.Req = Req;

    /* ---------------------- Perfil / sidebar -------------------------- */
    if (typeof window.toggleProfile !== "function") {
        window.toggleProfile = function () {
            const menu = document.getElementById("profile-menu");
            if (menu) menu.classList.toggle("active");
        };
    }

    document.addEventListener("click", function (ev) {
        const menu = document.getElementById("profile-menu");
        if (menu && menu.classList.contains("active") && !ev.target.closest(".user-profile-container")) {
            menu.classList.remove("active");
        }
    });

    /* Sidebar: no celular começa recolhida e abre sobreposta ao conteúdo. */
    function ajustarSidebar() {
        const sidebar = document.querySelector(".sidebar");
        const principal = document.querySelector(".main-content");
        if (!sidebar || !principal) return;
        if (window.innerWidth <= 900) {
            sidebar.classList.add("collapsed");
            principal.classList.add("expanded");
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        ajustarSidebar();

        if (!document.querySelector(".scrim-sidebar")) {
            const scrim = document.createElement("div");
            scrim.className = "scrim-sidebar";
            scrim.addEventListener("click", function () {
                const sidebar = document.querySelector(".sidebar");
                const principal = document.querySelector(".main-content");
                if (sidebar) sidebar.classList.add("collapsed");
                if (principal) principal.classList.add("expanded");
                document.body.classList.remove("sidebar-aberta");
            });
            document.body.appendChild(scrim);
        }

        const botaoMenu = document.querySelector('.top-header [data-lucide="menu"]');
        if (botaoMenu) {
            botaoMenu.addEventListener("click", function () {
                const sidebar = document.querySelector(".sidebar");
                const aberta = sidebar && !sidebar.classList.contains("collapsed");
                document.body.classList.toggle("sidebar-aberta", window.innerWidth <= 900 && aberta);
            });
        }
    });

    /* Máscara simples de valores monetários/decimais em campos marcados */
    document.addEventListener("blur", function (ev) {
        const el = ev.target;
        if (!(el instanceof HTMLInputElement)) return;
        if (el.dataset.mascara === "decimal" && el.value !== "") {
            el.value = Req.decimal(el.value, parseInt(el.dataset.casas || "2", 10));
        }
    }, true);
})();
