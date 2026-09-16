import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv


print("========================================")
print("CARGA DE COTACOES B3")
print("========================================")

load_dotenv()

ARQUIVO = "b3_cotacoes_fiis.csv"


# ==========================================================
# LER CSV
# ==========================================================

print("\nLendo arquivo...")

df = pd.read_csv(
    ARQUIVO,
    low_memory=False
)

print("Registros encontrados:", len(df))


# ==========================================================
# PREPARAR DADOS
# ==========================================================

df["data"] = pd.to_datetime(
    df["data"],
    errors="raise"
).dt.date

df["ticker"] = (
    df["ticker"]
    .astype(str)
    .str.strip()
)


colunas_numericas = [
    "preco_abertura",
    "preco_maximo",
    "preco_minimo",
    "preco_fechamento",
    "volume_financeiro",
    "quantidade_negocios"
]


for coluna in colunas_numericas:
    df[coluna] = pd.to_numeric(
        df[coluna],
        errors="coerce"
    )


# ==========================================================
# VALIDACOES
# ==========================================================

print("\n========================================")
print("VALIDACAO")
print("========================================")


duplicados = df.duplicated(
    subset=["data", "ticker"],
    keep=False
)


print(
    "Duplicidades data+ticker:",
    duplicados.sum()
)

print(
    "Datas invalidas:",
    df["data"].isna().sum()
)

print(
    "Tickers vazios:",
    df["ticker"].isna().sum()
)

print(
    "Fechamentos vazios:",
    df["preco_fechamento"].isna().sum()
)


if duplicados.any():
    raise RuntimeError(
        "Existem duplicidades data+ticker. "
        "Carga cancelada."
    )


if df["preco_fechamento"].isna().any():
    raise RuntimeError(
        "Existem precos de fechamento invalidos. "
        "Carga cancelada."
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


# ==========================================================
# CONTAGEM ANTES
# ==========================================================

cursor.execute(
    """
    SELECT COUNT(*)
    FROM cotacoes;
    """
)

total_antes = cursor.fetchone()[0]

print(
    "Registros antes da carga:",
    total_antes
)


# ==========================================================
# UPSERT
# ==========================================================

try:

    processados = 0

    print("\nIniciando UPSERT...")

    for _, linha in df.iterrows():

        cursor.execute(
            """
            INSERT INTO cotacoes (
                data,
                ticker,
                preco_abertura,
                preco_maximo,
                preco_minimo,
                preco_fechamento,
                volume_financeiro,
                quantidade_negocios,
                fonte,
                data_atualizacao
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                'B3',
                CURRENT_TIMESTAMP
            )

            ON CONFLICT (data, ticker)

            DO UPDATE SET
                preco_abertura =
                    EXCLUDED.preco_abertura,

                preco_maximo =
                    EXCLUDED.preco_maximo,

                preco_minimo =
                    EXCLUDED.preco_minimo,

                preco_fechamento =
                    EXCLUDED.preco_fechamento,

                volume_financeiro =
                    EXCLUDED.volume_financeiro,

                quantidade_negocios =
                    EXCLUDED.quantidade_negocios,

                fonte =
                    EXCLUDED.fonte,

                data_atualizacao =
                    CURRENT_TIMESTAMP;
            """,
            (
                linha["data"],
                linha["ticker"],
                linha["preco_abertura"],
                linha["preco_maximo"],
                linha["preco_minimo"],
                linha["preco_fechamento"],
                linha["volume_financeiro"],
                int(linha["quantidade_negocios"])
                if pd.notna(
                    linha["quantidade_negocios"]
                )
                else None
            )
        )

        processados += 1


    # ======================================================
    # VALIDACAO ANTES DO COMMIT
    # ======================================================

    cursor.execute(
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT ticker),
            MIN(data),
            MAX(data)
        FROM cotacoes;
        """
    )

    resultado = cursor.fetchone()

    total_depois = resultado[0]
    tickers_banco = resultado[1]
    primeira_data = resultado[2]
    ultima_data = resultado[3]


    print("\n========================================")
    print("RESULTADO")
    print("========================================")

    print(
        "Registros processados:",
        processados
    )

    print(
        "Registros no banco:",
        total_depois
    )

    print(
        "Tickers diferentes:",
        tickers_banco
    )

    print(
        "Primeira data:",
        primeira_data
    )

    print(
        "Ultima data:",
        ultima_data
    )


    # ======================================================
    # VALIDACAO DE QUANTIDADE
    # ======================================================

    if total_antes == 0:

        if total_depois != len(df):

            raise RuntimeError(
                "Quantidade no banco diferente "
                "da quantidade esperada."
            )


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