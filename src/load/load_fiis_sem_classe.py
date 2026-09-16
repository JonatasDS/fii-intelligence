import io
import os
import zipfile

import pandas as pd
import psycopg2
import requests
from dotenv import load_dotenv


print("========================================")
print("CARGA - FIIs SEM CLASSE")
print("========================================")


# ==========================================================
# CONFIGURACOES
# ==========================================================

load_dotenv()

URL_CVM = (
    "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/"
    "registro_fundo_classe.zip"
)

ARQUIVO_B3 = "b3_fiis_detalhes.csv"


# ==========================================================
# FUNCOES
# ==========================================================

def limpar_cnpj(valor):
    if pd.isna(valor):
        return None

    numeros = "".join(
        caractere
        for caractere in str(valor)
        if caractere.isdigit()
    )

    if not numeros:
        return None

    return numeros.zfill(14)


def limpar_id(valor):
    if pd.isna(valor):
        return None

    valor = str(valor).strip()

    if valor.endswith(".0"):
        valor = valor[:-2]

    return valor


def pegar_valor(linha, coluna):
    if coluna not in linha.index:
        return None

    valor = linha[coluna]

    if pd.isna(valor):
        return None

    valor = str(valor).strip()

    if not valor:
        return None

    return valor


# ==========================================================
# CARREGAR B3
# ==========================================================

print("\nLendo arquivo B3...")

if not os.path.exists(ARQUIVO_B3):
    raise FileNotFoundError(
        f"Arquivo nao encontrado: {ARQUIVO_B3}"
    )

b3 = pd.read_csv(
    ARQUIVO_B3,
    dtype=str,
    low_memory=False
)

print(
    "Registros B3:",
    len(b3)
)


if "cnpj" not in b3.columns:
    raise ValueError(
        "A coluna 'cnpj' nao existe em b3_fiis_detalhes.csv"
    )


b3["cnpj_limpo"] = (
    b3["cnpj"]
    .apply(limpar_cnpj)
)


# ==========================================================
# BAIXAR CVM
# ==========================================================

print("\nBaixando cadastro atual da CVM...")

resposta = requests.get(
    URL_CVM,
    timeout=120
)

resposta.raise_for_status()

print(
    "Download concluido:",
    len(resposta.content),
    "bytes"
)


# ==========================================================
# LER ARQUIVOS CVM
# ==========================================================

with zipfile.ZipFile(
    io.BytesIO(resposta.content)
) as arquivo_zip:

    print("\nLendo registro_fundo.csv...")

    with arquivo_zip.open(
        "registro_fundo.csv"
    ) as arquivo:

        fundos = pd.read_csv(
            arquivo,
            sep=";",
            encoding="latin1",
            dtype=str,
            low_memory=False
        )

    print("Lendo registro_classe.csv...")

    with arquivo_zip.open(
        "registro_classe.csv"
    ) as arquivo:

        classes = pd.read_csv(
            arquivo,
            sep=";",
            encoding="latin1",
            dtype=str,
            low_memory=False
        )


print(
    "\nFundos CVM:",
    len(fundos)
)

print(
    "Classes CVM:",
    len(classes)
)


# ==========================================================
# NORMALIZAR IDS E CNPJS
# ==========================================================

fundos["id_fundo_limpo"] = (
    fundos["ID_Registro_Fundo"]
    .apply(limpar_id)
)

fundos["cnpj_limpo"] = (
    fundos["CNPJ_Fundo"]
    .apply(limpar_cnpj)
)

classes["id_fundo_limpo"] = (
    classes["ID_Registro_Fundo"]
    .apply(limpar_id)
)


# ==========================================================
# IDS DE FUNDOS QUE POSSUEM CLASSE
# ==========================================================

ids_com_classe = set(
    classes[
        "id_fundo_limpo"
    ]
    .dropna()
    .unique()
)

print(
    "\nIDs de fundos com pelo menos uma classe:",
    len(ids_com_classe)
)


# ==========================================================
# PEGAR SOMENTE FUNDOS CVM SEM CLASSE
# ==========================================================

fundos_sem_classe = fundos[
    ~fundos["id_fundo_limpo"].isin(
        ids_com_classe
    )
].copy()

print(
    "Registros CVM sem classe vinculada:",
    len(fundos_sem_classe)
)


# ==========================================================
# CRUZAR COM B3
# ==========================================================

print("\nCruzando fundos sem classe com a B3...")


candidatos = fundos_sem_classe.merge(
    b3,
    on="cnpj_limpo",
    how="inner",
    suffixes=("_cvm", "_b3")
)


print(
    "Registros encontrados no cruzamento:",
    len(candidatos)
)


# ==========================================================
# TRATAR CNPJS COM MAIS DE UM REGISTRO CVM
# ==========================================================
#
# Exemplo conhecido:
# BLUE possui um registro Em Funcionamento Normal
# e outro Cancelado com o mesmo CNPJ.
#
# Priorizamos o registro mais relevante atualmente.
# ==========================================================

prioridade_situacao = {
    "Em Funcionamento Normal": 1,
    "Fase Pré-Operacional": 2,
    "Em Liquidação": 3,
    "Cancelado": 4
}


