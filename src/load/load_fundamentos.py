import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv


print("========================================")
print("CARGA DE FUNDAMENTOS MENSAIS DOS FIIs")
print("========================================")


# ==========================================================
# CONFIGURACAO
# ==========================================================

ARQUIVO = "cvm_fundamentos_fii.csv"


# ==========================================================
# VARIAVEIS DE AMBIENTE
# ==========================================================

load_dotenv()


# ==========================================================
# LER CSV
# ==========================================================

print("\nLendo arquivo:", ARQUIVO)

df = pd.read_csv(
    ARQUIVO,
    dtype={
        "cnpj_fundo_classe": "string"
    }
)


print(
    "Registros encontrados:",
    len(df)
)


# ==========================================================
# VALIDACOES
# ==========================================================

colunas_obrigatorias = [
    "cnpj_fundo_classe",
    "data_referencia",
    "total_numero_cotistas",
    "valor_ativo",
    "patrimonio_liquido",
    "cotas_emitidas",
    "valor_patrimonial_cota",
    "rentabilidade_efetiva_mes",
    "rentabilidade_patrimonial_mes",
    "dividend_yield_mes",
    "amortizacao_cotas_mes"
]


faltantes = [
    coluna
    for coluna in colunas_obrigatorias
    if coluna not in df.columns
]


if faltantes:
    raise RuntimeError(
        "Colunas ausentes: "
        + ", ".join(faltantes)
    )


# ==========================================================
# DATA
# ==========================================================

df["data_referencia"] = pd.to_datetime(
    df["data_referencia"],
    errors="coerce"
).dt.date


datas_invalidas = (
    df["data_referencia"]
    .isna()
    .sum()
)


# ==========================================================
# CNPJ
# ==========================================================

df["cnpj_fundo_classe"] = (
    df["cnpj_fundo_classe"]
    .astype("string")
    .str.replace(
        r"\D",
        "",
        regex=True
    )
)


cnpjs_invalidos = (
    df["cnpj_fundo_classe"]
    .str.len()
    .ne(14)
    .sum()
)


# ==========================================================
# DUPLICIDADES
# ==========================================================

duplicados = df.duplicated(
    subset=[
        "cnpj_fundo_classe",
        "data_referencia"
    ]
).sum()


print("\n========================================")
print("VALIDACAO")
print("========================================")

print(
    "Datas invalidas:",
    datas_invalidas
)

print(
    "CNPJs invalidos:",
    cnpjs_invalidos
)

print(
    "Duplicidades CNPJ+data:",
    duplicados
)

print(
    "CNPJs diferentes:",
    df["cnpj_fundo_classe"].nunique()
)

print(
    "Primeira referencia:",
    df["data_referencia"].min()
)

print(
    "Ultima referencia:",
    df["data_referencia"].max()
)


if datas_invalidas > 0:
    raise RuntimeError(
        "Existem datas invalidas."
    )


if cnpjs_invalidos > 0:
    raise RuntimeError(
        "Existem CNPJs invalidos."
    )


if duplicados > 0:
    raise RuntimeError(
        "Existem duplicidades CNPJ+data."
    )


# ==========================================================
# SUBSTITUIR NAN POR NONE
# ==========================================================

df = df.astype(object).where(
    pd.notnull(df),
    None
)


# ==========================================================
# CONEXAO
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


