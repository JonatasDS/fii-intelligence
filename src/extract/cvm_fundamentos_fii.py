import io
import zipfile
import requests
import pandas as pd
import numpy as np
from datetime import datetime


print("========================================")
print("CVM - FUNDAMENTOS MENSAIS DOS FIIs")
print("========================================")


# ==========================================================
# CONFIGURACAO
# ==========================================================

ANO = datetime.now().year

URL = (
    f"https://dados.cvm.gov.br/dados/FII/DOC/"
    f"INF_MENSAL/DADOS/inf_mensal_fii_{ANO}.zip"
)

ARQUIVO_CSV = f"inf_mensal_fii_complemento_{ANO}.csv"

ARQUIVO_SAIDA = "cvm_fundamentos_fii.csv"


# ==========================================================
# DOWNLOAD
# ==========================================================

print(f"\nBaixando Informe Mensal FII {ANO}...")

resposta = requests.get(
    URL,
    timeout=180
)

resposta.raise_for_status()

print(
    "Download concluido:",
    len(resposta.content),
    "bytes"
)


# ==========================================================
# ABRIR ZIP
# ==========================================================

with zipfile.ZipFile(
    io.BytesIO(resposta.content)
) as arquivo_zip:

    print("\nArquivos encontrados:")

    for nome in arquivo_zip.namelist():
        print(" -", nome)

    if ARQUIVO_CSV not in arquivo_zip.namelist():
        raise RuntimeError(
            f"Arquivo {ARQUIVO_CSV} nao encontrado."
        )

    print(
        "\nLendo:",
        ARQUIVO_CSV
    )

    df = pd.read_csv(
        arquivo_zip.open(ARQUIVO_CSV),
        sep=";",
        encoding="latin1",
        dtype=str,
        low_memory=False
    )


print(
    "\nRegistros brutos:",
    len(df)
)


# ==========================================================
# SELECIONAR CAMPOS
# ==========================================================

colunas = [
    "CNPJ_Fundo_Classe",
    "Data_Referencia",
    "Versao",
    "Total_Numero_Cotistas",
    "Valor_Ativo",
    "Patrimonio_Liquido",
    "Cotas_Emitidas",
    "Valor_Patrimonial_Cotas",
    "Percentual_Rentabilidade_Efetiva_Mes",
    "Percentual_Rentabilidade_Patrimonial_Mes",
    "Percentual_Dividend_Yield_Mes",
    "Percentual_Amortizacao_Cotas_Mes"
]


faltantes = [
    coluna
    for coluna in colunas
    if coluna not in df.columns
]


if faltantes:
    raise RuntimeError(
        "Colunas ausentes no arquivo: "
        + ", ".join(faltantes)
    )


df = df[colunas].copy()


# ==========================================================
# LIMPAR CNPJ
# ==========================================================

df["CNPJ_Fundo_Classe"] = (
    df["CNPJ_Fundo_Classe"]
    .astype("string")
    .str.replace(
        r"\D",
        "",
        regex=True
    )
)


# CNPJ valido deve possuir 14 digitos
cnpjs_invalidos = (
    df["CNPJ_Fundo_Classe"]
    .str.len()
    .ne(14)
    .sum()
)


# ==========================================================
# DATA
# ==========================================================

df["Data_Referencia"] = pd.to_datetime(
    df["Data_Referencia"],
    errors="coerce"
)


datas_invalidas = (
    df["Data_Referencia"]
    .isna()
    .sum()
)


# ==========================================================
# NUMERICOS
# IMPORTANTE:
# CVM usa ponto como separador decimal neste arquivo.
# Nao remover os pontos.
# ==========================================================

colunas_numericas = [
    "Total_Numero_Cotistas",
    "Valor_Ativo",
    "Patrimonio_Liquido",
    "Cotas_Emitidas",
    "Valor_Patrimonial_Cotas",
    "Percentual_Rentabilidade_Efetiva_Mes",
    "Percentual_Rentabilidade_Patrimonial_Mes",
    "Percentual_Dividend_Yield_Mes",
    "Percentual_Amortizacao_Cotas_Mes"
]


for coluna in colunas_numericas:

    df[coluna] = pd.to_numeric(
        df[coluna],
        errors="coerce"
    )


# ==========================================================
# VERSAO
# ==========================================================

df["Versao"] = pd.to_numeric(
    df["Versao"],
    errors="coerce"
).fillna(0)


# ==========================================================
# TRATAR REAPRESENTACOES
# ==========================================================

duplicados_antes = df.duplicated(
    subset=[
        "CNPJ_Fundo_Classe",
        "Data_Referencia"
    ],
    keep=False
).sum()


print(
    "\nDuplicidades CNPJ+data antes do tratamento:",
    duplicados_antes
)


df = (
    df
    .sort_values(
        [
            "CNPJ_Fundo_Classe",
            "Data_Referencia",
            "Versao"
        ]
    )
    .drop_duplicates(
        subset=[
            "CNPJ_Fundo_Classe",
            "Data_Referencia"
        ],
        keep="last"
    )
    .reset_index(drop=True)
)


# ==========================================================
# VALIDACAO MATEMATICA
#
# Patrimonio Liquido / Cotas Emitidas
# deve ser aproximadamente igual ao
# Valor Patrimonial por Cota.
# ==========================================================

df["vp_calculado"] = np.where(
    df["Cotas_Emitidas"].notna()
    & (df["Cotas_Emitidas"] != 0)
    & df["Patrimonio_Liquido"].notna(),

    df["Patrimonio_Liquido"]
    / df["Cotas_Emitidas"],

    np.nan
)


