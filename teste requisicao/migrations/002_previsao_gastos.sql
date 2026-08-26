-- ============================================================
-- MIGRATION: PREVISÃO DE GASTOS
-- BLOCO: ESTRUTURA DO BANCO
-- ============================================================
-- Cria somente tabelas novas do módulo. Não altera usuarios, usurod ou req_*.
-- Em produção, executar esta migration antes de habilitar as rotas do módulo.

CREATE TABLE IF NOT EXISTS prev_classificacao (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    nome VARCHAR(120) NOT NULL UNIQUE,
    ativa BOOLEAN NOT NULL DEFAULT TRUE,
    criada_em DATETIME NOT NULL,
    atualizada_em DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS prev_usuario_setor (
    usuario_id INTEGER NOT NULL,
    setor VARCHAR(120) NOT NULL,
    PRIMARY KEY (usuario_id, setor),
    CONSTRAINT fk_prev_usuario_setor_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS prev_gasto (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    setor VARCHAR(120) NOT NULL,
    competencia DATE NOT NULL,
    cia VARCHAR(80),
    fornecedor VARCHAR(180),
    vencimento DATE,
    valor DECIMAL(15,2) NOT NULL DEFAULT 0.00,
    referencia TEXT,
    classificacao_id INTEGER,
    classificacao_nome VARCHAR(120),
    observacao TEXT,
    justificativa_anomalia TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'EM_PREENCHIMENTO',
    criado_por INTEGER NOT NULL,
    criado_em DATETIME NOT NULL,
    atualizado_em DATETIME NOT NULL,
    atualizado_por INTEGER,
    CONSTRAINT fk_prev_gasto_classificacao
        FOREIGN KEY (classificacao_id) REFERENCES prev_classificacao(id),
    CONSTRAINT fk_prev_gasto_criado_por
        FOREIGN KEY (criado_por) REFERENCES usuarios(id),
    CONSTRAINT fk_prev_gasto_atualizado_por
        FOREIGN KEY (atualizado_por) REFERENCES usuarios(id),
    INDEX ix_prev_gasto_setor_competencia (setor, competencia),
    INDEX ix_prev_gasto_cia_classificacao (cia, classificacao_id)
);

CREATE TABLE IF NOT EXISTS prev_historico (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    previsao_id INTEGER NOT NULL,
    usuario_id INTEGER NOT NULL,
    campo VARCHAR(80) NOT NULL,
    valor_anterior TEXT,
    valor_novo TEXT,
    motivo TEXT,
    data_hora DATETIME NOT NULL,
    CONSTRAINT fk_prev_historico_previsao
        FOREIGN KEY (previsao_id) REFERENCES prev_gasto(id) ON DELETE CASCADE,
    CONSTRAINT fk_prev_historico_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    INDEX ix_prev_historico_previsao (previsao_id),
    INDEX ix_prev_historico_usuario (usuario_id)
);

-- ============================================================
-- BLOCO: CATÁLOGO INICIAL
-- ============================================================
-- Dados derivados da planilha fictícia. INSERT IGNORE evita duplicidades.
INSERT IGNORE INTO prev_classificacao (nome, ativa, criada_em, atualizada_em) VALUES
('FORNECEDORES ESTRANGEIROS', TRUE, NOW(), NOW()),
('FORNECEDORES', TRUE, NOW(), NOW()),
('IMPOSTOS', TRUE, NOW(), NOW()),
('FOLHA', TRUE, NOW(), NOW()),
('RESCISÃO (INCLUSIVE DIRETORES)', TRUE, NOW(), NOW()),
('ENCARGOS E BENEFÍCIOS', TRUE, NOW(), NOW()),
('DESPESAS COMERCIAIS', TRUE, NOW(), NOW()),
('BALSAS', TRUE, NOW(), NOW()),
('DESPESAS OPERACIONAIS (GGF + ADM)', TRUE, NOW(), NOW()),
('COMPRA DE ATIVO', TRUE, NOW(), NOW());
