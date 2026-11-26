"""
Exportação de séries históricas de imagens de satélite via Google Earth Engine (GEE).

Gera, para cada Termo de Embargo (TAD) em lote:
  1. Composição RGB anual em visão macro (4 km x 4 km ao redor do centroide).
  2. Séries trimestrais de NDVI e Falsa Cor com buffer dinâmico proporcional à área do polígono,
     seguindo uma cascata de prioridade de sensores (Sentinel 2, Landsat 9/8/7/5, MODIS).

Inclui suporte a retomada (checkpoint em CSV) e resumo da fila de tarefas do GEE.
"""
#Rodar no terminal "pip install -r requirements.txt" ou "python -m pip install -r requirements.txt"

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import ee
import pandas as pd
from tqdm import tqdm

# ==============================================================================
# 1. CONSTANTES E CONFIGURAÇÃO DA CASCATA DE SATÉLITES
# ==============================================================================

ANO_LIMITE_SUPERIOR = 2026
ANOS_RETROSPECTIVOS_PADRAO = 20
MARGEM_MINIMA_M = 500.0
RAIO_MACRO_RGB_M = 2000  # Gera bounding box de 4 km x 4 km
LIMITE_NUVENS_PCT = 70
CRS_SAIDA = "EPSG:4326"

TRIMESTRES: tuple[dict[str, str], ...] = (
    {"nome": "T1", "ini": "-01-01", "fim": "-03-31"},
    {"nome": "T2", "ini": "-04-01", "fim": "-06-30"},
    {"nome": "T3", "ini": "-07-01", "fim": "-09-30"},
    {"nome": "T4", "ini": "-10-01", "fim": "-12-31"},
)


@dataclass(frozen=True)
class ConfigSatelite:
    nome: str
    colecao: str
    escala_m: int
    bandas_ndvi: list[str]
    bandas_falsa_cor: list[str]
    bandas_rgb: Optional[list[str]] = None
    propriedade_nuvem: Optional[str] = None
    funcao_mascara: Optional[Callable[[ee.Image], ee.Image]] = None


# ==============================================================================
# 2. MÁSCARAS DE NUVENS E FUNÇÕES DE PRÉ-PROCESSAMENTO (GEE)

def mask_sentinel2(image: ee.Image) -> ee.Image:
    """Aplica máscara de nuvens/cirrus (QA60) e fator de escala para Sentinel-2 SR."""
    qa = image.select("QA60")
    mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    return image.updateMask(mask).divide(10000).copyProperties(image, ["system:time_start"])


def mask_landsat_c2(image: ee.Image) -> ee.Image:
    """Aplica máscara de nuvens/sombras (QA_PIXEL) e fator de escala para Landsat Collection 2 (L5/L7/L8/L9)."""
    qa = image.select("QA_PIXEL")
    mask = qa.bitwiseAnd(1 << 4).eq(0).And(qa.bitwiseAnd(1 << 3).eq(0))
    return (
        image.updateMask(mask)
        .multiply(0.0000275)
        .add(-0.2)
        .copyProperties(image, ["system:time_start"])
    )


