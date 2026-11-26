-- =============================================================================
-- Objetivo : Cruzar espacialmente com o IBAMA apenas os polígonos do SICAR
--            formalmente declarados nas operações de Proagro (sicor_propriedades).
-- Entradas : opbasica_estado_proagro, car_historico, ibama_historico
-- Saída    : proagro_sicor_propriedades_ibama_historico
-- =============================================================================

DROP TABLE IF EXISTS proagro_sicor_propriedades_ibama_historico;

CREATE TABLE proagro_sicor_propriedades_ibama_historico AS
WITH cars_declarados_proagro AS (
    SELECT DISTINCT car_normalizado
    FROM opbasica_estado_proagro
    WHERE car_normalizado IS NOT NULL
),
imoveis_proagro_geom AS (
    SELECT
        c.cod_imovel,
        c.geom
    FROM car_historico c
    JOIN cars_declarados_proagro p
        ON c.cod_imovel = p.car_normalizado
)
SELECT
    im.cod_imovel,
    ib.num_tad,
    ib.dat_embargo::date AS dat_embargo,
    im.geom              AS geom_imovel,
    ib.geom              AS geom_embargo
FROM imoveis_proagro_geom im
JOIN ibama_historico ib
    ON ST_Intersects(im.geom, ib.geom);

CREATE INDEX idx_proagro_prop_ibama_cod_imov ON proagro_sicor_propriedades_ibama_historico (cod_imovel);
CREATE INDEX idx_proagro_prop_ibama_num_tad  ON proagro_sicor_propriedades_ibama_historico (num_tad);