try:

    # ======================================================
    # CONTAGEM ANTES
    # ======================================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM fundamentos_fii;
        """
    )

    total_antes = cursor.fetchone()[0]

    print(
        "Registros antes da carga:",
        total_antes
    )


    # ======================================================
    # PREPARAR DADOS
    # ======================================================

    registros = [
        (
            linha["cnpj_fundo_classe"],
            linha["data_referencia"],
            linha["total_numero_cotistas"],
            linha["valor_ativo"],
            linha["patrimonio_liquido"],
            linha["cotas_emitidas"],
            linha["valor_patrimonial_cota"],
            linha["rentabilidade_efetiva_mes"],
            linha["rentabilidade_patrimonial_mes"],
            linha["dividend_yield_mes"],
            linha["amortizacao_cotas_mes"]
        )

        for _, linha in df.iterrows()
    ]


    # ======================================================
    # UPSERT
    # ======================================================

    sql = """
        INSERT INTO fundamentos_fii (
            cnpj_fundo_classe,
            data_referencia,
            total_numero_cotistas,
            valor_ativo,
            patrimonio_liquido,
            cotas_emitidas,
            valor_patrimonial_cota,
            rentabilidade_efetiva_mes,
            rentabilidade_patrimonial_mes,
            dividend_yield_mes,
            amortizacao_cotas_mes,
            fonte,
            data_atualizacao
        )

        VALUES %s

        ON CONFLICT (
            cnpj_fundo_classe,
            data_referencia
        )

        DO UPDATE SET

            total_numero_cotistas =
                EXCLUDED.total_numero_cotistas,

            valor_ativo =
                EXCLUDED.valor_ativo,

            patrimonio_liquido =
                EXCLUDED.patrimonio_liquido,

            cotas_emitidas =
                EXCLUDED.cotas_emitidas,

            valor_patrimonial_cota =
                EXCLUDED.valor_patrimonial_cota,

            rentabilidade_efetiva_mes =
                EXCLUDED.rentabilidade_efetiva_mes,

            rentabilidade_patrimonial_mes =
                EXCLUDED.rentabilidade_patrimonial_mes,

            dividend_yield_mes =
                EXCLUDED.dividend_yield_mes,

            amortizacao_cotas_mes =
                EXCLUDED.amortizacao_cotas_mes,

            fonte =
                'CVM_INF_MENSAL',

            data_atualizacao =
                CURRENT_TIMESTAMP;
    """


    template = """
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            'CVM_INF_MENSAL',
            CURRENT_TIMESTAMP
        )
    """


    print(
        "\nCarregando fundamentos..."
    )


    execute_values(
        cursor,
        sql,
        registros,
        template=template,
        page_size=1000
    )


    # ======================================================
    # VALIDAR APOS CARGA
    # ======================================================

    cursor.execute(
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT cnpj_fundo_classe),
            MIN(data_referencia),
            MAX(data_referencia),
            COUNT(valor_patrimonial_cota),
            COUNT(dividend_yield_mes)

        FROM fundamentos_fii;
        """
    )


    resultado = cursor.fetchone()


    total = resultado[0]
    cnpjs = resultado[1]
    primeira_data = resultado[2]
    ultima_data = resultado[3]
    com_vp = resultado[4]
    com_dy = resultado[5]


    print("\n========================================")
    print("RESULTADO")
    print("========================================")

    print(
        "Registros processados:",
        len(registros)
    )

    print(
        "Registros no banco:",
        total
    )

    print(
        "CNPJs diferentes:",
        cnpjs
    )

    print(
        "Primeira referencia:",
        primeira_data
    )

    print(
        "Ultima referencia:",
        ultima_data
    )

    print(
        "Valores patrimoniais preenchidos:",
        com_vp
    )

    print(
        "Dividend Yield preenchidos:",
        com_dy
    )


    # ======================================================
    # AMOSTRA ULTIMA REFERENCIA
    # ======================================================

    cursor.execute(
        """
        SELECT
            cnpj_fundo_classe,
            data_referencia,
            ROUND(patrimonio_liquido, 2),
            ROUND(valor_patrimonial_cota, 4),
            ROUND(dividend_yield_mes, 6),
            total_numero_cotistas

        FROM fundamentos_fii

        WHERE data_referencia = (
            SELECT MAX(data_referencia)
            FROM fundamentos_fii
        )

        ORDER BY patrimonio_liquido DESC NULLS LAST

        LIMIT 15;
        """
    )


    amostra = cursor.fetchall()


    print("\n========================================")
    print("AMOSTRA - MAIORES PATRIMONIOS")
    print("========================================")


    for linha in amostra:
        print(linha)


    # ======================================================
    # COMMIT
    # ======================================================

    conexao.commit()

    print(
        "\nCOMMIT realizado com sucesso."
    )


except Exception:

    conexao.rollback()

    print(
        "\nERRO DURANTE A CARGA."
    )

    print(
        "ROLLBACK executado."
    )

    raise


finally:

    cursor.close()
    conexao.close()


print("\n========================================")
print("FINALIZADO")
print("========================================")