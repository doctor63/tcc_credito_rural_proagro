-- =============================================================================
-- Objetivo : Realizar interseção espacial entre as glebas financiadas
--            e o histórico de áreas embargadas pelo IBAMA.
-- Entradas : glebas, opbasica_estado, ibama_historico
-- Saída    : glebas_ibama_historico
-- =============================================================================

DROP TABLE IF EXISTS glebas_ibama_historico;

CREATE TABLE glebas_ibama_historico AS
SELECT
    g.ref_bacen,
    g.nu_ordem,
    g.nu_indice,
    g.ref_nu,
    op.vl_aliq_proagro,
    ib.num_tad,
    ib.dat_embargo::date AS dat_embargo,
    g.geom               AS geom_gleba,
    ib.geom              AS geom_embargo
FROM glebas g
JOIN opbasica_estado op
    ON g.ref_bacen = op.ref_bacen
   AND g.nu_ordem  = op.nu_ordem
JOIN ibama_historico ib
    ON ST_Intersects(g.geom, ib.geom);

CREATE INDEX idx_glebas_ibama_ref_bacen ON glebas_ibama_historico (ref_bacen);
CREATE INDEX idx_glebas_ibama_num_tad   ON glebas_ibama_historico (num_tad);