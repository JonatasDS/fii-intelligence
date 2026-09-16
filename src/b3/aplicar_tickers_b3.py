import os
import re

import pandas as pd
import psycopg2
from dotenv import load_dotenv


print("========================================")
print("APLICACAO DEFINITIVA DOS TICKERS B3")
print("========================================")

load_dotenv()

ARQUIVO_B3 = "b3_fiis_detalhes.csv"


# ==========================================================
# FUNCOES
# ==========================================================

def limpar_cnpj(valor):
    if pd.isna(valor):
        return None

    numeros = re.sub(r"[^0-9]", "", str(valor))

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
# LER B3
# ==========================================================

print("\nLendo arquivo B3...")

b3 = pd.read_csv(
    ARQUIVO_B3,
    dtype=str,
    low_memory=False
)

b3["cnpj_limpo"] = b3["cnpj"].apply(limpar_cnpj)
b3["ticker_limpo"] = b3["trading_code"].apply(limpar_texto)

print("Registros B3:", len(b3))
print("Tickers preenchidos:", b3["ticker_limpo"].notna().sum())
print("Tickers vazios:", b3["ticker_limpo"].isna().sum())


# ==========================================================
# CONECTAR BANCO
# ==========================================================

print("\nConectando ao PostgreSQL...")

conexao = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT", "5432"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)

cursor = conexao.cursor()


# ==========================================================
# CARREGAR FIIs ATUAIS
# ==========================================================

consulta = """
SELECT
    id_registro_classe,
    id_registro_fundo,
    cnpj_classe,
    cnpj_fundo,
    nome_classe,
    ticker
FROM fiis
WHERE presente_cvm = TRUE
"""

fiis = pd.read_sql_query(consulta, conexao)

print("FIIs atuais:", len(fiis))

fiis["cnpj_classe_limpo"] = fiis["cnpj_classe"].apply(limpar_cnpj)
fiis["cnpj_fundo_limpo"] = fiis["cnpj_fundo"].apply(limpar_cnpj)


# ==========================================================
# MATCH CNPJ CLASSE
# ==========================================================

b3_base = b3[["cnpj_limpo", "ticker_limpo"]].copy()

match_classe = b3_base.merge(
    fiis,
    left_on="cnpj_limpo",
    right_on="cnpj_classe_limpo",
    how="inner"
)

cnpjs_classe = set(match_classe["cnpj_limpo"].dropna())

match_classe["tipo_match"] = "CNPJ_CLASSE"


# ==========================================================
# MATCH CNPJ FUNDO
# ==========================================================

b3_restante = b3_base[
    ~b3_base["cnpj_limpo"].isin(cnpjs_classe)
].copy()

match_fundo = b3_restante.merge(
    fiis,
    left_on="cnpj_limpo",
    right_on="cnpj_fundo_limpo",
    how="inner"
)

match_fundo["tipo_match"] = "CNPJ_FUNDO"


# ==========================================================
# CONSOLIDAR
# ==========================================================

matches = pd.concat(
    [match_classe, match_fundo],
    ignore_index=True
)

com_ticker = matches[
    matches["ticker_limpo"].notna()
].copy()


# ==========================================================
# AMBIGUIDADES
# ==========================================================

qtd = (
    com_ticker
    .groupby("ticker_limpo")["id_registro_classe"]
    .nunique()
)

tickers_ambiguos = set(
    qtd[qtd > 1].index
)

seguros = com_ticker[
    ~com_ticker["ticker_limpo"].isin(tickers_ambiguos)
].copy()


# ==========================================================
# VALIDACOES
# ==========================================================

duplicados_id = seguros[
    seguros["id_registro_classe"].duplicated(keep=False)
]

if not duplicados_id.empty:
    raise RuntimeError(
        "IDs de classe duplicados detectados."
    )

duplicados_ticker = (
    seguros.groupby("ticker_limpo")["id_registro_classe"]
    .nunique()
)

duplicados_ticker = duplicados_ticker[
    duplicados_ticker > 1
]

if not duplicados_ticker.empty:
    raise RuntimeError(
        "Ticker seguro associado a mais de uma classe."
    )


print("\n========================================")
print("VALIDACAO")
print("========================================")

print("Match classe:", len(match_classe))
print("Match fundo:", len(match_fundo))
print("Correspondencias:", len(com_ticker))
print("Ambiguos:", len(tickers_ambiguos))
print("Seguros:", len(seguros))


# ==========================================================
# TRANSACAO
# ==========================================================

try:

    print("\nIniciando transacao...")

    # limpar somente registros atuais
    cursor.execute(
        """
        UPDATE fiis
        SET ticker = NULL
        WHERE presente_cvm = TRUE;
        """
    )

    linhas_limpas = cursor.rowcount

    print(
        "Tickers atuais limpos:",
        linhas_limpas
    )

    # aplicar correspondencias seguras
    atualizados = 0

    for _, linha in seguros.iterrows():

        cursor.execute(
            """
            UPDATE fiis
            SET ticker = %s
            WHERE id_registro_classe = %s
              AND presente_cvm = TRUE;
            """,
            (
                linha["ticker_limpo"],
                int(linha["id_registro_classe"])
            )
        )

        atualizados += cursor.rowcount


    # ======================================================
    # VALIDACAO FINAL
    # ======================================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM fiis
        WHERE presente_cvm = TRUE
          AND ticker IS NOT NULL;
        """
    )

    total_ticker = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT ticker, COUNT(*)
        FROM fiis
        WHERE presente_cvm = TRUE
          AND ticker IS NOT NULL
        GROUP BY ticker
        HAVING COUNT(*) > 1;
        """
    )

    duplicados = cursor.fetchall()

    print("\n========================================")
    print("VALIDACAO FINAL")
    print("========================================")

    print("Atualizados:", atualizados)
    print("FIIs com ticker:", total_ticker)
    print("Tickers duplicados:", len(duplicados))


    if total_ticker != len(seguros):
        raise RuntimeError(
            f"Quantidade incorreta. Esperado {len(seguros)} e obtido {total_ticker}."
        )

    if len(duplicados) > 0:
        raise RuntimeError(
            "Existem tickers duplicados apos sincronizacao."
        )


    conexao.commit()

    print("\nCOMMIT realizado com sucesso.")


except Exception as erro:

    conexao.rollback()

    print("\nERRO NA TRANSACAO")
    print(erro)
    print("ROLLBACK executado.")

    raise


finally:

    cursor.close()
    conexao.close()


print("\n========================================")
print("FINALIZADO")
print("========================================")

print("Tickers sincronizados com a B3.")
print("MAGM11 e RJDA11 permaneceram sem associacao automatica.")
print("Nenhuma outra coluna foi alterada.")