CASCATA_SATELITES: tuple[ConfigSatelite, ...] = (
    ConfigSatelite(
        nome="Sentinel-2",
        colecao="COPERNICUS/S2_SR_HARMONIZED",
        escala_m=10,
        bandas_ndvi=["B8", "B4"],
        bandas_falsa_cor=["B11", "B8", "B4"],
        bandas_rgb=["B4", "B3", "B2"],
        propriedade_nuvem="CLOUDY_PIXEL_PERCENTAGE",
        funcao_mascara=mask_sentinel2,
    ),
    ConfigSatelite(
        nome="Landsat-9",
        colecao="LANDSAT/LC09/C02/T1_L2",
        escala_m=30,
        bandas_ndvi=["SR_B5", "SR_B4"],
        bandas_falsa_cor=["SR_B6", "SR_B5", "SR_B4"],
        bandas_rgb=["SR_B4", "SR_B3", "SR_B2"],
        propriedade_nuvem="CLOUD_COVER",
        funcao_mascara=mask_landsat_c2,
    ),
    ConfigSatelite(
        nome="Landsat-8",
        colecao="LANDSAT/LC08/C02/T1_L2",
        escala_m=30,
        bandas_ndvi=["SR_B5", "SR_B4"],
        bandas_falsa_cor=["SR_B6", "SR_B5", "SR_B4"],
        bandas_rgb=["SR_B4", "SR_B3", "SR_B2"],
        propriedade_nuvem="CLOUD_COVER",
        funcao_mascara=mask_landsat_c2,
    ),
    ConfigSatelite(
        nome="Landsat-5",
        colecao="LANDSAT/LT05/C02/T1_L2",
        escala_m=30,
        bandas_ndvi=["SR_B4", "SR_B3"],
        bandas_falsa_cor=["SR_B5", "SR_B4", "SR_B3"],
        bandas_rgb=["SR_B3", "SR_B2", "SR_B1"],
        propriedade_nuvem="CLOUD_COVER",
        funcao_mascara=mask_landsat_c2,
    ),
    ConfigSatelite(
        nome="Landsat-7",
        colecao="LANDSAT/LE07/C02/T1_L2",
        escala_m=30,
        bandas_ndvi=["SR_B4", "SR_B3"],
        bandas_falsa_cor=["SR_B5", "SR_B4", "SR_B3"],
        bandas_rgb=["SR_B3", "SR_B2", "SR_B1"],
        propriedade_nuvem="CLOUD_COVER",
        funcao_mascara=mask_landsat_c2,
    ),
    ConfigSatelite(
        nome="MODIS",
        colecao="MODIS/061/MOD09Q1",
        escala_m=250,
        bandas_ndvi=["sur_refl_b02", "sur_refl_b01"],
        bandas_falsa_cor=["sur_refl_b02", "sur_refl_b02", "sur_refl_b01"],
        bandas_rgb=None,
        propriedade_nuvem=None,
        funcao_mascara=None,
    ),
)


# ==============================================================================
# 3. FUNÇÕES AUXILIARES DE CHECKPOINT E GEOMETRIA
# 

def inicializar_gee(project_id: str) -> None:
    """Inicializa a sessão do Earth Engine; autenticação interativa se necessário."""
    try:
        ee.Initialize(project=project_id)
    except Exception:
        print("Sessão GEE não autenticada localmente....")
        ee.Authenticate()
        ee.Initialize(project=project_id)
    print(f"Conexão com o Google Earth Engine estabelecida (projeto: {project_id}).\n")


def carregar_checkpoint(caminho_csv: Path) -> set[str]:
    """Retorna o conjunto de num_tad já registrados no arquivo de checkpoint."""
    if not caminho_csv.exists():
        return set()

    df_existente = pd.read_csv(caminho_csv, dtype={"num_tad": str})
    if "num_tad" not in df_existente.columns:
        return set()

    tads_processados = set(df_existente["num_tad"].dropna().str.strip().unique())
    print(f"Checkpoint encontrado: {len(tads_processados)} TADs já processados serão ignorados.")
    return tads_processados


def salvar_checkpoint(registros: list[dict], caminho_csv: Path) -> None:
    """Anexa registros ao CSV de checkpoint preservando cabeçalho apenas na criação."""
    if not registros:
        return

    caminho_csv.parent.mkdir(parents=True, exist_ok=True)
    escrever_cabecalho = not caminho_csv.exists()
    pd.DataFrame(registros).to_csv(
        caminho_csv,
        mode="a",
        header=escrever_cabecalho,
        index=False,
    )


def calcular_janela_temporal(
    linha: pd.Series,
    anos_retrospectivos: int = ANOS_RETROSPECTIVOS_PADRAO,
) -> Optional[list[int]]:
    """
    Define a janela retrospectiva de N anos a contar da data de embargo.
    Retorna None caso o registro não possua data de embargo válida.
    """
    valor_data = (
        linha["dat_embargo"]
        if "dat_embargo" in linha.index and pd.notna(linha["dat_embargo"])
        else linha.get("dat_embarg")
    )
    dt_embargo = pd.to_datetime(valor_data, errors="coerce")
    if pd.isna(dt_embargo):
        return None

    ano_final = min(dt_embargo.year, ANO_LIMITE_SUPERIOR)
    ano_inicial = ano_final - anos_retrospectivos
    return list(range(ano_inicial, ano_final + 1))


