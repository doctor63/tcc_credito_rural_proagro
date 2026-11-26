-- =============================================================================
-- Objetivo : Contabilizar operações com Proagro, imóveis declarados e TADs
--            lavrados durante a vigência da operação.
-- Entradas : opbasica_estado_proagro, proagro_sicor_propriedades_ibama_historico
-- Regra    : dat_embargo > dt_emissao AND dat_embargo < dt_vencimento
-- =============================================================================

SELECT
    COUNT(DISTINCT op.ref_bacen)  AS operacoes_embargadas_vigencia,
    COUNT(DISTINCT ib.cod_imovel) AS imoveis_embargados_vigencia,
    COUNT(DISTINCT ib.num_tad)    AS tads_gerados_vigencia
FROM opbasica_estado_proagro op
JOIN proagro_sicor_propriedades_ibama_historico ib
    ON ib.cod_imovel = op.car_normalizado
WHERE op.car_normalizado IS NOT NULL
  AND ib.dat_embargo::date > op.dt_emissao::date
  AND ib.dat_embargo::date < op.dt_vencimento::date;