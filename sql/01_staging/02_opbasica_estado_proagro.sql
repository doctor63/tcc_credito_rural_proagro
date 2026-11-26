-- =============================================================================
-- Objetivo : Filtrar operações de crédito rural com Proagro contratado
--            (jul/2017 a jun/2026) e vincular o CAR declarado no SICOR.
-- Entradas : opbasica_estado, sicor_propriedades
-- Saída    : opbasica_estado_proagro
-- =============================================================================

DROP TABLE IF EXISTS opbasica_estado_proagro;

CREATE TABLE opbasica_estado_proagro AS
WITH params AS (
    SELECT
        DATE '2017-07-01' AS dt_inicio,
        DATE '2026-06-30' AS dt_fim
)
SELECT
    op.ref_bacen,
    op.nu_ordem,
    op.ref_nu,
    op.dt_emissao::date    AS dt_emissao,
    op.dt_vencimento::date AS dt_vencimento,
    op.cd_tipo_seguro,
    op.vl_aliq_proagro,
    op.vl_parc_credito,
    op.vl_area_informada,
    p.cd_car               AS propriedades_car,
    fn_normalizar_car(p.cd_car::text) AS car_normalizado
FROM opbasica_estado op
CROSS JOIN params par
LEFT JOIN sicor_propriedades p
    ON op.ref_bacen = p.ref_bacen
   AND op.nu_ordem  = p.nu_ordem
WHERE op.dt_emissao::date BETWEEN par.dt_inicio AND par.dt_fim
  AND op.vl_aliq_proagro IS NOT NULL
  AND op.vl_aliq_proagro > 0;

CREATE INDEX idx_op_proagro_ref_bacen ON opbasica_estado_proagro (ref_bacen);
CREATE INDEX idx_op_proagro_car_norm  ON opbasica_estado_proagro (car_normalizado);