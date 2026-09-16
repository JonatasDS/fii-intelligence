import os
import pandas as pd
import requests
import zipfile
import io

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# ==========================================================
# 1. CONFIGURACOES
# ==========================================================

load_dotenv()

print("Iniciando atualizacao dos FIIs...")


# ==========================================================
# 2. BAIXAR DADOS DA CVM
# ==========================================================

print("\nBaixando dados da CVM...")

url = (
    "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/"
    "registro_fundo_classe.zip"
)

resposta = requests.get(
    url,
    timeout=60
)

resposta.raise_for_status()

zip_file = zipfile.ZipFile(
    io.BytesIO(resposta.content)
)


# ==========================================================
# 3. LER REGISTRO DE CLASSES
# ==========================================================

print("Lendo registro_classe.csv...")

with zip_file.open("registro_classe.csv") as arquivo:

    classes = pd.read_csv(
        arquivo,
        sep=";",
        encoding="latin1",
        low_memory=False
    )


# ==========================================================
# 4. LER REGISTRO DE FUNDOS
# ==========================================================

print("Lendo registro_fundo.csv...")

with zip_file.open("registro_fundo.csv") as arquivo:

    fundos = pd.read_csv(
        arquivo,
        sep=";",
        encoding="latin1",
        low_memory=False
    )


# ==========================================================
# 5. FILTRAR TODAS AS CLASSES DE FII
# ==========================================================

print("\nFiltrando todas as classes de FIIs...")

fiis = classes[
    classes["Tipo_Classe"]
    == "Classes de Cotas de Fundos FII"
].copy()

print(
    "FIIs encontrados:",
    len(fiis)
)

print("\nSituacoes encontradas:")

print(
    fiis["Situacao"]
    .value_counts(
        dropna=False
    )
)


# ==========================================================
# 6. FUNCAO PARA CONSOLIDAR CAMPOS
# ==========================================================

def juntar_valores_unicos(serie):

    valores = (
        serie
        .dropna()
        .astype(str)
        .str.strip()
    )

    valores = [
        valor
        for valor in valores.unique()
        if valor != ""
    ]

    if len(valores) == 0:
        return pd.NA

    return " | ".join(valores)


# ==========================================================
# 7. CONSOLIDAR FUNDOS
# ==========================================================

print("\nConsolidando registros de fundos...")

fundos_consolidados = (
    fundos
    .groupby(
        "ID_Registro_Fundo",
        as_index=False
    )
    .agg({
        "CNPJ_Fundo": "first",
        "Denominacao_Social": "first",
        "Administrador": juntar_valores_unicos,
        "Gestor": juntar_valores_unicos
    })
)

print(
    "Fundos unicos:",
    len(fundos_consolidados)
)


# ==========================================================
# 8. MERGE CLASSE + FUNDO
# ==========================================================

print("\nJuntando dados de fundo e classe...")

fiis_completos = fiis.merge(
    fundos_consolidados,
    on="ID_Registro_Fundo",
    how="left",
    validate="many_to_one",
    suffixes=(
        "_classe",
        "_fundo"
    )
)

print(
    "Quantidade apos o merge:",
    len(fiis_completos)
)


# ==========================================================
# 9. CRIAR DATAFRAME FINAL
# ==========================================================

