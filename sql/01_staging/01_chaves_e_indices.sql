-- =============================================================================
-- Objetivo : Criar a chave composta ref_nu (ref_bacen + nu_ordem) e índices
--            nas tabelas base
-- Entradas : opbasica_estado, glebas, sicor_propriedades, car_historico,
--            ibama_historico
-- =============================================================================

-- 1. Chave composta
ALTER TABLE opbasica_estado
ADD COLUMN IF NOT EXISTS ref_nu TEXT
GENERATED ALWAYS AS (ref_bacen::text || '_' || nu_ordem::text) STORED;

ALTER TABLE glebas
ADD COLUMN IF NOT EXISTS ref_nu TEXT
GENERATED ALWAYS AS (ref_bacen::text || '_' || nu_ordem::text) STORED;

-- 2. Índices alfanuméricos (B-Tree)
CREATE INDEX IF NOT EXISTS idx_opbasica_ref_bacen ON opbasica_estado (ref_bacen);
CREATE INDEX IF NOT EXISTS idx_opbasica_ref_nu    ON opbasica_estado (ref_nu);
CREATE INDEX IF NOT EXISTS idx_glebas_ref_bacen   ON glebas (ref_bacen);
CREATE INDEX IF NOT EXISTS idx_glebas_ref_nu      ON glebas (ref_nu);
CREATE INDEX IF NOT EXISTS idx_prop_ref_bacen     ON sicor_propriedades (ref_bacen);
CREATE INDEX IF NOT EXISTS idx_car_cod_imovel     ON car_historico (cod_imovel);

-- 3. Índices espaciais (GIST) - ajustar "geom" caso a coluna seja "wkb_geometry"
CREATE INDEX IF NOT EXISTS idx_glebas_geom        ON glebas USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_car_geom           ON car_historico USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_ibama_geom         ON ibama_historico USING GIST (geom);