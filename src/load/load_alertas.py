import os
import psycopg2
from dotenv import load_dotenv


print("========================================")
print("GERACAO DE ALERTAS DOS FIIs")
print("========================================")

load_dotenv()


# ==========================================================
# CONEXAO
# ==========================================================

print("\nConectando ao PostgreSQL...")

conexao = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT", "5432"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)

cursor = conexao.cursor()


try:

    # ======================================================
    # ULTIMA DATA DISPONIVEL
    # ======================================================

    cursor.execute(
        """
        SELECT MAX(data)
        FROM indicadores_fii;
        """
    )

    ultima_data = cursor.fetchone()[0]

    if ultima_data is None:
        raise RuntimeError(
            "Nenhuma data encontrada em indicadores_fii."
        )

    print(
        "Ultimo pregao encontrado:",
        ultima_data
    )


    # ======================================================
    # CONTAGEM ANTES
    # ======================================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM alertas_fii
        WHERE data = %s;
        """,
        (ultima_data,)
    )

    alertas_antes = cursor.fetchone()[0]

    print(
        "Alertas existentes para o dia:",
        alertas_antes
    )


    # ======================================================
    # GERAR ALERTAS
    # ======================================================

    print("\nGerando alertas...")

    cursor.execute(
        """
        WITH candidatos AS (

            SELECT
                data,
                ticker,
                score_atencao,
                nivel_atencao,
                variacao_percentual,
                zscore_variacao_20,
                volume_relativo_20,
                negocios_relativo_20,
                liquidez_score,
                p_vp,
                dividend_yield_mes,
                total_numero_cotistas,

                CASE
                    WHEN
                        ABS(zscore_variacao_20) >= 3
                        AND volume_relativo_20 >= 2
                        AND negocios_relativo_20 >= 2
                    THEN 'MULTIPLOS_SINAIS'

                    WHEN
                        ABS(zscore_variacao_20) >= 3
                    THEN 'MOVIMENTO_ANORMAL'

                    WHEN
                        volume_relativo_20 >= 3
                        AND negocios_relativo_20 >= 2
                    THEN 'VOLUME_ANORMAL'

                    WHEN
                        negocios_relativo_20 >= 3
                    THEN 'NEGOCIACAO_ANORMAL'

                    ELSE 'ATENCAO_ELEVADA'
                END AS tipo_alerta

            FROM indicadores_fii

            WHERE
                data = %s

                AND nivel_atencao IN (
                    'ALTO',
                    'MUITO ALTO'
                )

                AND score_atencao IS NOT NULL
        ),

        mensagens AS (

            SELECT
                *,

                (
                    ticker
                    || ' - '
                    || tipo_alerta

                    || ' | Score: '
                    || ROUND(
                        score_atencao,
                        2
                    )::TEXT

                    || ' | Nivel: '
                    || nivel_atencao

                    || ' | Variacao: '
                    || COALESCE(
                        ROUND(
                            variacao_percentual,
                            2
                        )::TEXT,
                        'N/D'
                    )
                    || '%%'

                    || ' | Z-score: '
                    || COALESCE(
                        ROUND(
                            zscore_variacao_20,
                            2
                        )::TEXT,
                        'N/D'
                    )

                    || ' | Volume: '
                    || COALESCE(
                        ROUND(
                            volume_relativo_20,
                            2
                        )::TEXT,
                        'N/D'
                    )
                    || 'x'

                    || ' | Negocios: '
                    || COALESCE(
                        ROUND(
                            negocios_relativo_20,
                            2
                        )::TEXT,
                        'N/D'
                    )
                    || 'x'

                    || ' | P/VP: '
                    || COALESCE(
                        ROUND(
                            p_vp,
                            4
                        )::TEXT,
                        'N/D'
                    )

                ) AS mensagem

            FROM candidatos
        )

        INSERT INTO alertas_fii (
            data,
            ticker,
            score_atencao,
            nivel_atencao,
            tipo_alerta,
            variacao_percentual,
            zscore_variacao_20,
            volume_relativo_20,
            negocios_relativo_20,
            liquidez_score,
            p_vp,
            dividend_yield_mes,
            total_numero_cotistas,
            mensagem,
            fonte,
            data_geracao
        )

        SELECT
            data,
            ticker,
            score_atencao,
            nivel_atencao,
            tipo_alerta,
            variacao_percentual,
            zscore_variacao_20,
            volume_relativo_20,
            negocios_relativo_20,
            liquidez_score,
            p_vp,
            dividend_yield_mes,
            total_numero_cotistas,
            mensagem,
            'FII_INTELLIGENCE',
            CURRENT_TIMESTAMP

        FROM mensagens

        ON CONFLICT (data, ticker)

        DO UPDATE SET

            score_atencao =
                EXCLUDED.score_atencao,

            nivel_atencao =
                EXCLUDED.nivel_atencao,

            tipo_alerta =
                EXCLUDED.tipo_alerta,

            variacao_percentual =
                EXCLUDED.variacao_percentual,

            zscore_variacao_20 =
                EXCLUDED.zscore_variacao_20,

            volume_relativo_20 =
                EXCLUDED.volume_relativo_20,

            negocios_relativo_20 =
                EXCLUDED.negocios_relativo_20,

            liquidez_score =
                EXCLUDED.liquidez_score,

            p_vp =
                EXCLUDED.p_vp,

            dividend_yield_mes =
                EXCLUDED.dividend_yield_mes,

            total_numero_cotistas =
                EXCLUDED.total_numero_cotistas,

            mensagem =
                EXCLUDED.mensagem,

            fonte =
                'FII_INTELLIGENCE',

            data_geracao =
                CURRENT_TIMESTAMP;
        """,
        (ultima_data,)
    )

    processados = cursor.rowcount


    # ======================================================
    # VALIDAR RESULTADO
    # ======================================================

    cursor.execute(
        """
        SELECT
            COUNT(*),

            COUNT(*) FILTER (
                WHERE nivel_atencao = 'MUITO ALTO'
            ),

            COUNT(*) FILTER (
                WHERE nivel_atencao = 'ALTO'
            )

        FROM alertas_fii

        WHERE data = %s;
        """,
        (ultima_data,)
    )

    resultado = cursor.fetchone()

    total_alertas = resultado[0]
    muito_alto = resultado[1]
    alto = resultado[2]


    print("\n========================================")
    print("RESULTADO")
    print("========================================")

    print(
        "Alertas processados:",
        processados
    )

    print(
        "Total de alertas no ultimo pregao:",
        total_alertas
    )

    print(
        "Muito alto:",
        muito_alto
    )

    print(
        "Alto:",
        alto
    )


    # ======================================================
    # DISTRIBUICAO POR TIPO
    # ======================================================

    cursor.execute(
        """
        SELECT
            tipo_alerta,
            COUNT(*)

        FROM alertas_fii

        WHERE data = %s

        GROUP BY tipo_alerta

        ORDER BY COUNT(*) DESC;
        """,
        (ultima_data,)
    )

    tipos = cursor.fetchall()


    print("\n========================================")
    print("TIPOS DE ALERTA")
    print("========================================")

    for linha in tipos:
        print(linha)


    # ======================================================
    # TOP ALERTAS
    # ======================================================

    cursor.execute(
        """
        SELECT
            ticker,

            ROUND(
                score_atencao,
                2
            ),

            nivel_atencao,
            tipo_alerta,

            ROUND(
                variacao_percentual,
                2
            ),

            ROUND(
                zscore_variacao_20,
                2
            ),

            ROUND(
                volume_relativo_20,
                2
            ),

            ROUND(
                negocios_relativo_20,
                2
            ),

            ROUND(
                liquidez_score,
                2
            ),

            ROUND(
                p_vp,
                4
            ),

            mensagem

        FROM alertas_fii

        WHERE data = %s

        ORDER BY score_atencao DESC

        LIMIT 20;
        """,
        (ultima_data,)
    )

    alertas = cursor.fetchall()


    print("\n========================================")
    print("TOP ALERTAS")
    print("========================================")

    for linha in alertas:
        print(linha)


    # ======================================================
    # PROTECAO
    # ======================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM alertas_fii

        WHERE
            data = %s

            AND (
                score_atencao IS NULL

                OR nivel_atencao NOT IN (
                    'ALTO',
                    'MUITO ALTO'
                )
            );
        """,
        (ultima_data,)
    )

    alertas_invalidos = cursor.fetchone()[0]

    print(
        "\nAlertas invalidos:",
        alertas_invalidos
    )

    if alertas_invalidos > 0:
        raise RuntimeError(
            "Foram encontrados alertas invalidos."
        )


    # ======================================================
    # COMMIT
    # ======================================================

    conexao.commit()

    print(
        "\nCOMMIT realizado com sucesso."
    )


except Exception:

    conexao.rollback()

    print(
        "\nERRO DURANTE A GERACAO."
    )

    print(
        "ROLLBACK executado."
    )

    raise


finally:

    cursor.close()
    conexao.close()


print("\n========================================")
print("FINALIZADO")
print("========================================")