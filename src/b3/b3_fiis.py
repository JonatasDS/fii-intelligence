import requests
import base64
import json
import pandas as pd
import time
from pathlib import Path


print("========================================")
print("COLETA DETALHADA DE FIIs DA B3")
print("========================================")


BASE_URL = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "fundsListedProxy/Search/"
)

ENDPOINT_LISTA = BASE_URL + "GetListFunds/"
ENDPOINT_DETALHE = BASE_URL + "GetDetailFund/"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


session = requests.Session()
session.headers.update(HEADERS)


def gerar_base64(dados):

    texto = json.dumps(
        dados,
        separators=(",", ":"),
        ensure_ascii=False
    )

    return base64.b64encode(
        texto.encode("utf-8")
    ).decode("ascii")


def consultar_lista(pagina, tamanho=100):

    filtro = {
        "typeFund": "FII",
        "pageNumber": pagina,
        "pageSize": tamanho,
        "keyword": "",
        "language": "pt-br"
    }

    parametro = gerar_base64(filtro)

    url = ENDPOINT_LISTA + parametro

    resposta = session.get(
        url,
        timeout=60
    )

    resposta.raise_for_status()

    return resposta.json()


def consultar_detalhe(id_fnet, acronym):

    filtro = {
        "language": "pt-br",
        "idFNET": str(id_fnet),
        "idCEM": acronym,
        "typeFund": "FII"
    }

    parametro = gerar_base64(filtro)

    url = ENDPOINT_DETALHE + parametro

    resposta = session.get(
        url,
        timeout=60
    )

    resposta.raise_for_status()

    if not resposta.text.strip():
        return None

    return resposta.json()


# ==========================================================
# COLETAR LISTA COMPLETA
# ==========================================================

print("\nConsultando lista de FIIs...")

primeira = consultar_lista(
    pagina=1,
    tamanho=100
)

total_paginas = primeira["page"]["totalPages"]
total_registros = primeira["page"]["totalRecords"]

fundos = []

fundos.extend(
    primeira.get("results", [])
)

for pagina in range(
    2,
    total_paginas + 1
):

    print(
        f"Lista pagina {pagina}/{total_paginas}"
    )

    dados = consultar_lista(
        pagina=pagina,
        tamanho=100
    )

    fundos.extend(
        dados.get("results", [])
    )


print("\nTotal informado pela B3:", total_registros)
print("Total coletado na lista:", len(fundos))


# ==========================================================
# COLETAR DETALHES
# ==========================================================

detalhes = []

erros = []


print("\n========================================")
print("COLETANDO DETALHES")
print("========================================")


for indice, fundo in enumerate(
    fundos,
    start=1
):

    id_fnet = fundo.get("id")
    acronym = fundo.get("acronym")

    print(
        f"[{indice}/{len(fundos)}] "
        f"{acronym} - ID {id_fnet}"
    )

    try:

        detalhe = consultar_detalhe(
            id_fnet=id_fnet,
            acronym=acronym
        )

        if detalhe:

            registro = {
                "id_fnet": detalhe.get("idFNET"),
                "type_fnet": detalhe.get("typeFNET"),
                "type": detalhe.get("type"),
                "type_name": detalhe.get("typeName"),
                "acronym": detalhe.get("acronym"),
                "trading_name": detalhe.get("tradingName"),
                "trading_code": detalhe.get("tradingCode"),
                "trading_code_others": detalhe.get(
                    "tradingCodeOthers"
                ),
                "cnpj": detalhe.get("cnpj"),
                "classification": detalhe.get(
                    "classification"
                ),
                "website": detalhe.get("webSite"),
                "fund_address": detalhe.get(
                    "fundAddress"
                ),
                "fund_phone_ddd": detalhe.get(
                    "fundPhoneNumberDDD"
                ),
                "fund_phone": detalhe.get(
                    "fundPhoneNumber"
                ),
                "position_manager": detalhe.get(
                    "positionManager"
                ),
                "manager_name": detalhe.get(
                    "managerName"
                ),
                "fund_name": detalhe.get(
                    "fundName"
                ),
                "quota_count": detalhe.get(
                    "quotaCount"
                ),
                "quota_date_approved": detalhe.get(
                    "quotaDateApproved"
                ),
                "segment": detalhe.get(
                    "segment"
                )
            }

            share_holder = detalhe.get(
                "shareHolder"
            )

            if isinstance(
                share_holder,
                dict
            ):

                registro[
                    "share_holder_name"
                ] = share_holder.get(
                    "shareHolderName"
                )

                registro[
                    "share_holder_email"
                ] = share_holder.get(
                    "shareHolderEmail"
                )

            else:

                registro[
                    "share_holder_name"
                ] = None

                registro[
                    "share_holder_email"
                ] = None

            detalhes.append(
                registro
            )

        else:

            erros.append(
                {
                    "id_fnet": id_fnet,
                    "acronym": acronym,
                    "erro": "Resposta vazia"
                }
            )

    except Exception as erro:

        erros.append(
            {
                "id_fnet": id_fnet,
                "acronym": acronym,
                "erro": str(erro)
            }
        )

        print(
            "ERRO:",
            erro
        )

    time.sleep(0.15)


