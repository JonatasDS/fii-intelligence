import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

host = os.getenv("DB_HOST")
port = os.getenv("DB_PORT")
database = os.getenv("DB_NAME")
user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")

engine = create_engine(
    f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
)

sql_file = os.path.join("sql", "create_tables.sql")

try:
    with open(sql_file, "r", encoding="utf-8") as arquivo:
        sql = arquivo.read()

    with engine.begin() as connection:
        connection.execute(text(sql))

    print("Tabela criada com sucesso!")

except Exception as erro:
    print("Erro ao criar a tabela:")
    print(erro)