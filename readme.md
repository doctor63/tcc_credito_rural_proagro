---
Repositório com o pipeline SQL (PostgreSQL/PostGIS) e script em Python para Google Earth Engine desenvolvidos para o Trabalho de Conclusão de Curso em Agronomia pela Faculdade de Agronomia e Medicina Veterinária (FAV) da Universidade de Brasília (UnB).

---

## 1. Objetivo

Avaliar a sobreposição espaço-temporal entre operações de crédito rural contratadas com Proagro (julho de 2017 a junho de 2026), polígonos de áreas embargadas pelo IBAMA e a supressão vegetal observada por satélite.
---

## 2. Fontes de Dados

Devido ao volume de dados (dezenas de gigabytes em tabelas relacionais, geometrias e rasters), os arquivos brutos não estão armazenados neste repositório e devem ser obtidos diretamente nas fontes oficiais:

* **SICOR / Banco Central do Brasil:** Tabelas `sicor_operacao_basica_estado`, `sicor_glebas_wkt` e `sicor_propriedades` (jul/2017 a jun/2026) — [Dados Abertos do Crédito Rural](https://www.bcb.gov.br/estabilidadefinanceira/tabelas-credito-rural-proagro)
* **SICAR** Base vetorial de perímetros de imóveis rurais (`car_historico`, jul/2024 a jul/2025) (https://consulta.car.gov.br/geoservices)
* **IBAMA:** Base histórica de polígonos de áreas embargadas (`ibama_historico`) (https://dadosabertos.IBAMA.gov.br/dataset/fiscalizacao-termo-de-embargo)
* **Google Earth Engine (GEE):** Séries históricas de imagens de satélite
---

## 3. Estrutura do Repositório

```
tcc/
├── README.md
├── .gitignore
├── requirements.txt
├── sql/
│   ├── 00_utils/                                        # Funções auxiliares reutilizáveis
│   │   └── 01_fn_normalizar_car.sql
│   ├── 01_staging/                                      # Chaves compostas, índices e filtros base
│   │   ├── 01_chaves_e_indices.sql
│   │   └── 02_opbasica_estado_proagro.sql
│   ├── 02_spatial_joins/                                # Cruzamentos espaciais (PostGIS)
│   │   ├── 01_glebas_ibama_historico.sql
│   │   ├── 02_car_glebas_ibama_historico_limpa.sql
│   │   └── 03_proagro_sicor_propriedades_ibama_historico.sql
│   ├── 03_analytics/                                    # Consultas finais de extração de resultados
│   │   ├── 01_glebas_embargadas_vigencia.sql
│   │   ├── 02_car_sicar_embargos_pos_emissao.sql
│   │   ├── 03_validacao_car_proagro.sql
│   │   └── 04_imoveis_declarados_vigencia.sql
│   └── run_all.sql                                      # Orquestrador sequencial via psql
└── python/
    └── 01_processamento_gee.py                          # Exportação e processamento de imagens no GEE
```

---
Pré-requisitos e Execução
PostgreSQL com extensão PostGIS habilitada
Python 3.10+ (dependências listadas em requirements.txt)
Conta autenticada no Google Earth Engine

---

###Definir o projeto GEE
export GEE_PROJECT_ID="seu-projeto-gee"

# Rodar um lote específico
python python/01_processamento_gee.py \
  --csv-base data/tads.csv \
  --lote 14 \
  --tamanho-lote 10

# Consultar apenas a fila de tarefas no GEE
python python/01_processamento_gee.py --apenas-status