# ==========================================================
# DATAFRAME
# ==========================================================

df = pd.DataFrame(
    detalhes
)


print("\n========================================")
print("VALIDACAO")
print("========================================")

print(
    "Detalhes coletados:",
    len(df)
)

print(
    "Erros:",
    len(erros)
)


if not df.empty:

    print(
        "\nTrading codes preenchidos:",
        df["trading_code"].notna().sum()
    )

    print(
        "CNPJs preenchidos:",
        df["cnpj"].notna().sum()
    )

    print(
        "Classificacoes preenchidas:",
        df["classification"].notna().sum()
    )

    print(
        "Segmentos preenchidos:",
        df["segment"].notna().sum()
    )


# ==========================================================
# DUPLICADOS
# ==========================================================

if not df.empty:

    print(
        "\nIDs FNET duplicados:",
        df["id_fnet"].duplicated().sum()
    )

    print(
        "Trading codes duplicados:",
        df["trading_code"].duplicated().sum()
    )

    print(
        "CNPJs duplicados:",
        df["cnpj"].duplicated().sum()
    )


# ==========================================================
# AMOSTRA
# ==========================================================

if not df.empty:

    print("\n========================================")
    print("AMOSTRA")
    print("========================================")

    colunas = [
        "id_fnet",
        "acronym",
        "trading_code",
        "cnpj",
        "fund_name",
        "classification",
        "segment",
        "position_manager"
    ]

    print(
        df[colunas]
        .head(20)
        .to_string(index=False)
    )


# ==========================================================
# SALVAR ARQUIVOS
# ==========================================================

PASTA_PROJETO = (
    Path(__file__)
    .resolve()
    .parents[2]
)


arquivo_detalhes = (
    PASTA_PROJETO
    / "b3_fiis_detalhes.csv"
)


df.to_csv(
    arquivo_detalhes,
    index=False,
    encoding="utf-8-sig"
)


print("\n========================================")
print("ARQUIVO PRINCIPAL")
print("========================================")

print(
    arquivo_detalhes
)


if erros:

    arquivo_erros = (
        PASTA_PROJETO
        / "b3_fiis_erros.csv"
    )

    pd.DataFrame(
        erros
    ).to_csv(
        arquivo_erros,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        "\nArquivo de erros:"
    )

    print(
        arquivo_erros
    )


print("\n========================================")
print("RESUMO FINAL")
print("========================================")

print(
    "FIIs na lista B3:",
    len(fundos)
)

print(
    "Detalhes obtidos:",
    len(df)
)

print(
    "Falhas:",
    len(erros)
)

print(
    "\nNenhuma alteracao foi feita "
    "no PostgreSQL."
)