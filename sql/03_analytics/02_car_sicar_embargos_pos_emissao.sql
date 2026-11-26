-- =============================================================================
-- Objetivo : Contabilizar operações com Proagro, imóveis e embargos únicos
--            considerando toda a base de imóveis do SICAR sobrepostos às glebas.
-- Entrada  : car_glebas_ibama_historico_limpa
-- Regra    : Emissões entre jul/2017 e jun/2026 com embargo posterior à emissão.
-- =============================================================================

WITH params AS (
    SELECT
        DATE '2017-07-01' AS dt_inicio,
        DATE '2026-06-30' AS dt_fim
)
SELECT
    COUNT(DISTINCT c.ref_bacen)  AS total_operacoes_unicas,
    COUNT(DISTINCT c.cod_imovel) AS total_imoveis_unicos,
    COUNT(DISTINCT c.num_tad)    AS total_embargos_unicos
FROM car_glebas_ibama_historico_limpa c
CROSS JOIN params p
WHERE c.dt_emissao::date BETWEEN p.dt_inicio AND p.dt_fim
  AND c.dat_embargo::date > c.dt_emissao::date;