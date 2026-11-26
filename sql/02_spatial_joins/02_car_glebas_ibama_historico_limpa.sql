-- =============================================================================
-- Objetivo : Identificar os imóveis completos do SICAR que contêm glebas
--            financiadas com Proagro e cruzá-los com os embargos do IBAMA.
-- Entradas : car_historico, glebas, opbasica_estado, ibama_historico
-- Saídas   : car_glebas, car_glebas_ibama_historico_limpa
-- =============================================================================

-- Etapa 1: Sobreposição espacial entre imóveis do SICAR e glebas com Proagro
DROP TABLE IF EXISTS car_glebas;

CREATE TABLE car_glebas AS
SELECT DISTINCT
    g.ref_bacen,
    g.nu_ordem,
    g.ref_nu,
    op.dt_emissao::date    AS dt_emissao,
    op.dt_vencimento::date AS dt_vencimento,
    op.vl_aliq_proagro,
    c.cod_imovel,
    c.geom
FROM glebas g
JOIN opbasica_estado op
    ON g.ref_bacen = op.ref_bacen
   AND g.nu_ordem  = op.nu_ordem
JOIN car_historico c
    ON ST_Intersects(g.geom, c.geom)
WHERE op.vl_aliq_proagro IS NOT NULL
  AND op.vl_aliq_proagro > 0;

CREATE INDEX idx_car_glebas_geom ON car_glebas USING GIST (geom);

-- Etapa 2: Sobreposição dos imóveis inteiros resultantes com o histórico do IBAMA
DROP TABLE IF EXISTS car_glebas_ibama_historico_limpa;

CREATE TABLE car_glebas_ibama_historico_limpa AS
SELECT
    cg.ref_bacen,
    cg.nu_ordem,
    cg.ref_nu,
    cg.dt_emissao,
    cg.dt_vencimento,
    cg.vl_aliq_proagro,
    cg.cod_imovel,
    ib.num_tad,
    ib.dat_embargo::date AS dat_embargo,
    cg.geom              AS geom_imovel,
    ib.geom              AS geom_embargo
FROM car_glebas cg
JOIN ibama_historico ib
    ON ST_Intersects(cg.geom, ib.geom);

CREATE INDEX idx_car_glebas_ibama_ref_bacen ON car_glebas_ibama_historico_limpa (ref_bacen);
CREATE INDEX idx_car_glebas_ibama_cod_imov  ON car_glebas_ibama_historico_limpa (cod_imovel);
CREATE INDEX idx_car_glebas_ibama_num_tad   ON car_glebas_ibama_historico_limpa (num_tad);