def calcular_margem_buffer_m(linha: pd.Series) -> float:
    """Calcula margem proporcional (25% do lado equivalente em metros), com mínimo de 500 m."""
    def _parse_area(valor: object) -> float:
        num = pd.to_numeric(str(valor).replace(",", "."), errors="coerce")
        return float(num) if pd.notna(num) else 0.0

    maior_area_ha = max(
        _parse_area(linha.get("area_ib", 0)),
        _parse_area(linha.get("mp_areaha", 0)),
    )
    if maior_area_ha <= 0:
        return MARGEM_MINIMA_M

    lado_equivalente_m = (maior_area_ha * 10_000) ** 0.5
    return max(lado_equivalente_m * 0.25, MARGEM_MINIMA_M)


def aplicar_buffer_dinamico(feature: ee.Feature, margem_m: float) -> ee.Geometry:
    """Gera o bounding box expandido pela margem informada em metros."""
    return feature.geometry().bounds().buffer(margem_m).bounds()


def buscar_feature_tad(embargos_fc: ee.FeatureCollection, num_tad: str) -> Optional[ee.Feature]:
    """Busca o polígono do TAD na FeatureCollection tratando tipagem string ou inteira."""
    colecao = embargos_fc.filter(ee.Filter.eq("num_tad", num_tad))
    if colecao.size().getInfo() > 0:
        return colecao.first()

    try:
        colecao_int = embargos_fc.filter(ee.Filter.eq("num_tad", int(num_tad)))
        if colecao_int.size().getInfo() > 0:
            return colecao_int.first()
    except ValueError:
        pass

    return None


# ==============================================================================
# 4. SELEÇÃO DE IMAGENS E SUBMISSÃO DE TAREFAS (GEE)

def _filtrar_colecao(
    sat: ConfigSatelite,
    roi: ee.Geometry,
    data_ini: str,
    data_fim: str,
) -> ee.ImageCollection:
    """Filtra a coleção do satélite por área, período e percentual máximo de nuvens."""
    colecao = ee.ImageCollection(sat.colecao).filterBounds(roi).filterDate(data_ini, data_fim)
    if sat.propriedade_nuvem:
        colecao = colecao.filter(ee.Filter.lt(sat.propriedade_nuvem, LIMITE_NUVENS_PCT))
    return colecao


def buscar_melhor_imagem_trimestre(
    roi: ee.Geometry,
    data_ini: str,
    data_fim: str,
) -> tuple[Optional[ee.Image], Optional[str], Optional[int], Optional[ee.Image], Optional[ee.Image]]:
    """Percorre a cascata de satélites e retorna o qualityMosaic de NDVI da primeira coleção disponível."""
    for sat in CASCATA_SATELITES:
        colecao = _filtrar_colecao(sat, roi, data_ini, data_fim)
        if colecao.size().getInfo() == 0:
            continue

        if sat.funcao_mascara:
            colecao = colecao.map(sat.funcao_mascara)

        bandas_ndvi = sat.bandas_ndvi
        img = colecao.map(
            lambda i, b=bandas_ndvi: i.addBands(i.normalizedDifference(b).rename("NDVI"))
        ).qualityMosaic("NDVI")

        return img, sat.nome, sat.escala_m, img.select("NDVI"), img.select(sat.bandas_falsa_cor)

    return None, None, None, None, None


def gerar_composicao_rgb_anual(
    roi_rgb: ee.Geometry,
    ano: int,
) -> tuple[Optional[ee.Image], Optional[str], Optional[int]]:
    """Gera composição mediana RGB anual seguindo a cascata de sensores disponíveis."""
    data_ini, data_fim = f"{ano}-01-01", f"{ano}-12-31"

    for sat in CASCATA_SATELITES:
        if sat.bandas_rgb is None:
            continue

        colecao = _filtrar_colecao(sat, roi_rgb, data_ini, data_fim)
        if colecao.size().getInfo() == 0:
            continue

        if sat.funcao_mascara:
            colecao = colecao.map(sat.funcao_mascara)

        return colecao.median().select(sat.bandas_rgb), sat.nome, sat.escala_m

    return None, None, None


def iniciar_exportacao_drive(
    image: ee.Image,
    descricao: str,
    pasta_drive: str,
    region: ee.Geometry,
    scale: int,
) -> None:
    """Submete uma tarefa de exportação GeoTIFF (Float32) para o Google Drive."""
    task = ee.batch.Export.image.toDrive(
        image=image.toFloat(),
        description=descricao,
        folder=pasta_drive,
        region=region,
        scale=scale,
        crs=CRS_SAIDA,
    )
    task.start()


