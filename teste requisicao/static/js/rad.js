/* ============================================================
   ARQUITETURA RAD — INTERAÇÃO
   BLOCO: comportamento compartilhado
   OBJETIVO: concentrar pequenas interações da nova casca para evitar
   JavaScript duplicado entre as páginas do MVP.
   ============================================================ */

(function () {
    'use strict';

    // BLOCO: confirmação de ações destrutivas.
    // REGRA: somente elementos explicitamente marcados recebem confirmação.
    document.addEventListener('click', function (evento) {
        const alvo = evento.target.closest('[data-rad-confirm]');
        if (!alvo) return;
        const mensagem = alvo.getAttribute('data-rad-confirm') || 'Confirmar esta ação?';
        if (!window.confirm(mensagem)) evento.preventDefault();
    });
})();
