import os
import re

import pandas as pd
import psycopg2
from dotenv import load_dotenv


print("========================================")
print("PREPARACAO DOS TICKERS B3")
print("========================================")

load_dotenv()

ARQUIVO_B3 = "b3_fiis_detalhes.csv"


def limpar_cnpj(valor):
    if pd.isna(valor):
        return None

    numeros = re.sub(
        r"[^0-9]",
        "",
        str(valor)
    )

    if not numeros:
        return None

    return numeros.zfill(14)


def limpar_texto(valor):
    if pd.isna(valor):
        return None

    valor = str(valor).strip()

    if not valor:
        return None

    return valor


# ==========================================================
# B3
# ==========================================================

print("\nLendo B3...")

b3 = pd.read_csv(
    ARQUIVO_B3,
    dtype=str,
    low_memory=False
)

b3["cnpj_limpo"] = (
    b3["cnpj"]
    .apply(limpar_cnpj)
)

b3["ticker_limpo"] = (
    b3["trading_code"]
    .apply(limpar_texto)
)

print("Registros B3:", len(b3))
print(
    "Tickers preenchidos:",
    b3["ticker_limpo"].notna().sum()
)
print(
    "Tickers vazios:",
    b3["ticker_limpo"].isna().sum()
)


# ==========================================================
# POSTGRESQL
# ==========================================================

print("\nConectando ao PostgreSQL...")

conexao = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT", "5432"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)

consulta = """
SELECT
    id_registro_classe,
    id_registro_fundo,
    cnpj_classe,
    cnpj_fundo,
    nome_classe,
    nome_fundo,
    situacao,
    presente_cvm,
    ticker
FROM fiis
WHERE presente_cvm = TRUE
"""
fiis = pd.read_sql_query(
    consulta,
    conexao
)

conexao.close()

print(
    "Registros na tabela fiis:",
    len(fiis)
)


# ==========================================================
# NORMALIZAR CNPJS CVM
# ==========================================================

fiis["cnpj_classe_limpo"] = (
    fiis["cnpj_classe"]
    .apply(limpar_cnpj)
)

fiis["cnpj_fundo_limpo"] = (
    fiis["cnpj_fundo"]
    .apply(limpar_cnpj)
)


# ==========================================================
# MATCH 1 - CNPJ DA CLASSE
# ==========================================================

b3_base = b3[
    [
        "cnpj_limpo",
        "ticker_limpo",
        "classification",
        "segment"
    ]
].copy()


match_classe = b3_base.merge(
    fiis,
    left_on="cnpj_limpo",
    right_on="cnpj_classe_limpo",
    how="inner"
)

match_classe["tipo_match"] = "CNPJ_CLASSE"


# ==========================================================
# B3 JA IDENTIFICADOS POR CLASSE
# ==========================================================

cnpjs_encontrados_classe = set(
    match_classe["cnpj_limpo"]
    .dropna()
)


# ==========================================================
# MATCH 2 - CNPJ DO FUNDO
# Apenas B3 ainda nao encontrados por classe
# ==========================================================

b3_restante = b3_base[
    ~b3_base["cnpj_limpo"].isin(
        cnpjs_encontrados_classe
    )
].copy()


match_fundo = b3_restante.merge(
    fiis,
    left_on="cnpj_limpo",
    right_on="cnpj_fundo_limpo",
    how="inner"
)

match_fundo["tipo_match"] = "CNPJ_FUNDO"


# ==========================================================
# JUNTAR
# ==========================================================

matches = pd.concat(
    [
        match_classe,
        match_fundo
    ],
    ignore_index=True
)


print("\n========================================")
print("RESULTADO DO CRUZAMENTO")
print("========================================")

print(
    "Encontrados por CNPJ da classe:",
    len(match_classe)
)

print(
    "Encontrados adicionais por CNPJ do fundo:",
    len(match_fundo)
)

print(
    "Total de correspondencias:",
    len(matches)
)


# ==========================================================
# VALIDAR DUPLICIDADE DE CLASSE
# ==========================================================

duplicados_classe = matches[
    matches["id_registro_classe"]
    .duplicated(keep=False)
]

print(
    "IDs de classe duplicados no resultado:",
    duplicados_classe[
        "id_registro_classe"
    ].nunique()
)


# ==========================================================
# REGISTROS COM TICKER
# ==========================================================

com_ticker = matches[
    matches["ticker_limpo"].notna()
].copy()

sem_ticker = matches[
    matches["ticker_limpo"].isna()
].copy()


print("\n========================================")
print("TICKERS")
print("========================================")

print(
    "Correspondencias com ticker:",
    len(com_ticker)
)

print(
    "Correspondencias sem ticker:",
    len(sem_ticker)
)


# ==========================================================
# VERIFICAR SE TICKER JA EXISTE DIFERENTE
# ==========================================================

com_ticker["ticker_atual"] = (
    com_ticker["ticker"]
    .apply(limpar_texto)
)


conflitos = com_ticker[
    com_ticker["ticker_atual"].notna()
    &
    (
        com_ticker["ticker_atual"]
        !=
        com_ticker["ticker_limpo"]
    )
].copy()


print(
    "Conflitos com ticker ja existente:",
    len(conflitos)
)


# ==========================================================
# DUPLICIDADE REAL DE TICKER
# ==========================================================

duplicidade_ticker = (
    com_ticker[
        com_ticker["ticker_limpo"].notna()
    ]
    .groupby("ticker_limpo")[
        "id_registro_classe"
    ]
    .nunique()
)

duplicidade_ticker = (
    duplicidade_ticker[
        duplicidade_ticker > 1
    ]
)


print(
    "Tickers ligados a mais de uma classe:",
    len(duplicidade_ticker)
)


# ==========================================================
# AMOSTRA
# ==========================================================

print("\n========================================")
print("AMOSTRA DO QUE SERIA ATUALIZADO")
print("========================================")


colunas_amostra = [
    "ticker_limpo",
    "id_registro_classe",
    "cnpj_limpo",
    "nome_classe",
    "nome_fundo",
    "situacao",
    "tipo_match"
]


print(
    com_ticker[
        colunas_amostra
    ]
    .head(30)
    .to_string(index=False)
)


# ==========================================================
# SALVAR PREVIA
# ==========================================================

arquivo_saida = (
    "b3_tickers_previa_atualizacao.csv"
)

com_ticker[
    colunas_amostra
].to_csv(
    arquivo_saida,
    index=False,
    encoding="utf-8-sig"
)


print("\n========================================")
print("VALIDACAO FINAL")
print("========================================")

if (
    len(conflitos) == 0
    and
    len(duplicidade_ticker) == 0
    and
    duplicados_classe.empty
):

    print(
        "STATUS: APROVADO PARA PROXIMA ETAPA"
    )

else:

    print(
        "STATUS: NECESSITA REVISAO"
    )


print(
    "\nPrevia salva em:",
    arquivo_saida
)

print(
    "\nIMPORTANTE:"
    "\nNenhum UPDATE ou INSERT foi executado."
    "\nO PostgreSQL nao foi alterado."
)

print("\n========================================")
print("FINALIZADO")
print("========================================")