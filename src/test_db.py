import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Carrega as variaveis do arquivo .env
load_dotenv()

# Dados de conexao com o PostgreSQL
host = os.getenv("DB_HOST")
port = os.getenv("DB_PORT")
database = os.getenv("DB_NAME")
user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")

# Cria a conexao
engine = create_engine(
    f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
)

# Testa a conexao
try:
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT current_database();")
        )

        print("Conexao realizada com sucesso!")
        print("Banco conectado:", result.scalar())

except Exception as erro:
    print("Erro ao conectar com o PostgreSQL:")
    print(erro)
    