DROP TABLE IF EXISTS fiis;

CREATE TABLE fiis (
    id_fii SERIAL PRIMARY KEY,

    id_registro_fundo BIGINT,
    id_registro_classe BIGINT UNIQUE NOT NULL,

    codigo_cvm BIGINT,

    cnpj_fundo VARCHAR(14),
    cnpj_classe VARCHAR(14),

    nome_fundo VARCHAR(255),
    nome_classe VARCHAR(255),

    tipo_classe VARCHAR(100),

    classificacao VARCHAR(255),
    classificacao_anbima VARCHAR(255),

    situacao VARCHAR(100),

    administrador VARCHAR(255),
    gestor VARCHAR(255),

    patrimonio_liquido NUMERIC(20,2),
    data_patrimonio_liquido DATE,

    data_inicio DATE,

    ticker VARCHAR(10),
    segmento VARCHAR(100),

    fonte VARCHAR(50) DEFAULT 'CVM',

    data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fiis_historico (
    id_historico SERIAL PRIMARY KEY,

    id_registro_classe BIGINT NOT NULL,

    campo_alterado VARCHAR(100) NOT NULL,

    valor_anterior TEXT,

    valor_novo TEXT,

    data_alteracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    fonte VARCHAR(50) DEFAULT 'CVM'
);