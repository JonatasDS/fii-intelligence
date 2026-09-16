import io
import zipfile
import requests
import pandas as pd
from datetime import datetime


print("========================================")
print("B3 - COTACOES HISTORICAS")
print("========================================")


# ==========================================================
# CONFIGURACAO
# ==========================================================

ANO = datetime.now().year

URL = (
    f"https://bvmf.bmfbovespa.com.br/"
    f"InstDados/SerHist/COTAHIST_A{ANO}.ZIP"
)

ARQUIVO_SAIDA = "b3_cotacoes_fiis.csv"


# ==========================================================
# DOWNLOAD
# ==========================================================

print(f"\nBaixando COTAHIST {ANO}...")
print("Fonte: B3")

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

    arquivos = arquivo_zip.namelist()

    print("\nArquivos no ZIP:")

    for nome in arquivos:
        print(" -", nome)

    arquivo_txt = next(
        nome
        for nome in arquivos
        if nome.upper().endswith(".TXT")
    )

    print(
        "\nLendo:",
        arquivo_txt
    )

    conteudo = arquivo_zip.read(
        arquivo_txt
    ).decode(
        "latin1"
    )


# ==========================================================
# INTERPRETAR COTAHIST
# ==========================================================

registros = []


for linha in conteudo.splitlines():

    # Registro 01 = cotacao
    if linha[0:2] != "01":
        continue

    try:

        data = linha[2:10]

        codbdi = linha[10:12].strip()

        ticker = linha[12:24].strip()

        tipo_mercado = linha[24:27].strip()

        nome_resumido = linha[27:39].strip()

        especificacao = linha[39:49].strip()

        preco_abertura = (
            int(linha[56:69]) / 100
        )

        preco_maximo = (
            int(linha[69:82]) / 100
        )

        preco_minimo = (
            int(linha[82:95]) / 100
        )

        preco_fechamento = (
            int(linha[108:121]) / 100
        )

        quantidade_negocios = int(
            linha[147:152]
        )

        volume_financeiro = (
            int(linha[170:188]) / 100
        )

        registros.append(
            {
                "data": data,
                "ticker": ticker,
                "codbdi": codbdi,
                "tipo_mercado": tipo_mercado,
                "nome_resumido": nome_resumido,
                "especificacao": especificacao,
                "preco_abertura": preco_abertura,
                "preco_maximo": preco_maximo,
                "preco_minimo": preco_minimo,
                "preco_fechamento": preco_fechamento,
                "quantidade_negocios": quantidade_negocios,
                "volume_financeiro": volume_financeiro
            }
        )

    except Exception:
        continue


df = pd.DataFrame(
    registros
)


print(
    "\nRegistros de cotacao encontrados:",
    len(df)
)


# ==========================================================
# CONVERTER DATA
# ==========================================================

df["data"] = pd.to_datetime(
    df["data"],
    format="%Y%m%d",
    errors="coerce"
)


# ==========================================================
# CARREGAR LISTA B3 DE FIIs
# ==========================================================

print(
    "\nCarregando lista oficial de FIIs..."
)

fiis = pd.read_csv(
    "b3_fiis_detalhes.csv",
    dtype=str,
    low_memory=False
)


tickers_fii = set(
    fiis[
        "trading_code"
    ]
    .dropna()
    .astype(str)
    .str.strip()
)


print(
    "Tickers FII conhecidos:",
    len(tickers_fii)
)


# ==========================================================
# FILTRAR FIIs
# ==========================================================

cotacoes_fii = df[
    df["ticker"].isin(
        tickers_fii
    )
].copy()


print(
    "Registros de FIIs encontrados:",
    len(cotacoes_fii)
)

print(
    "FIIs diferentes com cotacao:",
    cotacoes_fii[
        "ticker"
    ].nunique()
)


# ==========================================================
# VALIDACOES
# ==========================================================

duplicados = cotacoes_fii.duplicated(
    subset=[
        "data",
        "ticker"
    ],
    keep=False
)


print(
    "Duplicidades data+ticker:",
    duplicados.sum()
)


print(
    "Primeira data:",
    cotacoes_fii["data"].min()
)

print(
    "Ultima data:",
    cotacoes_fii["data"].max()
)


# ==========================================================
# AMOSTRA
# ==========================================================

print("\n========================================")
print("AMOSTRA")
print("========================================")


print(
    cotacoes_fii[
        [
            "data",
            "ticker",
            "preco_abertura",
            "preco_maximo",
            "preco_minimo",
            "preco_fechamento",
            "quantidade_negocios",
            "volume_financeiro"
        ]
    ]
    .tail(20)
    .to_string(index=False)
)


# ==========================================================
# SALVAR CSV
# ==========================================================

cotacoes_fii.to_csv(
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
    "Nenhuma alteracao foi feita "
    "no PostgreSQL."
)