def exibir_status_tarefas_gee() -> None:
    """Lista e contabiliza o status atual das tarefas submetidas na conta GEE."""
    tarefas = ee.batch.Task.list()
    contagem = {
        "READY": sum(1 for t in tarefas if t.state == "READY"),
        "RUNNING": sum(1 for t in tarefas if t.state == "RUNNING"),
        "COMPLETED": sum(1 for t in tarefas if t.state == "COMPLETED"),
        "FAILED": sum(1 for t in tarefas if t.state == "FAILED"),
    }

    print("\n--- STATUS DAS EXPORTAÇÕES (GEE) ---")
    print(f"Na fila : {contagem['READY']}")
    print(f"Processando agora    : {contagem['RUNNING']}")
    print(f"Concluídas           : {contagem['COMPLETED']}")
    print(f"Falhas               : {contagem['FAILED']}")


# ==============================================================================
# 5. PROCESSAMENTO DO LOTE

def processar_lote(
    caminho_csv_base: Path,
    caminho_csv_saida: Path,
    asset_embargos: str,
    numero_do_lote: int,
    tamanho_do_lote: int, 
    anos_retrospectivos: int,
) -> None:
    """Executa o processamento em lote com retomada por checkpoint."""
    df_base = pd.read_csv(caminho_csv_base)
    df_base["num_tad"] = df_base["num_tad"].astype(str).str.strip()
    lista_geral_tads = df_base["num_tad"].unique().tolist()

    inicio = (numero_do_lote - 1) * tamanho_do_lote
    fim = inicio + tamanho_do_lote
    lote_tads = lista_geral_tads[inicio:fim]

    tads_ja_processados = carregar_checkpoint(caminho_csv_saida)
    embargos_fc = ee.FeatureCollection(asset_embargos)

    print(f"\nIniciando processamento — Lote {numero_do_lote} (janela: -{anos_retrospectivos} anos do embargo)")
    print(f"TADs no lote: {len(lote_tads)} (índices {inicio} a {fim})\n")

    tarefas_gee = 0
    with tqdm(total=len(lote_tads), desc=f"Lote {numero_do_lote}", colour="green") as pbar_global:
        for num_tad in lote_tads:
            if num_tad in tads_ja_processados:
                pbar_global.update(1)
                continue

            feat = buscar_feature_tad(embargos_fc, num_tad)
            if feat is None:
                tqdm.write(f"AVISO: Geometria do TAD {num_tad} não encontrada no GEE.")
                salvar_checkpoint(
                    [{"num_tad": num_tad, "satelite": "NENHUM", "ano_trimestre": "FALTA_POLIGONO", "escala_m": 0}],
                    caminho_csv_saida,
                )
                pbar_global.update(1)
                continue

            linha = df_base[df_base["num_tad"] == num_tad].iloc[0]
            anos_dinamicos = calcular_janela_temporal(linha, anos_retrospectivos=anos_retrospectivos)
            if anos_dinamicos is None:
                tqdm.write(f"AVISO: Data de embargo ausente/inválida para o TAD {num_tad}.")
                salvar_checkpoint(
                    [{"num_tad": num_tad, "satelite": "NENHUM", "ano_trimestre": "SEM_DATA_EMBARGO", "escala_m": 0}],
                    caminho_csv_saida,
                )
                pbar_global.update(1)
                continue

            margem_m = calcular_margem_buffer_m(linha)
            roi_buffer = aplicar_buffer_dinamico(feat, margem_m)
            roi_rgb = feat.geometry().centroid().buffer(RAIO_MACRO_RGB_M).bounds()
            pasta_drive = f"Embargo_BR_{num_tad}"

            dados_csv_do_tad: list[dict] = []
            total_etapas = len(anos_dinamicos) * (len(TRIMESTRES) + 1)

            with tqdm(total=total_etapas, desc=f"TAD {num_tad}", leave=False, colour="blue") as pbar_local:
                for ano in anos_dinamicos:
                    # 1. Composição RGB anual (visão macro de 4 km x 4 km)
                    pbar_local.set_postfix(Task=f"RGB_{ano}")
                    rgb_anual, sat_rgb, scale_rgb = gerar_composicao_rgb_anual(roi_rgb, ano)
                    if rgb_anual is not None and sat_rgb and scale_rgb:
                        iniciar_exportacao_drive(
                            image=rgb_anual,
                            descricao=f"BR_{num_tad}_{sat_rgb}_{ano}_Anual_RGB",
                            pasta_drive=pasta_drive,
                            region=roi_rgb,
                            scale=scale_rgb,
                        )
                        tarefas_gee += 1
                    pbar_local.update(1)

                    # 2. Série trimestral NDVI e Falsa Cor (buffer dinâmico)
                    for tri in TRIMESTRES:
                        pbar_local.set_postfix(Task=f"{ano}_{tri['nome']}")
                        img, sat_nome, scale, ndvi, fcor = buscar_melhor_imagem_trimestre(
                            roi_buffer,
                            f"{ano}{tri['ini']}",
                            f"{ano}{tri['fim']}",
                        )
                        if img is not None and sat_nome and scale and ndvi and fcor:
                            nome_base = f"BR_{num_tad}_{sat_nome}_{ano}_{tri['nome']}"
                            iniciar_exportacao_drive(ndvi, f"{nome_base}_NDVI", pasta_drive, roi_buffer, scale)
                            iniciar_exportacao_drive(fcor, f"{nome_base}_FalsaCor", pasta_drive, roi_buffer, scale)
                            tarefas_gee += 2

                            dados_csv_do_tad.append(
                                {
                                    "num_tad": num_tad,
                                    "satelite": sat_nome,
                                    "ano_trimestre": f"{ano}_{tri['nome']}",
                                    "escala_m": scale,
                                }
                            )
                        pbar_local.update(1)

            salvar_checkpoint(dados_csv_do_tad, caminho_csv_saida)
            pbar_global.set_postfix(Tarefas=tarefas_gee)
            pbar_global.update(1)

    print(f"\nExecução finalizada. Total de tarefas submetidas neste lote: {tarefas_gee}.")