fiis_final = pd.DataFrame({

    "id_registro_fundo":
        fiis_completos["ID_Registro_Fundo"],

    "id_registro_classe":
        fiis_completos["ID_Registro_Classe"],

    "codigo_cvm":
        fiis_completos["Codigo_CVM"],

    "cnpj_fundo":
        fiis_completos["CNPJ_Fundo"],

    "cnpj_classe":
        fiis_completos["CNPJ_Classe"],

    "nome_fundo":
        fiis_completos[
            "Denominacao_Social_fundo"
        ],

    "nome_classe":
        fiis_completos[
            "Denominacao_Social_classe"
        ],

    "tipo_classe":
        fiis_completos["Tipo_Classe"],

    "classificacao":
        fiis_completos["Classificacao"],

    "classificacao_anbima":
        fiis_completos[
            "Classificacao_Anbima"
        ],

    "situacao":
        fiis_completos["Situacao"],

    "administrador":
        fiis_completos["Administrador"],

    "gestor":
        fiis_completos["Gestor"],

    "patrimonio_liquido":
        fiis_completos[
            "Patrimonio_Liquido"
        ],

    "data_patrimonio_liquido":
        fiis_completos[
            "Data_Patrimonio_Liquido"
        ],

    "data_inicio":
        fiis_completos["Data_Inicio"],

    "ticker":
        pd.NA,

    "segmento":
        pd.NA,

    "fonte":
        "CVM",

    "presente_cvm":
        True
})


# ==========================================================
# 10. LIMPAR CNPJs
# ==========================================================

print("\nLimpando e padronizando dados...")

for coluna in [
    "cnpj_fundo",
    "cnpj_classe"
]:

    fiis_final[coluna] = (
        fiis_final[coluna]
        .astype("string")
        .str.replace(
            r"\D",
            "",
            regex=True
        )
    )

    fiis_final[coluna] = (
        fiis_final[coluna]
        .where(
            fiis_final[coluna].isna(),
            fiis_final[coluna].str.zfill(14)
        )
    )


# ==========================================================
# 11. DATAS
# ==========================================================

fiis_final[
    "data_inicio"
] = pd.to_datetime(
    fiis_final["data_inicio"],
    errors="coerce"
)

fiis_final[
    "data_patrimonio_liquido"
] = pd.to_datetime(
    fiis_final[
        "data_patrimonio_liquido"
    ],
    errors="coerce"
)


# ==========================================================
# 12. PATRIMONIO
# ==========================================================

fiis_final[
    "patrimonio_liquido"
] = pd.to_numeric(
    fiis_final[
        "patrimonio_liquido"
    ],
    errors="coerce"
)


# ==========================================================
# 13. LIMPAR TEXTOS
# ==========================================================

colunas_texto = [

    "nome_fundo",
    "nome_classe",
    "tipo_classe",
    "classificacao",
    "classificacao_anbima",
    "situacao",
    "administrador",
    "gestor"

]

for coluna in colunas_texto:

    fiis_final[coluna] = (
        fiis_final[coluna]
        .astype("string")
        .str.strip()
    )

print("Limpeza concluida!")


# ==========================================================
# 14. VALIDACAO
# ==========================================================

print("\n========================================")
print("VALIDACAO")
print("========================================")

duplicados_id = (
    fiis_final[
        "id_registro_classe"
    ]
    .duplicated()
    .sum()
)

print(
    "Quantidade recebida:",
    len(fiis_final)
)

print(
    "Duplicados em id_registro_classe:",
    duplicados_id
)

if duplicados_id != 0:

    print("\nERRO:")
    print("Existem IDs duplicados.")
    print("Atualizacao cancelada.")

    raise SystemExit


# ==========================================================
# 15. CONEXAO POSTGRESQL
# ==========================================================

print("\nConectando ao PostgreSQL...")

host = os.getenv("DB_HOST")
port = os.getenv("DB_PORT")
database = os.getenv("DB_NAME")
user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")

engine = create_engine(
    f"postgresql+psycopg2://"
    f"{user}:{password}@"
    f"{host}:{port}/"
    f"{database}"
)


# ==========================================================
# 16. LER DADOS ATUAIS DO BANCO
# ==========================================================

print("\nLendo dados atuais do banco...")

fiis_banco = pd.read_sql(
    """
    SELECT
        id_registro_classe,
        nome_classe,
        situacao,
        administrador,
        gestor,
        patrimonio_liquido,
        presente_cvm
    FROM fiis
    """,
    engine
)

print(
    "Registros atuais no banco:",
    len(fiis_banco)
)


# ==========================================================
# 17. IDENTIFICAR NOVOS FIIs
# ==========================================================

