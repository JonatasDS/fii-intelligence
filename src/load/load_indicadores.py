import os
import psycopg2
from dotenv import load_dotenv


print("========================================")
print("CARGA DE INDICADORES DIARIOS")
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
    # CONTAGEM ANTES
    # ======================================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM indicadores_fii;
        """
    )

    total_antes = cursor.fetchone()[0]

    print(
        "Indicadores antes da carga:",
        total_antes
    )

    print("\nCalculando indicadores...")


    # ======================================================
    # INDICADORES DE MERCADO
    # ======================================================

    cursor.execute(
        """
        WITH base AS (

            SELECT
                data,
                ticker,
                preco_fechamento,
                volume_financeiro,
                quantidade_negocios,

                LAG(preco_fechamento) OVER (
                    PARTITION BY ticker
                    ORDER BY data
                ) AS fechamento_anterior,

                AVG(volume_financeiro) OVER (
                    PARTITION BY ticker
                    ORDER BY data
                    ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
                ) AS volume_medio_20,

                AVG(quantidade_negocios) OVER (
                    PARTITION BY ticker
                    ORDER BY data
                    ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
                ) AS negocios_medio_20

            FROM cotacoes
        ),

        variacoes AS (

            SELECT
                data,
                ticker,
                preco_fechamento,
                fechamento_anterior,
                volume_financeiro,
                quantidade_negocios,
                volume_medio_20,
                negocios_medio_20,

                CASE
                    WHEN fechamento_anterior IS NULL
                        THEN NULL

                    WHEN fechamento_anterior = 0
                        THEN NULL

                    ELSE
                        (
                            (
                                preco_fechamento
                                / fechamento_anterior
                            ) - 1
                        ) * 100
                END AS variacao_percentual

            FROM base
        ),

        estatisticas AS (

            SELECT
                data,
                ticker,
                preco_fechamento,
                fechamento_anterior,
                variacao_percentual,
                volume_financeiro,
                quantidade_negocios,
                volume_medio_20,
                negocios_medio_20,

                AVG(variacao_percentual) OVER (
                    PARTITION BY ticker
                    ORDER BY data
                    ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
                ) AS variacao_media_20,

                STDDEV_SAMP(variacao_percentual) OVER (
                    PARTITION BY ticker
                    ORDER BY data
                    ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
                ) AS desvio_variacao_20

            FROM variacoes
        ),

        calculados AS (

            SELECT
                data,
                ticker,
                preco_fechamento,
                fechamento_anterior,
                variacao_percentual,
                volume_financeiro,
                quantidade_negocios,
                volume_medio_20,

                CASE
                    WHEN volume_medio_20 IS NULL
                        THEN NULL

                    WHEN volume_medio_20 = 0
                        THEN NULL

                    ELSE
                        volume_financeiro
                        / volume_medio_20
                END AS volume_relativo_20,

                negocios_medio_20,

                CASE
                    WHEN negocios_medio_20 IS NULL
                        THEN NULL

                    WHEN negocios_medio_20 = 0
                        THEN NULL

                    ELSE
                        quantidade_negocios::NUMERIC
                        / negocios_medio_20
                END AS negocios_relativo_20,

                CASE
                    WHEN volume_medio_20 IS NULL
                         OR negocios_medio_20 IS NULL
                        THEN NULL

                    ELSE
                        ROUND(
                            (
                                (
                                    0.70
                                    *
                                    LEAST(
                                        1.0,
                                        LN(
                                            1.0
                                            + volume_medio_20::DOUBLE PRECISION
                                        )
                                        /
                                        LN(1000001.0)
                                    )
                                )

                                +

                                (
                                    0.30
                                    *
                                    LEAST(
                                        1.0,
                                        LN(
                                            1.0
                                            + negocios_medio_20::DOUBLE PRECISION
                                        )
                                        /
                                        LN(1001.0)
                                    )
                                )
                            )::NUMERIC * 100,
                            4
                        )
                END AS liquidez_score,

                variacao_media_20,
                desvio_variacao_20,

                CASE
                    WHEN desvio_variacao_20 IS NULL
                        THEN NULL

                    ELSE
                        desvio_variacao_20
                        * SQRT(252)
                END AS volatilidade_20,

                CASE
                    WHEN desvio_variacao_20 IS NULL
                        THEN NULL

                    WHEN desvio_variacao_20 = 0
                        THEN NULL

                    WHEN variacao_percentual IS NULL
                        THEN NULL

                    ELSE
                        (
                            variacao_percentual
                            - variacao_media_20
                        )
                        / desvio_variacao_20
                END AS zscore_variacao_20

            FROM estatisticas
        )

        INSERT INTO indicadores_fii (
            data,
            ticker,
            preco_fechamento,
            fechamento_anterior,
            variacao_percentual,
            volume_financeiro,
            quantidade_negocios,
            volume_medio_20,
            volume_relativo_20,
            negocios_medio_20,
            negocios_relativo_20,
            liquidez_score,
            variacao_media_20,
            desvio_variacao_20,
            volatilidade_20,
            zscore_variacao_20,
            data_atualizacao
        )

        SELECT
            data,
            ticker,
            preco_fechamento,
            fechamento_anterior,
            variacao_percentual,
            volume_financeiro,
            quantidade_negocios,
            volume_medio_20,
            volume_relativo_20,
            negocios_medio_20,
            negocios_relativo_20,
            liquidez_score,
            variacao_media_20,
            desvio_variacao_20,
            volatilidade_20,
            zscore_variacao_20,
            CURRENT_TIMESTAMP

        FROM calculados

        ON CONFLICT (data, ticker)

        DO UPDATE SET

            preco_fechamento =
                EXCLUDED.preco_fechamento,

            fechamento_anterior =
                EXCLUDED.fechamento_anterior,

            variacao_percentual =
                EXCLUDED.variacao_percentual,

            volume_financeiro =
                EXCLUDED.volume_financeiro,

            quantidade_negocios =
                EXCLUDED.quantidade_negocios,

            volume_medio_20 =
                EXCLUDED.volume_medio_20,

            volume_relativo_20 =
                EXCLUDED.volume_relativo_20,

            negocios_medio_20 =
                EXCLUDED.negocios_medio_20,

            negocios_relativo_20 =
                EXCLUDED.negocios_relativo_20,

            liquidez_score =
                EXCLUDED.liquidez_score,

            variacao_media_20 =
                EXCLUDED.variacao_media_20,

            desvio_variacao_20 =
                EXCLUDED.desvio_variacao_20,

            volatilidade_20 =
                EXCLUDED.volatilidade_20,

            zscore_variacao_20 =
                EXCLUDED.zscore_variacao_20,

            data_atualizacao =
                CURRENT_TIMESTAMP;
        """
    )

    processados = cursor.rowcount


    # ======================================================
    # LIMPAR FUNDAMENTOS ANTERIORES
    # ======================================================

    print(
        "\nPreparando associacao "
        "com fundamentos CVM..."
    )

    cursor.execute(
        """
        UPDATE indicadores_fii

        SET
            valor_patrimonial_cota = NULL,
            p_vp = NULL,
            dividend_yield_mes = NULL,
            total_numero_cotistas = NULL,
            data_fundamento = NULL;
        """
    )


    # ======================================================
    # ASSOCIAR FUNDAMENTOS HISTORICOS
    # ======================================================

    print(
        "Associando fundamentos CVM "
        "aos indicadores..."
    )

    cursor.execute(
        """
        WITH fundamentos_associados AS (

            SELECT
                i.data,
                i.ticker,

                fd.data_referencia,
                fd.valor_patrimonial_cota,
                fd.dividend_yield_mes,
                fd.total_numero_cotistas

            FROM indicadores_fii i

            JOIN fiis f
                ON f.ticker = i.ticker
                AND f.presente_cvm = TRUE
                AND f.ticker IS NOT NULL

            JOIN LATERAL (

                SELECT
                    x.data_referencia,
                    x.valor_patrimonial_cota,
                    x.dividend_yield_mes,
                    x.total_numero_cotistas

                FROM fundamentos_fii x

                WHERE
                    x.cnpj_fundo_classe =
                        f.cnpj_classe

                    AND x.data_referencia <= i.data

                ORDER BY
                    x.data_referencia DESC

                LIMIT 1

            ) fd ON TRUE
        )

        UPDATE indicadores_fii i

        SET
            valor_patrimonial_cota =
                fa.valor_patrimonial_cota,

            p_vp =
                CASE
                    WHEN fa.valor_patrimonial_cota IS NULL
                        THEN NULL

                    WHEN fa.valor_patrimonial_cota = 0
                        THEN NULL

                    WHEN i.preco_fechamento IS NULL
                        THEN NULL

                    ELSE
                        i.preco_fechamento
                        / fa.valor_patrimonial_cota
                END,

            dividend_yield_mes =
                fa.dividend_yield_mes,

            total_numero_cotistas =
                fa.total_numero_cotistas,

            data_fundamento =
                fa.data_referencia,

            data_atualizacao =
                CURRENT_TIMESTAMP

        FROM fundamentos_associados fa

        WHERE
            i.data = fa.data
            AND i.ticker = fa.ticker;
        """
    )

    fundamentos_atualizados = cursor.rowcount


    # ======================================================
    # SCORE DE ATENCAO
    #
    # PESOS:
    #
    # 50% = movimento anormal (|z-score|)
    # 25% = volume relativo
    # 15% = negocios relativos
    # 10% = liquidez
    #
    # O score mede anormalidade / atencao.
    # Nao e recomendacao de compra ou venda.
    # ======================================================

    print(
        "\nCalculando Score de Atencao..."
    )

    cursor.execute(
        """
        WITH componentes AS (

            SELECT
                data,
                ticker,
                zscore_variacao_20,
                volume_relativo_20,
                negocios_relativo_20,
                liquidez_score,

                CASE
                    WHEN zscore_variacao_20 IS NULL
                        THEN NULL

                    ELSE
                        LEAST(
                            1.0,
                            ABS(
                                zscore_variacao_20::DOUBLE PRECISION
                            ) / 4.0
                        )
                END AS componente_movimento,

                CASE
                    WHEN volume_relativo_20 IS NULL
                        THEN 0.0

                    WHEN volume_relativo_20 <= 0
                        THEN 0.0

                    ELSE
                        LEAST(
                            1.0,
                            LN(
                                1.0
                                + volume_relativo_20::DOUBLE PRECISION
                            )
                            /
                            LN(11.0)
                        )
                END AS componente_volume,

                CASE
                    WHEN negocios_relativo_20 IS NULL
                        THEN 0.0

                    WHEN negocios_relativo_20 <= 0
                        THEN 0.0

                    ELSE
                        LEAST(
                            1.0,
                            LN(
                                1.0
                                + negocios_relativo_20::DOUBLE PRECISION
                            )
                            /
                            LN(11.0)
                        )
                END AS componente_negocios,

                CASE
                    WHEN liquidez_score IS NULL
                        THEN 0.0

                    ELSE
                        LEAST(
                            1.0,
                            GREATEST(
                                0.0,
                                liquidez_score::DOUBLE PRECISION
                                / 100.0
                            )
                        )
                END AS componente_liquidez

            FROM indicadores_fii
        ),

        scores AS (

            SELECT
                data,
                ticker,

                CASE
                    WHEN componente_movimento IS NULL
                        THEN NULL

                    ELSE
                        ROUND(
                            (
                                (
                                    0.50
                                    * componente_movimento
                                )

                                +

                                (
                                    0.25
                                    * componente_volume
                                )

                                +

                                (
                                    0.15
                                    * componente_negocios
                                )

                                +

                                (
                                    0.10
                                    * componente_liquidez
                                )
                            )::NUMERIC
                            * 100,
                            4
                        )
                END AS score_atencao

            FROM componentes
        ),

        classificados AS (

            SELECT
                data,
                ticker,
                score_atencao,

                CASE
                    WHEN score_atencao IS NULL
                        THEN NULL

                    WHEN score_atencao >= 80
                        THEN 'MUITO ALTO'

                    WHEN score_atencao >= 60
                        THEN 'ALTO'

                    WHEN score_atencao >= 40
                        THEN 'MODERADO'

                    ELSE
                        'BAIXO'
                END AS nivel_atencao

            FROM scores
        )

        UPDATE indicadores_fii i

        SET
            score_atencao =
                c.score_atencao,

            nivel_atencao =
                c.nivel_atencao,

            data_atualizacao =
                CURRENT_TIMESTAMP

        FROM classificados c

        WHERE
            i.data = c.data
            AND i.ticker = c.ticker;
        """
    )

    scores_atualizados = cursor.rowcount


    # ======================================================
    # CONTAGENS
    # ======================================================

    cursor.execute(
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT ticker),
            MIN(data),
            MAX(data),
            COUNT(variacao_percentual),
            COUNT(volume_relativo_20),
            COUNT(volatilidade_20),
            COUNT(zscore_variacao_20),
            COUNT(liquidez_score),
            COUNT(valor_patrimonial_cota),
            COUNT(p_vp),
            COUNT(dividend_yield_mes),
            COUNT(total_numero_cotistas),
            COUNT(data_fundamento),
            COUNT(score_atencao)

        FROM indicadores_fii;
        """
    )

    resultado = cursor.fetchone()

    total = resultado[0]
    tickers = resultado[1]
    primeira_data = resultado[2]
    ultima_data = resultado[3]

    com_variacao = resultado[4]
    com_volume_relativo = resultado[5]
    com_volatilidade = resultado[6]
    com_zscore = resultado[7]
    com_liquidez_score = resultado[8]

    com_vp = resultado[9]
    com_p_vp = resultado[10]
    com_dy = resultado[11]
    com_cotistas = resultado[12]
    com_data_fundamento = resultado[13]
    com_score_atencao = resultado[14]


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM cotacoes;
        """
    )

    total_cotacoes = cursor.fetchone()[0]


    # ======================================================
    # RESULTADO
    # ======================================================

    print("\n========================================")
    print("RESULTADO")
    print("========================================")

    print(
        "Linhas processadas:",
        processados
    )

    print(
        "Indicadores no banco:",
        total
    )

    print(
        "Cotacoes no banco:",
        total_cotacoes
    )

    print(
        "Tickers diferentes:",
        tickers
    )

    print(
        "Primeira data:",
        primeira_data
    )

    print(
        "Ultima data:",
        ultima_data
    )

    print(
        "Registros com variacao:",
        com_variacao
    )

    print(
        "Registros com volume relativo:",
        com_volume_relativo
    )

    print(
        "Registros com volatilidade:",
        com_volatilidade
    )

    print(
        "Registros com z-score:",
        com_zscore
    )

    print(
        "Registros com liquidez score:",
        com_liquidez_score
    )

    print(
        "Registros associados a fundamento:",
        fundamentos_atualizados
    )

    print(
        "Registros com VP/cota:",
        com_vp
    )

    print(
        "Registros com P/VP:",
        com_p_vp
    )

    print(
        "Registros com Dividend Yield:",
        com_dy
    )

    print(
        "Registros com numero de cotistas:",
        com_cotistas
    )

    print(
        "Registros com data de fundamento:",
        com_data_fundamento
    )

    print(
        "Registros atualizados pelo score:",
        scores_atualizados
    )

    print(
        "Registros com Score de Atencao:",
        com_score_atencao
    )


    # ======================================================
    # PROTECAO
    # ======================================================

    if total != total_cotacoes:

        raise RuntimeError(
            "A quantidade de indicadores nao corresponde "
            "a quantidade de cotacoes."
        )


    # ======================================================
    # VALIDAR LOOK-AHEAD
    # ======================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM indicadores_fii

        WHERE
            data_fundamento IS NOT NULL

            AND data_fundamento > data;
        """
    )

    erros_lookahead = cursor.fetchone()[0]

    print(
        "Fundamentos com data futura:",
        erros_lookahead
    )

    if erros_lookahead > 0:

        raise RuntimeError(
            "Foram encontrados fundamentos futuros "
            "associados a cotacoes."
        )


    # ======================================================
    # VALIDAR SCORE
    # ======================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM indicadores_fii

        WHERE
            score_atencao < 0
            OR score_atencao > 100;
        """
    )

    scores_invalidos = cursor.fetchone()[0]

    print(
        "Scores fora do intervalo 0-100:",
        scores_invalidos
    )

    if scores_invalidos > 0:

        raise RuntimeError(
            "Existem Scores de Atencao "
            "fora do intervalo 0-100."
        )


    # ======================================================
    # DISTRIBUICAO DOS NIVEIS
    # ======================================================

    cursor.execute(
        """
        SELECT
            nivel_atencao,
            COUNT(*)

        FROM indicadores_fii

        WHERE score_atencao IS NOT NULL

        GROUP BY nivel_atencao

        ORDER BY
            CASE nivel_atencao
                WHEN 'MUITO ALTO' THEN 1
                WHEN 'ALTO' THEN 2
                WHEN 'MODERADO' THEN 3
                WHEN 'BAIXO' THEN 4
                ELSE 5
            END;
        """
    )

    niveis = cursor.fetchall()


    print("\n========================================")
    print("DISTRIBUICAO DOS NIVEIS")
    print("========================================")

    for linha in niveis:
        print(linha)


    # ======================================================
    # TOP SCORE - ULTIMO PREGAO
    # ======================================================

    cursor.execute(
        """
        SELECT
            ticker,
            data,

            ROUND(
                score_atencao,
                2
            ),

            nivel_atencao,

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

            ROUND(
                dividend_yield_mes * 100,
                4
            ),

            total_numero_cotistas

        FROM indicadores_fii

        WHERE
            data = (
                SELECT MAX(data)
                FROM indicadores_fii
            )

            AND score_atencao IS NOT NULL

        ORDER BY
            score_atencao DESC

        LIMIT 20;
        """
    )

    top_score = cursor.fetchall()


    print("\n========================================")
    print("TOP 20 - SCORE DE ATENCAO")
    print("========================================")

    print(
        "ticker | data | score | nivel | "
        "variacao% | z-score | volume rel. | "
        "negocios rel. | liquidez | P/VP | "
        "DY% | cotistas"
    )

    for linha in top_score:
        print(linha)


    # ======================================================
    # DISTRIBUICAO DO SCORE - ULTIMO PREGAO
    # ======================================================

    cursor.execute(
        """
        SELECT
            COUNT(score_atencao),

            ROUND(
                PERCENTILE_CONT(0.25)
                WITHIN GROUP (
                    ORDER BY score_atencao
                )::NUMERIC,
                2
            ),

            ROUND(
                PERCENTILE_CONT(0.50)
                WITHIN GROUP (
                    ORDER BY score_atencao
                )::NUMERIC,
                2
            ),

            ROUND(
                PERCENTILE_CONT(0.75)
                WITHIN GROUP (
                    ORDER BY score_atencao
                )::NUMERIC,
                2
            ),

            ROUND(
                MAX(score_atencao),
                2
            )

        FROM indicadores_fii

        WHERE
            data = (
                SELECT MAX(data)
                FROM indicadores_fii
            );
        """
    )

    distribuicao_score = cursor.fetchone()


    print("\n========================================")
    print("DISTRIBUICAO SCORE - ULTIMO PREGAO")
    print("========================================")

    print(
        "FIIs com score:",
        distribuicao_score[0]
    )

    print(
        "Percentil 25%:",
        distribuicao_score[1]
    )

    print(
        "Mediana:",
        distribuicao_score[2]
    )

    print(
        "Percentil 75%:",
        distribuicao_score[3]
    )

    print(
        "Maior score:",
        distribuicao_score[4]
    )


    # ======================================================
    # DISTRIBUICAO P/VP
    # ======================================================

    cursor.execute(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE p_vp > 0
            ),

            ROUND(
                PERCENTILE_CONT(0.25)
                WITHIN GROUP (
                    ORDER BY p_vp
                )
                FILTER (
                    WHERE p_vp > 0
                )::NUMERIC,
                4
            ),

            ROUND(
                PERCENTILE_CONT(0.50)
                WITHIN GROUP (
                    ORDER BY p_vp
                )
                FILTER (
                    WHERE p_vp > 0
                )::NUMERIC,
                4
            ),

            ROUND(
                PERCENTILE_CONT(0.75)
                WITHIN GROUP (
                    ORDER BY p_vp
                )
                FILTER (
                    WHERE p_vp > 0
                )::NUMERIC,
                4
            )

        FROM indicadores_fii

        WHERE data = (
            SELECT MAX(data)
            FROM indicadores_fii
        );
        """
    )

    distribuicao = cursor.fetchone()


    print("\n========================================")
    print("DISTRIBUICAO P/VP - ULTIMO PREGAO")
    print("========================================")

    print(
        "FIIs com P/VP positivo:",
        distribuicao[0]
    )

    print(
        "Percentil 25%:",
        distribuicao[1]
    )

    print(
        "Mediana:",
        distribuicao[2]
    )

    print(
        "Percentil 75%:",
        distribuicao[3]
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
        "\nERRO DURANTE A CARGA."
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