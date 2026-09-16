import io
import zipfile
import requests
import pandas as pd


print("========================================")
print("DIAGNOSTICO DOS 6 FIIs - CVM")
print("========================================")


URL = (
    "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/"
    "registro_fundo_classe.zip"
)


CNPJS_PROCURADOS = {
    "05437916000127": "EURO11",
    "14217108000145": "FIIB11",
    "39347413000182": "HUCG11",
    "16685929000131": "BLUE11",
    "63643353000120": "KOIM11",
    "49361020000187": "SLDZ11",
}


# ==========================================================
# FUNCAO PARA LIMPAR CNPJ
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


# ==========================================================
# DOWNLOAD DA BASE CVM
# ==========================================================

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


# ==========================================================
# ABRIR ZIP
# ==========================================================

with zipfile.ZipFile(
    io.BytesIO(resposta.content)
) as arquivo_zip:

    print("\nArquivos encontrados no ZIP:")

    for nome in arquivo_zip.namelist():
        print(" -", nome)

    # ------------------------------------------------------
    # CLASSES
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # FUNDOS
    # ------------------------------------------------------

    print("Lendo registro_fundo.csv...")

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


print("\nClasses:", len(classes))
print("Fundos:", len(fundos))


# ==========================================================
# MOSTRAR COLUNAS RELACIONADAS A CNPJ
# ==========================================================

print("\n========================================")
print("COLUNAS DE CNPJ")
print("========================================")

print("\nregistro_classe.csv:")

for coluna in classes.columns:

    if "CNPJ" in coluna.upper():
        print(" -", coluna)


print("\nregistro_fundo.csv:")

for coluna in fundos.columns:

    if "CNPJ" in coluna.upper():
        print(" -", coluna)


# ==========================================================
# PROCURAR EM TODAS AS COLUNAS DE CNPJ
# ==========================================================

resultados = []


def procurar(df, origem):

    colunas_cnpj = [
        coluna
        for coluna in df.columns
        if "CNPJ" in coluna.upper()
    ]

    for coluna in colunas_cnpj:

        serie_limpa = (
            df[coluna]
            .apply(limpar_cnpj)
        )

        mascara = serie_limpa.isin(
            CNPJS_PROCURADOS.keys()
        )

        encontrados = df[
            mascara
        ].copy()

        if encontrados.empty:
            continue

        encontrados[
            "_cnpj_encontrado"
        ] = serie_limpa[
            mascara
        ]

        encontrados[
            "_coluna_encontrada"
        ] = coluna

        encontrados[
            "_origem"
        ] = origem

        resultados.append(
            encontrados
        )


print("\nProcurando os 6 CNPJs...")

procurar(
    classes,
    "registro_classe.csv"
)

procurar(
    fundos,
    "registro_fundo.csv"
)


# ==========================================================
# RESULTADOS
# ==========================================================

print("\n========================================")
print("RESULTADO")
print("========================================")


if not resultados:

    print(
        "Nenhum dos 6 CNPJs foi encontrado "
        "nos arquivos atuais da CVM."
    )

else:

    resultado = pd.concat(
        resultados,
        ignore_index=True
    )

    for cnpj, ticker in CNPJS_PROCURADOS.items():

        registros = resultado[
            resultado["_cnpj_encontrado"]
            == cnpj
        ]

        print("\n----------------------------------------")
        print(ticker)
        print("CNPJ:", cnpj)
        print("----------------------------------------")

        if registros.empty:

            print(
                "NAO ENCONTRADO NA CVM"
            )

            continue

        print(
            "Quantidade de ocorrencias:",
            len(registros)
        )

        for _, linha in registros.iterrows():

            print(
                "\nOrigem:",
                linha["_origem"]
            )

            print(
                "Coluna:",
                linha["_coluna_encontrada"]
            )

            campos_interesse = [
                "ID_Registro_Fundo",
                "ID_Registro_Classe",
                "CNPJ_Fundo",
                "CNPJ_Classe",
                "Denominacao_Social",
                "Denominacao_Social_Classe",
                "Tipo_Classe",
                "Situacao",
                "Data_Registro",
                "Data_Inicio"
            ]

            for campo in campos_interesse:

                if campo in linha.index:

                    valor = linha[campo]

                    if pd.notna(valor):

                        print(
                            f"{campo}: {valor}"
                        )


# ==========================================================
# RESUMO INDIVIDUAL
# ==========================================================

print("\n========================================")
print("RESUMO DOS 6")
print("========================================")


if resultados:

    resultado = pd.concat(
        resultados,
        ignore_index=True
    )

    encontrados_cnpj = set(
        resultado["_cnpj_encontrado"]
        .dropna()
    )

else:

    encontrados_cnpj = set()


for cnpj, ticker in CNPJS_PROCURADOS.items():

    if cnpj in encontrados_cnpj:

        status = "ENCONTRADO"

    else:

        status = "NAO ENCONTRADO"

    print(
        ticker,
        "-",
        cnpj,
        "-",
        status
    )


print("\n========================================")
print("FINALIZADO")
print("========================================")

print(
    "Nenhuma alteracao foi feita "
    "no PostgreSQL."
)