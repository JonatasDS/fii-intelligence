import pandas as pd

url = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi.csv"

print("Baixando base da CVM...")

df = pd.read_csv(
    url,
    sep=";",
    encoding="latin1",
    low_memory=False
)

print(f"Registros encontrados: {len(df):,}")

print("\nColunas encontradas:")
print(df.columns.tolist())
print("\nTipos de fundos encontrados:")
print(df["TP_FUNDO"].value_counts(dropna=False))

print("\nPossiveis registros de FII:")
fiis = df[
    df["TP_FUNDO"]
    .astype(str)
    .str.contains("FII", case=False, na=False)
]

print("Quantidade encontrada:", len(fiis))

print(
    fiis[
        [
            "TP_FUNDO",
            "CNPJ_FUNDO",
            "DENOM_SOCIAL",
            "SIT",
            "VL_PATRIM_LIQ",
            "ADMIN",
            "GESTOR"
        ]
    ].head(20)
)

print("\nSituacoes dos FIIs encontrados:")
print(fiis["SIT"].value_counts(dropna=False))