# ==============================================================================
# 6. INTERFACE DE LINHA DE COMANDO 

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exporta séries temporais (RGB anual + NDVI/Falsa Cor trimestrais) de TADs via GEE."
    )
    parser.add_argument(
        "--gee-project",
        default=os.getenv("GEE_PROJECT_ID"),
        required=os.getenv("GEE_PROJECT_ID") is None,
        help="ID do projeto no Google Earth Engine (ou defina a variável de ambiente GEE_PROJECT_ID).",
    )
    parser.add_argument(
        "--asset-embargos",
        default=os.getenv("GEE_ASSET_EMBARGOS", "projects/<seu-projeto>/assets/tads_embargos"),
        help="Caminho da FeatureCollection de polígonos de embargos no GEE.",
    )
    parser.add_argument(
        "--csv-base",
        type=Path,
        default=Path("data/tads.csv"),
        help="Caminho para o CSV de entrada com a lista de TADs e datas de embargo.",
    )
    parser.add_argument(
        "--dir-saida",
        type=Path,
        default=Path("outputs"),
        help="Diretório local para salvar os arquivos CSV de checkpoint.",
    )
    parser.add_argument("--lote", type=int, default=1, help="Número do lote a processar (base 1).")
    parser.add_argument("--tamanho-lote", type=int, default=10, help="quantos poligonos serão carregados por requisição. GEE tem limite de 3.000 tarefas em fila, tamanho de lote muito grande pode estourar esse limite")
    parser.add_argument(
        "--anos-retrospectivos",
        type=int,
        default=ANOS_RETROSPECTIVOS_PADRAO,
        help="Quantidade de anos anteriores à data de embargo a incluir na série (padrão: 20).",
    )
    parser.add_argument(
        "--apenas-status",
        action="store_true",
        help="Exibe apenas o status atual da fila de tarefas no GEE sem iniciar novas exportações.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inicializar_gee(args.gee_project)

    if not args.apenas_status:
        caminho_csv_saida = args.dir_saida / f"historico_ndvi_lote{args.lote}_v2.csv"
        processar_lote(
            caminho_csv_base=args.csv_base,
            caminho_csv_saida=caminho_csv_saida,
            asset_embargos=args.asset_embargos,
            numero_do_lote=args.lote,
            tamanho_do_lote=args.tamanho_lote,
            anos_retrospectivos=args.anos_retrospectivos,
        )

    exibir_status_tarefas_gee()


if __name__ == "__main__":
    main()