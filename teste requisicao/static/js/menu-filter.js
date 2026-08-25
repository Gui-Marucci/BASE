//  navegação do menu, painel 
document.addEventListener('DOMContentLoaded', function() {
    console.log("Script do Menu Carregado!"); // Se isso aparecer no F12, o arquivo está lido

    const inputMenu = document.getElementById('inputBuscaMenu');
    
    if (inputMenu) {
        inputMenu.addEventListener('input', function() {
            const termo = this.value.toLowerCase();
            const itens = document.querySelectorAll('.nav-item');

            itens.forEach(item => {
                const texto = item.textContent.toLowerCase();
                // Mostra se o texto existir no link, senão esconde
                item.style.display = texto.includes(termo) ? "flex" : "none";
            });
        });
    } else {
        console.error("Erro: Não encontrei o ID 'inputBuscaMenu' no seu HTML!");
    }
});

function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    
    // Alterna as classes que criamos no CSS
    sidebar.classList.toggle('collapsed');
    mainContent.classList.toggle('expanded');
}