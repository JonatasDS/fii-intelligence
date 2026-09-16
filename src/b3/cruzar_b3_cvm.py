import pandas as pd
import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv


print("========================================")
print("CRUZAMENTO B3 x CVM")
print("========================================")


# ==========================================================
# LOCALIZAR PROJETO
# ==========================================================

PASTA_PROJETO = (
    Path(__file__)
    .resolve()
    .parents[2]
)

ARQUIVO_B3 = (
    PASTA_PROJETO
    / "b3_fiis_detalhes.csv"
)

ARQUIVO_ENV = (
    PASTA_PROJETO
    / ".env"
)


# ==========================================================
# CARREGAR .ENV
# ==========================================================

load_dotenv(
    ARQUIVO_ENV
)


# ==========================================================
# FUNCAO PARA LIMPAR CNPJ
# ==========================================================

def limpar_cnpj(valor):

    if pd.isna(valor):
        return None

    texto = str(valor)

    apenas_numeros = "".join(
        caractere
        for caractere in texto
        if caractere.isdigit()
    )

    if not apenas_numeros:
        return None

    return apenas_numeros.zfill(14)


# ==========================================================
# LER B3
# ==========================================================

print("\nLendo arquivo da B3...")

df_b3 = pd.read_csv(
    ARQUIVO_B3,
    dtype={
        "cnpj": "string",
        "trading_code": "string",
        "acronym": "string"
    }
)


df_b3["cnpj_limpo"] = (
    df_b3["cnpj"]
    .apply(limpar_cnpj)
)


print(
    "Registros B3:",
    len(df_b3)
)

print(
    "CNPJs B3 preenchidos:",
    df_b3["cnpj_limpo"].notna().sum()
)


# ==========================================================
# CONECTAR POSTGRESQL
# ==========================================================

print("\nConectando ao PostgreSQL...")


conexao = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)


# ==========================================================
# LER FIIs CVM
# ==========================================================

consulta = """
SELECT
    id_fii,
    id_registro_fundo,
    id_registro_classe,
    codigo_cvm,
    cnpj_fundo,
    cnpj_classe,
    nome_fundo,
    nome_classe,
    situacao,
    ticker,
    segmento,
    presente_cvm
FROM fiis
"""


df_cvm = pd.read_sql_query(
    consulta,
    conexao
)


conexao.close()


print(
    "Registros CVM no banco:",
    len(df_cvm)
)


# ==========================================================
# LIMPAR CNPJs CVM
# ==========================================================

df_cvm["cnpj_classe_limpo"] = (
    df_cvm["cnpj_classe"]
    .apply(limpar_cnpj)
)

df_cvm["cnpj_fundo_limpo"] = (
    df_cvm["cnpj_fundo"]
    .apply(limpar_cnpj)
)


# ==========================================================
# CRUZAMENTO POR CNPJ DA CLASSE
# ==========================================================

classe = df_b3.merge(
    df_cvm,
    how="left",
    left_on="cnpj_limpo",
    right_on="cnpj_classe_limpo",
    suffixes=("_b3", "_cvm")
)


classe_encontrados = classe[
    classe["id_registro_classe"].notna()
].copy()


cnpjs_encontrados_classe = set(
    classe_encontrados["cnpj_limpo"]
    .dropna()
)


# ==========================================================
# B3 AINDA NAO ENCONTRADOS
# ==========================================================

b3_restante = df_b3[
    ~df_b3["cnpj_limpo"].isin(
        cnpjs_encontrados_classe
    )
].copy()


# ==========================================================
# CRUZAMENTO POR CNPJ DO FUNDO
# ==========================================================

fundo = b3_restante.merge(
    df_cvm,
    how="left",
    left_on="cnpj_limpo",
    right_on="cnpj_fundo_limpo",
    suffixes=("_b3", "_cvm")
)


fundo_encontrados = fundo[
    fundo["id_registro_classe"].notna()
].copy()


cnpjs_encontrados_fundo = set(
    fundo_encontrados["cnpj_limpo"]
    .dropna()
)


# ==========================================================
# NAO ENCONTRADOS
# ==========================================================

todos_encontrados = (
    cnpjs_encontrados_classe
    |
    cnpjs_encontrados_fundo
)


nao_encontrados = df_b3[
    ~df_b3["cnpj_limpo"].isin(
        todos_encontrados
    )
].copy()


# ==========================================================
# RESUMO
# ==========================================================

print("\n========================================")
print("RESULTADO DO CRUZAMENTO")
print("========================================")


print(
    "FIIs B3:",
    len(df_b3)
)


print(
    "Encontrados por CNPJ da classe:",
    len(cnpjs_encontrados_classe)
)


print(
    "Encontrados adicionais por CNPJ do fundo:",
    len(cnpjs_encontrados_fundo)
)


print(
    "Total identificado:",
    len(todos_encontrados)
)


print(
    "Nao identificados:",
    len(nao_encontrados)
)


percentual = (
    len(todos_encontrados)
    / len(df_b3)
    * 100
)


print(
    f"Percentual identificado: {percentual:.2f}%"
)


# ==========================================================
# TRADING CODES
# ==========================================================

print("\n========================================")
print("VALIDACAO DE TICKERS B3")
print("========================================")


preenchidos = df_b3[
    df_b3["trading_code"].notna()
].copy()


vazios = df_b3[
    df_b3["trading_code"].isna()
].copy()


duplicados_reais = preenchidos[
    preenchidos.duplicated(
        subset=["trading_code"],
        keep=False
    )
].copy()


print(
    "Trading codes preenchidos:",
    len(preenchidos)
)


print(
    "Trading codes vazios:",
    len(vazios)
)


print(
    "Trading codes duplicados reais:",
    len(duplicados_reais)
)


# ==========================================================
# MOSTRAR NAO ENCONTRADOS
# ==========================================================

if not nao_encontrados.empty:

    print("\n========================================")
    print("B3 NAO ENCONTRADOS NA CVM")
    print("========================================")

    colunas = [
        "id_fnet",
        "acronym",
        "trading_code",
        "cnpj",
        "fund_name"
    ]

    print(
        nao_encontrados[colunas]
        .to_string(index=False)
    )


# ==========================================================
# MOSTRAR TICKERS VAZIOS
# ==========================================================

if not vazios.empty:

    print("\n========================================")
    print("FIIs SEM TRADING CODE")
    print("========================================")

    colunas = [
        "id_fnet",
        "acronym",
        "cnpj",
        "fund_name"
    ]

    print(
        vazios[colunas]
        .to_string(index=False)
    )


# ==========================================================
# MOSTRAR DUPLICADOS REAIS
# ==========================================================

if not duplicados_reais.empty:

    print("\n========================================")
    print("TRADING CODES DUPLICADOS REAIS")
    print("========================================")

    colunas = [
        "id_fnet",
        "acronym",
        "trading_code",
        "cnpj",
        "fund_name"
    ]

    print(
        duplicados_reais[colunas]
        .sort_values(
            "trading_code"
        )
        .to_string(index=False)
    )


# ==========================================================
# SALVAR RESULTADOS
# ==========================================================

arquivo_nao_encontrados = (
    PASTA_PROJETO
    / "b3_cvm_nao_encontrados.csv"
)


nao_encontrados.to_csv(
    arquivo_nao_encontrados,
    index=False,
    encoding="utf-8-sig"
)


print("\n========================================")
print("ARQUIVO GERADO")
print("========================================")

print(
    arquivo_nao_encontrados
)


print("\n========================================")
print("FINALIZADO")
print("========================================")

print(
    "Nenhuma alteracao foi feita "
    "no PostgreSQL."
)