df["diferenca_vp_percentual"] = np.where(
    df["vp_calculado"].notna()
    & df["Valor_Patrimonial_Cotas"].notna()
    & (df["Valor_Patrimonial_Cotas"] != 0),

    (
        (
            df["vp_calculado"]
            - df["Valor_Patrimonial_Cotas"]
        ).abs()
        /
        df["Valor_Patrimonial_Cotas"].abs()
    ) * 100,

    np.nan
)


# Tolerancia de 0,1%
# Serve para detectar erro de escala/conversao.
inconsistencias_vp = (
    df["diferenca_vp_percentual"] > 0.1
).sum()


comparacoes_vp = (
    df["diferenca_vp_percentual"]
    .notna()
    .sum()
)


# ==========================================================
# VALIDACOES
# ==========================================================

print("\n========================================")
print("VALIDACAO")
print("========================================")

print(
    "Registros apos tratamento:",
    len(df)
)

print(
    "CNPJs diferentes:",
    df["CNPJ_Fundo_Classe"].nunique()
)

print(
    "CNPJs com tamanho invalido:",
    cnpjs_invalidos
)

print(
    "Datas invalidas:",
    datas_invalidas
)

print(
    "Primeira referencia:",
    df["Data_Referencia"].min()
)

print(
    "Ultima referencia:",
    df["Data_Referencia"].max()
)

print(
    "Patrimonios preenchidos:",
    df["Patrimonio_Liquido"].notna().sum()
)

print(
    "Valores patrimoniais por cota:",
    df["Valor_Patrimonial_Cotas"].notna().sum()
)

print(
    "Dividend Yield preenchidos:",
    df["Percentual_Dividend_Yield_Mes"].notna().sum()
)

print(
    "Numero de cotistas preenchidos:",
    df["Total_Numero_Cotistas"].notna().sum()
)

print(
    "Comparacoes matematicas de VP:",
    comparacoes_vp
)

print(
    "Inconsistencias de VP acima de 0,1%:",
    inconsistencias_vp
)


duplicados_depois = df.duplicated(
    subset=[
        "CNPJ_Fundo_Classe",
        "Data_Referencia"
    ]
).sum()


print(
    "Duplicidades apos tratamento:",
    duplicados_depois
)


# ==========================================================
# PROTECOES
# ==========================================================

if cnpjs_invalidos > 0:
    raise RuntimeError(
        "Existem CNPJs com quantidade de digitos invalida."
    )


if datas_invalidas > 0:
    raise RuntimeError(
        "Existem datas de referencia invalidas."
    )


if duplicados_depois > 0:
    raise RuntimeError(
        "Ainda existem duplicidades CNPJ+data."
    )


# Nao exigimos zero absoluto porque podem existir casos
# contabeis excepcionais, mas uma quantidade muito alta
# indicaria novamente problema de conversao.
if comparacoes_vp > 0:

    percentual_inconsistente = (
        inconsistencias_vp
        / comparacoes_vp
    ) * 100

    print(
        "Percentual de inconsistencias de VP:",
        round(percentual_inconsistente, 4),
        "%"
    )

    if percentual_inconsistente > 5:
        raise RuntimeError(
            "Mais de 5% dos registros apresentam "
            "inconsistencia entre patrimonio, cotas "
            "e valor patrimonial por cota. "
            "Carga interrompida por seguranca."
        )


# ==========================================================
# RENOMEAR
# ==========================================================

df = df.rename(
    columns={
        "CNPJ_Fundo_Classe":
            "cnpj_fundo_classe",

        "Data_Referencia":
            "data_referencia",

        "Versao":
            "versao",

        "Total_Numero_Cotistas":
            "total_numero_cotistas",

        "Valor_Ativo":
            "valor_ativo",

        "Patrimonio_Liquido":
            "patrimonio_liquido",

        "Cotas_Emitidas":
            "cotas_emitidas",

        "Valor_Patrimonial_Cotas":
            "valor_patrimonial_cota",

        "Percentual_Rentabilidade_Efetiva_Mes":
            "rentabilidade_efetiva_mes",

        "Percentual_Rentabilidade_Patrimonial_Mes":
            "rentabilidade_patrimonial_mes",

        "Percentual_Dividend_Yield_Mes":
            "dividend_yield_mes",

        "Percentual_Amortizacao_Cotas_Mes":
            "amortizacao_cotas_mes"
    }
)


# ==========================================================
# AMOSTRA MAIS RECENTE
# ==========================================================

ultima_data = df["data_referencia"].max()


amostra = (
    df[
        df["data_referencia"]
        == ultima_data
    ]
    [
        [
            "cnpj_fundo_classe",
            "data_referencia",
            "patrimonio_liquido",
            "cotas_emitidas",
            "valor_patrimonial_cota",
            "vp_calculado",
            "diferenca_vp_percentual",
            "dividend_yield_mes",
            "total_numero_cotistas"
        ]
    ]
    .head(15)
)


print("\n========================================")
print("AMOSTRA - ULTIMA REFERENCIA")
print("========================================")

print(
    amostra.to_string(
        index=False
    )
)


# ==========================================================
# REMOVER COLUNAS AUXILIARES
# ==========================================================

df = df.drop(
    columns=[
        "vp_calculado",
        "diferenca_vp_percentual"
    ]
)


# ==========================================================
# SALVAR
# ==========================================================

df.to_csv(
    ARQUIVO_SAIDA,
    index=False,
    encoding="utf-8-sig"
)


print("\n========================================")
print("FINALIZADO")
print("========================================")

print(
    "Arquivo salvo:",
    ARQUIVO_SAIDA
)

print(
    "Nenhuma alteracao foi feita no PostgreSQL."
)