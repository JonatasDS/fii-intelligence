import pandas as pd
import requests
import zipfile
import io

print("Baixando dados da CVM...")

url = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"

resposta = requests.get(url)
resposta.raise_for_status()

zip_file = zipfile.ZipFile(io.BytesIO(resposta.content))

print("Lendo registro_classe.csv...")

with zip_file.open("registro_classe.csv") as arquivo:
    classes = pd.read_csv(
        arquivo,
        sep=";",
        encoding="latin1",
        low_memory=False
    )

print("Lendo registro_fundo.csv...")

with zip_file.open("registro_fundo.csv") as arquivo:
    fundos = pd.read_csv(
        arquivo,
        sep=";",
        encoding="latin1",
        low_memory=False
    )

print("Filtrando FIIs ativos...")

fiis = classes[
    (classes["Tipo_Classe"] == "Classes de Cotas de Fundos FII") &
    (classes["Situacao"] == "Em Funcionamento Normal")
].copy()

print("FIIs ativos encontrados:", len(fiis))

print("Juntando dados de fundo e classe...")

fiis_completos = fiis.merge(
    fundos[
        [
            "ID_Registro_Fundo",
            "CNPJ_Fundo",
            "Denominacao_Social",
            "Administrador",
            "Gestor"
        ]
    ],
    on="ID_Registro_Fundo",
    how="left",
    suffixes=("_classe", "_fundo")
)

print("Criando estrutura final...")

fiis_final = pd.DataFrame({
    "id_registro_fundo": fiis_completos["ID_Registro_Fundo"],
    "id_registro_classe": fiis_completos["ID_Registro_Classe"],
    "codigo_cvm": fiis_completos["Codigo_CVM"],
    "cnpj_fundo": fiis_completos["CNPJ_Fundo"],
    "cnpj_classe": fiis_completos["CNPJ_Classe"],
    "nome_fundo": fiis_completos["Denominacao_Social_fundo"],
    "nome_classe": fiis_completos["Denominacao_Social_classe"],
    "tipo_classe": fiis_completos["Tipo_Classe"],
    "classificacao": fiis_completos["Classificacao"],
    "classificacao_anbima": fiis_completos["Classificacao_Anbima"],
    "situacao": fiis_completos["Situacao"],
    "administrador": fiis_completos["Administrador"],
    "gestor": fiis_completos["Gestor"],
    "patrimonio_liquido": fiis_completos["Patrimonio_Liquido"],
    "data_patrimonio_liquido": fiis_completos["Data_Patrimonio_Liquido"],
    "data_inicio": fiis_completos["Data_Inicio"]
})

print("\nQuantidade final de FIIs:", len(fiis_final))

print("\nColunas finais:")
print(fiis_final.columns.tolist())

print("\nPrimeiros 10 FIIs:")
print(
    fiis_final[
        [
            "cnpj_classe",
            "nome_classe",
            "administrador",
            "gestor",
            "patrimonio_liquido"
        ]
    ].head(10)
)

print("\nValores ausentes:")
print(
    fiis_final[
        [
            "cnpj_classe",
            "nome_classe",
            "administrador",
            "gestor",
            "patrimonio_liquido"
        ]
    ].isna().sum()
)

print("\nLimpando e padronizando os dados...")

# CNPJs como texto, preservando zeros à esquerda
fiis_final["cnpj_fundo"] = (
    fiis_final["cnpj_fundo"]
    .astype("string")
    .str.replace(r"\D", "", regex=True)
    .str.zfill(14)
)

fiis_final["cnpj_classe"] = (
    fiis_final["cnpj_classe"]
    .astype("string")
    .str.replace(r"\D", "", regex=True)
    .str.zfill(14)
)

# Datas
fiis_final["data_inicio"] = pd.to_datetime(
    fiis_final["data_inicio"],
    errors="coerce"
)

fiis_final["data_patrimonio_liquido"] = pd.to_datetime(
    fiis_final["data_patrimonio_liquido"],
    errors="coerce"
)

# Patrimônio líquido como número
fiis_final["patrimonio_liquido"] = pd.to_numeric(
    fiis_final["patrimonio_liquido"],
    errors="coerce"
)

# Remove espaços extras dos textos
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
    fiis_final[coluna] = fiis_final[coluna].astype("string").str.strip()

print("Limpeza concluida!")

print("\nTipos finais das colunas:")
print(fiis_final.dtypes)

print("\nExemplo apos limpeza:")
print(
    fiis_final[
        [
            "cnpj_classe",
            "nome_classe",
            "patrimonio_liquido",
            "data_patrimonio_liquido"
        ]
    ].head()
)