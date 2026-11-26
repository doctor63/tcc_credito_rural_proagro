-- =============================================================================
-- Objetivo : Padronizar e validar códigos de recibo do CAR declarados no SICOR
--            (remove -1/NULL e aplica a máscara UF-IBGE-HASH).
-- Entrada  : codigo_raw (TEXT)
-- Saída    : Código CAR formatado (TEXT) ou NULL quando inválido.
-- =============================================================================

CREATE OR REPLACE FUNCTION fn_normalizar_car(codigo_raw TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT CASE
        WHEN codigo_raw IS NULL
          OR TRIM(codigo_raw) IN ('', '-1', '-1.0', 'NULL')
        THEN NULL
        WHEN POSITION('-' IN TRIM(codigo_raw)) > 0
        THEN UPPER(TRIM(codigo_raw))
        ELSE
            UPPER(
                SUBSTRING(TRIM(codigo_raw), 1, 2) || '-' ||
                SUBSTRING(TRIM(codigo_raw), 3, 7) || '-' ||
                SUBSTRING(TRIM(codigo_raw), 10)
            )
    END;
$$;