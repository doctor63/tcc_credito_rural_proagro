-- =============================================================================
-- Objetivo : Contabilizar glebas, operações totais, operações com Proagro e
--            TADs únicos embargados estritamente durante a vigência contratual.
-- Entradas : glebas_ibama_historico, opbasica_estado
-- Regra    : dat_embargo > dt_emissao AND dat_embargo < dt_vencimento
-- =============================================================================

SELECT
    -- 1. Glebas onde o embargo ocorreu durante o ciclo do contrato
    COUNT(DISTINCT g.ref_nu) FILTER (
        WHERE g.dat_embargo::date > op.dt_emissao::date
          AND g.dat_embargo::date < op.dt_vencimento::date
    ) AS glebas_embargadas_na_vigencia,

    -- 2. Operações totais onde o embargo ocorreu durante o ciclo do contrato
    COUNT(DISTINCT g.ref_bacen) FILTER (
        WHERE g.dat_embargo::date > op.dt_emissao::date
          AND g.dat_embargo::date < op.dt_vencimento::date
    ) AS operacoes_embargadas_na_vigencia,

    -- 3. Operações com Proagro onde o embargo ocorreu durante o ciclo do contrato
    COUNT(DISTINCT g.ref_bacen) FILTER (
        WHERE g.vl_aliq_proagro IS NOT NULL
          AND g.dat_embargo::date > op.dt_emissao::date
          AND g.dat_embargo::date < op.dt_vencimento::date
    ) AS operacoes_proagro_embargadas_na_vigencia,

    -- 4. Termos de Embargo (TAD) únicos vinculados a operações com Proagro na vigência
    COUNT(DISTINCT g.num_tad) FILTER (
        WHERE g.vl_aliq_proagro IS NOT NULL
          AND g.dat_embargo::date > op.dt_emissao::date
          AND g.dat_embargo::date < op.dt_vencimento::date
    ) AS num_tad_unicos
FROM glebas_ibama_historico g
JOIN opbasica_estado op
    ON g.ref_bacen = op.ref_bacen;