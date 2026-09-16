from pathlib import Path
from datetime import datetime
import subprocess
import sys
import time


# ============================================================
# CONFIGURAÇÃO
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
PYTHON = BASE_DIR / ".venv" / "Scripts" / "python.exe"

ETAPAS = [
    ("1. Atualização cadastral CVM", "src/load/load_fiis.py"),
    ("2. Coleta detalhada B3", "src/b3/b3_fiis.py"),
    ("3. FIIs sem classe", "src/load/load_fiis_sem_classe.py"),
    ("4. Associação de tickers B3", "src/b3/aplicar_tickers_b3.py"),
    ("5. Cotações históricas B3", "src/b3/cotahist_b3.py"),
    ("6. Carga das cotações", "src/load/load_cotacoes.py"),
    ("7. Fundamentos mensais CVM", "src/extract/cvm_fundamentos_fii.py"),
    ("8. Carga dos fundamentos", "src/load/load_fundamentos.py"),
    ("9. Indicadores e Score de Atenção", "src/load/load_indicadores.py"),
    ("10. Geração de alertas", "src/load/load_alertas.py"),
]


def executar_etapa(numero, nome, caminho_relativo):
    script = BASE_DIR / caminho_relativo

    print("\n" + "=" * 70)
    print(f"ETAPA {numero}/{len(ETAPAS)}")
    print(nome)
    print(f"Script: {caminho_relativo}")
    print("=" * 70)

    if not script.exists():
        raise FileNotFoundError(
            f"Script não encontrado: {script}"
        )

    inicio = time.time()

    resultado = subprocess.run(
        [str(PYTHON), str(script)],
        cwd=str(BASE_DIR),
        check=False
    )

    duracao = time.time() - inicio

    if resultado.returncode != 0:
        raise RuntimeError(
            f"{nome} falhou com código {resultado.returncode}."
        )

    print(f"\nOK - {nome}")
    print(f"Tempo: {duracao:.1f} segundos")


def main():
    inicio_pipeline = datetime.now()

    print("\n" + "=" * 70)
    print("FII INTELLIGENCE - ATUALIZAÇÃO DO PIPELINE")
    print("=" * 70)
    print(
        "Início:",
        inicio_pipeline.strftime("%d/%m/%Y %H:%M:%S")
    )

    if not PYTHON.exists():
        print("\nERRO:")
        print(f"Python da venv não encontrado em: {PYTHON}")
        sys.exit(1)

    try:
        for numero, (nome, script) in enumerate(ETAPAS, start=1):
            executar_etapa(numero, nome, script)

    except Exception as erro:
        print("\n" + "=" * 70)
        print("PIPELINE INTERROMPIDO")
        print("=" * 70)
        print(f"Erro: {erro}")
        print(
            "Horário:",
            datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        )
        sys.exit(1)

    fim_pipeline = datetime.now()
    duracao_total = fim_pipeline - inicio_pipeline

    print("\n" + "=" * 70)
    print("PIPELINE CONCLUÍDO COM SUCESSO")
    print("=" * 70)
    print(
        "Fim:",
        fim_pipeline.strftime("%d/%m/%Y %H:%M:%S")
    )
    print(f"Duração total: {duracao_total}")

    print("\nDados atualizados:")
    print("- Cadastro de FIIs")
    print("- Dados B3")
    print("- Tickers")
    print("- Cotações")
    print("- Fundamentos")
    print("- Indicadores")
    print("- Score de Atenção")
    print("- Alertas")

    print("\nPróximo passo:")
    print("Atualizar o Power BI para visualizar os novos dados.")


if __name__ == "__main__":
    main()
