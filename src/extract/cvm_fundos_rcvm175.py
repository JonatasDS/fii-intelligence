import pandas as pd
import requests
import zipfile
import io

print("Baixando cadastro atual da CVM...")

url = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"

resposta = requests.get(url)
resposta.raise_for_status()

zip_file = zipfile.ZipFile(io.BytesIO(resposta.content))

print("\nArquivos encontrados no ZIP:")
print(zip_file.namelist())

print("\nLendo registro_classe.csv...")

with zip_file.open("registro_classe.csv") as arquivo:
    classes = pd.read_csv(
        arquivo,
        sep=";",
        encoding="latin1",
        low_memory=False
    )

print("\nQuantidade de registros:", len(classes))

print("\nColunas encontradas:")
print(classes.columns.tolist())

print("\nTipos de classe encontrados:")
print(classes["Tipo_Classe"].value_counts(dropna=False))

print("\nFiltrando somente FIIs...")

fiis = classes[
    classes["Tipo_Classe"] == "Classes de Cotas de Fundos FII"
].copy()

print("Quantidade total de FIIs:", len(fiis))

print("\nSituacoes dos FIIs:")
print(fiis["Situacao"].value_counts(dropna=False))

print("\nLendo registro_fundo.csv...")

with zip_file.open("registro_fundo.csv") as arquivo:
    fundos = pd.read_csv(
        arquivo,
        sep=";",
        encoding="latin1",
        low_memory=False
    )

print("\nQuantidade de fundos:", len(fundos))

print("\nColunas de registro_fundo.csv:")
print(fundos.columns.tolist())

print("\nPrimeiros registros:")
print(fundos.head(5))