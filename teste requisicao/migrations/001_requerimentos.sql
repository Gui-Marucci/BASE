-- Migração 001 — módulo de Requerimentos (MySQL 5.7+/8)
-- Gerada a partir dos modelos em core/req_models.py
-- Executar em transação e revisar antes de aplicar em produção.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS req_sequencia (
	chave VARCHAR(20) NOT NULL, 
	ultimo_numero INTEGER NOT NULL, 
	PRIMARY KEY (chave)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS req_usuario_papel (
	usuario_id INTEGER NOT NULL, 
	papel VARCHAR(20) NOT NULL, 
	PRIMARY KEY (usuario_id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS req_requerimento (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	codigo VARCHAR(20), 
	numero INTEGER, 
	serie VARCHAR(20), 
	status VARCHAR(30) NOT NULL, 
	tipo VARCHAR(30), 
	prioridade VARCHAR(20) NOT NULL, 
	data_referencia DATE, 
	data_limite DATE, 
	solicitante_usuario_id INTEGER NOT NULL, 
	solicitante_nome VARCHAR(120), 
	solicitante_email VARCHAR(120), 
	solicitante_telefone VARCHAR(30), 
	funcionario VARCHAR(120), 
	filial VARCHAR(80), 
	setor VARCHAR(80), 
	responsavel VARCHAR(120), 
	unidade_negocio VARCHAR(80), 
	centro_gasto VARCHAR(80), 
	centro_custo VARCHAR(80), 
	classe_sintetica VARCHAR(80), 
	classe_analitica VARCHAR(80), 
	tipo_requisicao VARCHAR(80), 
	categoria VARCHAR(80), 
	justificativa TEXT, 
	observacao TEXT, 
	necessita_cotacao BOOL NOT NULL, 
	cotacao_selecionada_id INTEGER, 
	etapa_atual INTEGER NOT NULL, 
	valor_estimado NUMERIC(15, 2) NOT NULL, 
	responsavel_atual VARCHAR(120), 
	enviado_em DATETIME, 
	criado_em DATETIME NOT NULL, 
	criado_por VARCHAR(120), 
	atualizado_em DATETIME NOT NULL, 
	atualizado_por VARCHAR(120), 
	cancelado_em DATETIME, 
	cancelado_por VARCHAR(120), 
	motivo_cancelamento TEXT, 
	PRIMARY KEY (id), 
	UNIQUE (codigo), 
	FOREIGN KEY(solicitante_usuario_id) REFERENCES usuarios (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_req_requerimento_status ON req_requerimento (status);
CREATE INDEX ix_req_requerimento_solicitante_usuario_id ON req_requerimento (solicitante_usuario_id);
CREATE INDEX ix_req_status_prioridade ON req_requerimento (status, prioridade);

CREATE TABLE IF NOT EXISTS req_item (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	requerimento_id INTEGER NOT NULL, 
	sequencia INTEGER NOT NULL, 
	produto_codigo VARCHAR(40), 
	produto_descricao VARCHAR(200) NOT NULL, 
	descricao_complementar TEXT, 
	quantidade NUMERIC(15, 4) NOT NULL, 
	unidade VARCHAR(10) NOT NULL, 
	data_necessidade DATE, 
	valor_referencia NUMERIC(15, 4), 
	observacao TEXT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_req_item_seq UNIQUE (requerimento_id, sequencia), 
	FOREIGN KEY(requerimento_id) REFERENCES req_requerimento (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_req_item_requerimento_id ON req_item (requerimento_id);

CREATE TABLE IF NOT EXISTS req_localizacao (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	requerimento_id INTEGER NOT NULL, 
	item_sequencia INTEGER, 
	filial VARCHAR(80), 
	local VARCHAR(120), 
	almoxarifado VARCHAR(120), 
	setor VARCHAR(80), 
	departamento VARCHAR(80), 
	endereco VARCHAR(200), 
	centro_custo VARCHAR(80), 
	responsavel_recebimento VARCHAR(120), 
	observacao TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(requerimento_id) REFERENCES req_requerimento (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_req_localizacao_requerimento_id ON req_localizacao (requerimento_id);

CREATE TABLE IF NOT EXISTS req_complemento (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	requerimento_id INTEGER NOT NULL, 
	item_sequencia INTEGER, 
	tipo_movimento VARCHAR(30), 
	documento_origem VARCHAR(60), 
	quantidade NUMERIC(15, 4), 
	data_movimento DATE, 
	almoxarifado VARCHAR(120), 
	confirmado BOOL NOT NULL, 
	observacao TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(requerimento_id) REFERENCES req_requerimento (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_req_complemento_requerimento_id ON req_complemento (requerimento_id);

CREATE TABLE IF NOT EXISTS req_anexo (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	requerimento_id INTEGER NOT NULL, 
	nome_original VARCHAR(255) NOT NULL, 
	nome_arquivo VARCHAR(255) NOT NULL, 
	extensao VARCHAR(10), 
	tamanho_bytes INTEGER NOT NULL, 
	mime VARCHAR(120), 
	enviado_em DATETIME NOT NULL, 
	enviado_por VARCHAR(120), 
	PRIMARY KEY (id), 
	FOREIGN KEY(requerimento_id) REFERENCES req_requerimento (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_req_anexo_requerimento_id ON req_anexo (requerimento_id);

CREATE TABLE IF NOT EXISTS req_cotacao (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	requerimento_id INTEGER NOT NULL, 
	item_sequencia INTEGER, 
	fornecedor VARCHAR(150) NOT NULL, 
	fornecedor_documento VARCHAR(20), 
	produto VARCHAR(200), 
	quantidade NUMERIC(15, 4) NOT NULL, 
	preco_unitario NUMERIC(15, 4) NOT NULL, 
	preco_total NUMERIC(15, 2) NOT NULL, 
	prazo_entrega_dias INTEGER, 
	validade DATE, 
	condicao_pagamento VARCHAR(80), 
	observacao TEXT, 
	selecionada BOOL NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(requerimento_id) REFERENCES req_requerimento (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_req_cotacao_requerimento_id ON req_cotacao (requerimento_id);

CREATE TABLE IF NOT EXISTS req_historico (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	requerimento_id INTEGER NOT NULL, 
	data_hora DATETIME NOT NULL, 
	usuario_id INTEGER, 
	usuario_nome VARCHAR(120), 
	acao VARCHAR(60) NOT NULL, 
	status_anterior VARCHAR(30), 
	status_novo VARCHAR(30), 
	descricao TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(requerimento_id) REFERENCES req_requerimento (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_req_historico_requerimento_id ON req_historico (requerimento_id);