ids_banco = set(
    fiis_banco[
        "id_registro_classe"
    ].dropna()
)

novos_fiis = fiis_final[
    ~fiis_final[
        "id_registro_classe"
    ].isin(ids_banco)
].copy()

print(
    "Novos FIIs encontrados:",
    len(novos_fiis)
)


# ==========================================================
# 18. IDENTIFICAR AUSENTES NA CVM
# ==========================================================

ids_cvm = set(
    fiis_final[
        "id_registro_classe"
    ].dropna()
)

ausentes_cvm = fiis_banco[
    ~fiis_banco[
        "id_registro_classe"
    ].isin(ids_cvm)
].copy()

print(
    "FIIs ausentes na fotografia atual da CVM:",
    len(ausentes_cvm)
)


# ==========================================================
# 19. COMPARAR ALTERACOES
# ==========================================================

print("\nComparando alteracoes...")

campos_monitorados = [
    "nome_classe",
    "situacao",
    "administrador",
    "gestor",
    "patrimonio_liquido"
]

comparacao = fiis_final.merge(
    fiis_banco,
    on="id_registro_classe",
    how="left",
    suffixes=(
        "_novo",
        "_antigo"
    )
)

historico = []

for _, linha in comparacao.iterrows():

    id_classe = linha[
        "id_registro_classe"
    ]

    if id_classe not in ids_banco:
        continue

    for campo in campos_monitorados:

        valor_novo = linha[
            f"{campo}_novo"
        ]

        valor_antigo = linha[
            f"{campo}_antigo"
        ]

        if pd.isna(valor_novo):
            valor_novo_comparacao = None
        else:
            valor_novo_comparacao = str(
                valor_novo
            )

        if pd.isna(valor_antigo):
            valor_antigo_comparacao = None
        else:
            valor_antigo_comparacao = str(
                valor_antigo
            )

        if (
            valor_novo_comparacao
            != valor_antigo_comparacao
        ):

            historico.append({

                "id_registro_classe":
                    int(id_classe),

                "campo_alterado":
                    campo,

                "valor_anterior":
                    valor_antigo_comparacao,

                "valor_novo":
                    valor_novo_comparacao,

                "fonte":
                    "CVM"

            })


historico_df = pd.DataFrame(
    historico
)

print(
    "Alteracoes encontradas:",
    len(historico_df)
)


# ==========================================================
# 20. GRAVAR HISTORICO
# ==========================================================

if len(historico_df) > 0:

    print(
        "\nGravando historico de alteracoes..."
    )

    historico_df.to_sql(
        "fiis_historico",
        engine,
        if_exists="append",
        index=False,
        method="multi"
    )

    print(
        "Historico gravado com sucesso!"
    )

else:

    print(
        "\nNenhuma alteracao cadastral encontrada."
    )


# ==========================================================
# 21. MARCAR TODOS COMO AUSENTES
# ==========================================================

print(
    "\nMarcando registros antigos como ausentes..."
)

with engine.begin() as connection:

    connection.execute(
        text(
            """
            UPDATE fiis
            SET presente_cvm = FALSE;
            """
        )
    )

print(
    "Marcacao concluida."
)


# ==========================================================
# 22. CRIAR STAGING
# ==========================================================

print("\nCriando tabela staging...")

fiis_final.to_sql(
    "fiis_staging",
    engine,
    if_exists="replace",
    index=False,
    method="multi",
    chunksize=200
)

print(
    "Tabela staging criada."
)


# ==========================================================
# 23. UPSERT
# ==========================================================

print("\n========================================")
print("EXECUTANDO UPSERT")
print("========================================")

