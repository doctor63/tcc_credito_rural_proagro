-- =============================================================================
-- Objetivo : Validação dos CARs declarados no Proagro:
--            (1) CARs válidos únicos -> (2) com polígono no SICAR -> (3) com embargo.
-- Entradas : opbasica_estado_proagro, car_historico,
--            proagro_sicor_propriedades_ibama_historico
-- =============================================================================

WITH car_proagro AS (
    SELECT COUNT(DISTINCT car_normalizado) AS qtd_car_unicos_proagro
    FROM opbasica_estado_proagro
    WHERE car_normalizado IS NOT NULL
),
car_geometria AS (
    SELECT COUNT(DISTINCT p.car_normalizado) AS qtd_car_com_geometria
    FROM opbasica_estado_proagro p
    WHERE p.car_normalizado IS NOT NULL
      AND EXISTS (
          SELECT 1
          FROM car_historico c
          WHERE c.cod_imovel = p.car_normalizado
      )
),
car_embargo AS (
    SELECT COUNT(DISTINCT cod_imovel) AS qtd_car_com_embargo
    FROM proagro_sicor_propriedades_ibama_historico
)
SELECT
    a.qtd_car_unicos_proagro,
    b.qtd_car_com_geometria,
    c.qtd_car_com_embargo
FROM car_proagro a
CROSS JOIN car_geometria b
CROSS JOIN car_embargo c;