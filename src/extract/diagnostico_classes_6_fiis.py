import io
import zipfile
import requests
import pandas as pd


print("========================================")
print("DIAGNOSTICO DAS CLASSES DOS 6 FIIs")
print("========================================")


URL = (
    "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/"
    "registro_fundo_classe.zip"
)


# IDs encontrados no diagnostico anterior.
#
# BLUE possui dois IDs porque a CVM retornou:
# 628  = Em Funcionamento Normal
# 3454 = Cancelado
FUNDOS = {
    "EURO11": ["435"],
    "FIIB11": ["579"],
    "HUCG11": ["1255"],
    "BLUE11": ["628", "3454"],
    "KOIM11": ["2277"],
    "SLDZ11": ["1603"],
}


print("\nBaixando cadastro atual da CVM...")

resposta = requests.get(
    URL,
    timeout=120
)

resposta.raise_for_status()

print(
    "Download concluido:",
    len(resposta.content),
    "bytes"
)


with zipfile.ZipFile(
    io.BytesIO(resposta.content)
) as arquivo_zip:

    print("\nLendo registro_classe.csv...")

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
    "Total de classes na CVM:",
    len(classes)
)


# ==========================================================
# VERIFICAR COLUNAS
# ==========================================================

print("\n========================================")
print("COLUNAS IMPORTANTES")
print("========================================")

colunas_interesse = [
    "ID_Registro_Fundo",
    "ID_Registro_Classe",
    "CNPJ_Classe",
    "Denominacao_Social_Classe",
    "Tipo_Classe",
    "Situacao",
    "Data_Registro",
    "Data_Inicio"
]

for coluna in colunas_interesse:

    if coluna in classes.columns:
        print("OK  -", coluna)

    else:
        print("NAO EXISTE -", coluna)


if "ID_Registro_Fundo" not in classes.columns:

    print(
        "\nERRO: registro_classe.csv nao possui "
        "a coluna ID_Registro_Fundo."
    )

    raise SystemExit


# ==========================================================
# NORMALIZAR ID
# ==========================================================

classes["_id_fundo_limpo"] = (
    classes["ID_Registro_Fundo"]
    .astype(str)
    .str.strip()
    .str.replace(".0", "", regex=False)
)


# ==========================================================
# PROCURAR CLASSES LIGADAS A CADA FUNDO
# ==========================================================

print("\n========================================")
print("RESULTADOS")
print("========================================")


resumo = []


for ticker, ids_fundo in FUNDOS.items():

    print("\n----------------------------------------")
    print(ticker)
    print(
        "IDs Registro Fundo:",
        ", ".join(ids_fundo)
    )
    print("----------------------------------------")

    encontrados = classes[
        classes["_id_fundo_limpo"].isin(
            ids_fundo
        )
    ].copy()

    quantidade = len(encontrados)

    resumo.append(
        {
            "ticker": ticker,
            "ids_fundo": ", ".join(ids_fundo),
            "classes_encontradas": quantidade
        }
    )

    if encontrados.empty:

        print(
            "NENHUMA CLASSE VINCULADA ENCONTRADA"
        )

        continue

    print(
        "Classes vinculadas encontradas:",
        quantidade
    )

    for _, linha in encontrados.iterrows():

        print("\n>>> CLASSE")

        for coluna in colunas_interesse:

            if coluna not in linha.index:
                continue

            valor = linha[coluna]

            if pd.isna(valor):
                continue

            print(
                f"{coluna}: {valor}"
            )


# ==========================================================
# RESUMO
# ==========================================================

print("\n========================================")
print("RESUMO")
print("========================================")


for item in resumo:

    print(
        item["ticker"],
        "- IDs Fundo:",
        item["ids_fundo"],
        "- Classes encontradas:",
        item["classes_encontradas"]
    )


print("\n========================================")
print("FINALIZADO")
print("========================================")

print(
    "Nenhuma alteracao foi feita "
    "no PostgreSQL."
)