sql_upsert = text("""

INSERT INTO fiis (

    id_registro_fundo,
    id_registro_classe,
    codigo_cvm,
    cnpj_fundo,
    cnpj_classe,
    nome_fundo,
    nome_classe,
    tipo_classe,
    classificacao,
    classificacao_anbima,
    situacao,
    administrador,
    gestor,
    patrimonio_liquido,
    data_patrimonio_liquido,
    data_inicio,
    ticker,
    segmento,
    fonte,
    presente_cvm,
    data_atualizacao

)

SELECT

    id_registro_fundo,
    id_registro_classe,
    codigo_cvm,
    cnpj_fundo,
    cnpj_classe,
    nome_fundo,
    nome_classe,
    tipo_classe,
    classificacao,
    classificacao_anbima,
    situacao,
    administrador,
    gestor,
    patrimonio_liquido,
    data_patrimonio_liquido,
    data_inicio,
    ticker,
    segmento,
    fonte,
    presente_cvm,
    CURRENT_TIMESTAMP

FROM fiis_staging

ON CONFLICT (
    id_registro_classe
)

DO UPDATE SET

    id_registro_fundo =
        EXCLUDED.id_registro_fundo,

    codigo_cvm =
        EXCLUDED.codigo_cvm,

    cnpj_fundo =
        EXCLUDED.cnpj_fundo,

    cnpj_classe =
        EXCLUDED.cnpj_classe,

    nome_fundo =
        EXCLUDED.nome_fundo,

    nome_classe =
        EXCLUDED.nome_classe,

    tipo_classe =
        EXCLUDED.tipo_classe,

    classificacao =
        EXCLUDED.classificacao,

    classificacao_anbima =
        EXCLUDED.classificacao_anbima,

    situacao =
        EXCLUDED.situacao,

    administrador =
        EXCLUDED.administrador,

    gestor =
        EXCLUDED.gestor,

    patrimonio_liquido =
        EXCLUDED.patrimonio_liquido,

    data_patrimonio_liquido =
        EXCLUDED.data_patrimonio_liquido,

    data_inicio =
        EXCLUDED.data_inicio,

    fonte =
        EXCLUDED.fonte,

    presente_cvm =
        TRUE,

    data_atualizacao =
        CURRENT_TIMESTAMP;

""")


try:

    with engine.begin() as connection:

        connection.execute(
            sql_upsert
        )

    print(
        "UPSERT concluido com sucesso!"
    )

except Exception as erro:

    print("\nERRO NO UPSERT")

    print(
        "Tipo:",
        type(erro).__name__
    )

    print(
        "Causa:",
        getattr(
            erro,
            "orig",
            erro
        )
    )

    raise SystemExit


# ==========================================================
# 24. REMOVER STAGING
# ==========================================================

print(
    "\nRemovendo tabela staging..."
)

with engine.begin() as connection:

    connection.execute(
        text(
            "DROP TABLE IF EXISTS "
            "fiis_staging;"
        )
    )

print(
    "Tabela staging removida."
)


# ==========================================================
# 25. RESULTADOS FINAIS
# ==========================================================

with engine.connect() as connection:

    total_final = (
        connection.execute(
            text(
                "SELECT COUNT(*) "
                "FROM fiis;"
            )
        )
        .scalar()
    )

    total_presentes = (
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM fiis
                WHERE presente_cvm = TRUE;
                """
            )
        )
        .scalar()
    )

    total_ausentes = (
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM fiis
                WHERE presente_cvm = FALSE;
                """
            )
        )
        .scalar()
    )

    total_ativos = (
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM fiis
                WHERE situacao =
                'Em Funcionamento Normal'
                AND presente_cvm = TRUE;
                """
            )
        )
        .scalar()
    )


print("\n========================================")
print("PROCESSAMENTO FINALIZADO")
print("========================================")

print(
    "Total historico no banco:",
    total_final
)

print(
    "Presentes na CVM atual:",
    total_presentes
)

print(
    "Ausentes na CVM atual:",
    total_ausentes
)

print(
    "FIIs ativos e presentes:",
    total_ativos
)

print(
    "Novos FIIs nesta execucao:",
    len(novos_fiis)
)

print(
    "Alteracoes registradas:",
    len(historico_df)
)

print("========================================")