if "Situacao" in candidatos.columns:

    candidatos["_prioridade"] = (
        candidatos["Situacao"]
        .map(prioridade_situacao)
        .fillna(99)
    )

else:

    candidatos["_prioridade"] = 99


if "Data_Registro" in candidatos.columns:

    candidatos["_data_registro"] = pd.to_datetime(
        candidatos["Data_Registro"],
        errors="coerce"
    )

else:

    candidatos["_data_registro"] = pd.NaT


candidatos = candidatos.sort_values(
    by=[
        "cnpj_limpo",
        "_prioridade",
        "_data_registro"
    ],
    ascending=[
        True,
        True,
        False
    ]
)


# Uma linha B3 por CNPJ.
candidatos = candidatos.drop_duplicates(
    subset=["cnpj_limpo"],
    keep="first"
)


print(
    "FIIs sem classe unicos apos tratamento:",
    len(candidatos)
)


# ==========================================================
# MOSTRAR O QUE SERA GRAVADO
# ==========================================================

print("\n========================================")
print("FIIs IDENTIFICADOS")
print("========================================")


for _, linha in candidatos.iterrows():

    ticker = pegar_valor(
        linha,
        "trading_code"
    )

    cnpj = pegar_valor(
        linha,
        "CNPJ_Fundo"
    )

    nome = pegar_valor(
        linha,
        "Denominacao_Social"
    )

    situacao = pegar_valor(
        linha,
        "Situacao"
    )

    id_fundo = pegar_valor(
        linha,
        "ID_Registro_Fundo"
    )

    print(
        f"{ticker} | "
        f"ID Fundo: {id_fundo} | "
        f"CNPJ: {cnpj} | "
        f"Situacao: {situacao} | "
        f"{nome}"
    )


# ==========================================================
# CONECTAR POSTGRESQL
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
# UPSERT
# ==========================================================

try:

    # Registros antigos continuam preservados,
    # mas inicialmente ficam marcados como ausentes.
    cursor.execute(
        """
        UPDATE fiis_sem_classe
        SET presente_cvm = FALSE;
        """
    )

    quantidade_upsert = 0

    for _, linha in candidatos.iterrows():

        id_registro_fundo = pegar_valor(
            linha,
            "ID_Registro_Fundo"
        )

        cnpj_fundo = pegar_valor(
            linha,
            "CNPJ_Fundo"
        )

        nome_fundo = pegar_valor(
            linha,
            "Denominacao_Social"
        )

        situacao = pegar_valor(
            linha,
            "Situacao"
        )

        administrador = pegar_valor(
            linha,
            "Administrador"
        )

        gestor = pegar_valor(
            linha,
            "Gestor"
        )

        ticker = pegar_valor(
            linha,
            "trading_code"
        )

        classificacao_b3 = pegar_valor(
            linha,
            "classification"
        )

        segmento_b3 = pegar_valor(
            linha,
            "segment"
        )

        cursor.execute(
            """
            INSERT INTO fiis_sem_classe (
                id_registro_fundo,
                cnpj_fundo,
                nome_fundo,
                situacao,
                administrador,
                gestor,
                ticker,
                classificacao_b3,
                segmento_b3,
                fonte,
                presente_cvm,
                data_atualizacao
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                'CVM+B3',
                TRUE,
                CURRENT_TIMESTAMP
            )

            ON CONFLICT (id_registro_fundo)

            DO UPDATE SET
                cnpj_fundo = EXCLUDED.cnpj_fundo,
                nome_fundo = EXCLUDED.nome_fundo,
                situacao = EXCLUDED.situacao,
                administrador = EXCLUDED.administrador,
                gestor = EXCLUDED.gestor,
                ticker = EXCLUDED.ticker,
                classificacao_b3 = EXCLUDED.classificacao_b3,
                segmento_b3 = EXCLUDED.segmento_b3,
                fonte = EXCLUDED.fonte,
                presente_cvm = TRUE,
                data_atualizacao = CURRENT_TIMESTAMP;
            """,
            (
                int(id_registro_fundo),
                cnpj_fundo,
                nome_fundo,
                situacao,
                administrador,
                gestor,
                ticker,
                classificacao_b3,
                segmento_b3
            )
        )

        quantidade_upsert += 1


    conexao.commit()


    # ======================================================
    # VALIDACAO
    # ======================================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM fiis_sem_classe;
        """
    )

    total_banco = cursor.fetchone()[0]


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM fiis_sem_classe
        WHERE presente_cvm = TRUE;
        """
    )

    total_presentes = cursor.fetchone()[0]


    print("\n========================================")
    print("CARGA CONCLUIDA")
    print("========================================")

    print(
        "Registros processados:",
        quantidade_upsert
    )

    print(
        "Total em fiis_sem_classe:",
        total_banco
    )

    print(
        "Presentes na CVM atual:",
        total_presentes
    )

    print(
        "\nNenhuma alteracao foi feita "
        "na tabela fiis."
    )


except Exception:

    conexao.rollback()

    print(
        "\nERRO DURANTE A CARGA."
    )

    print(
        "A transacao foi revertida."
    )

    raise


finally:

    cursor.close()
    conexao.close()


print("\n========================================")
print("FINALIZADO")
print("========================================")