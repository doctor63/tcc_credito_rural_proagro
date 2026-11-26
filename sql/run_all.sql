-- =============================================================================
-- Orquestrador do pipeline SQL completo
-- Uso: psql -U <usuario> -d <banco> -f run_all.sql
-- =============================================================================

\set ON_ERROR_STOP on

\ir 00_utils/01_fn_normalizar_car.sql

\ir 01_staging/01_chaves_e_indices.sql
\ir 01_staging/02_opbasica_estado_proagro.sql

\ir 02_spatial_joins/01_glebas_ibama_historico.sql
\ir 02_spatial_joins/02_car_glebas_ibama_historico_limpa.sql
\ir 02_spatial_joins/03_proagro_sicor_propriedades_ibama_historico.sql

\ir 03_analytics/01_glebas_embargadas_vigencia.sql
\ir 03_analytics/02_car_sicar_embargos_pos_emissao.sql
\ir 03_analytics/03_validacao_car_proagro.sql
\ir 03_analytics/04_imoveis_declarados_vigencia.sql