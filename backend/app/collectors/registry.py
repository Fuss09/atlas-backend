"""
Atlas - Collector Registry
===========================
Point d'entrée unique pour accéder aux collecteurs.

Ajouter un nouveau collecteur = 3 étapes :
1. Créer app/collectors/mon_collecteur.py avec la classe
2. L'importer ici dans REGISTRY
3. Ajouter l'entrée dans DiscoverySourceName (models/discovery.py)

Le reste du code (service, API) n'a pas besoin d'être modifié.
"""

from app.collectors.base import BaseCollector
from app.collectors.crunchbase import CrunchbaseCollector
from app.collectors.github import GitHubCollector
from app.collectors.sec import SecCollector
from app.collectors.ycombinator import YCombinatorCollector
from app.models.discovery import DiscoverySourceName

REGISTRY: dict[DiscoverySourceName, type[BaseCollector]] = {
    DiscoverySourceName.SEC: SecCollector,
    DiscoverySourceName.GITHUB: GitHubCollector,
    DiscoverySourceName.YCOMBINATOR: YCombinatorCollector,
    DiscoverySourceName.CRUNCHBASE: CrunchbaseCollector,
    # Futurs collecteurs — ajouter ici quand implémentés :
    # DiscoverySourceName.FDA: FdaCollector,
    # DiscoverySourceName.USPTO: UsptoCollector,
    # DiscoverySourceName.ARXIV: ArxivCollector,
    # DiscoverySourceName.HUGGINGFACE: HuggingFaceCollector,
    # DiscoverySourceName.PRODUCTHUNT: ProductHuntCollector,
    # DiscoverySourceName.PITCHBOOK: PitchbookCollector,
}


def get_collector(
    source: DiscoverySourceName,
    params: dict | None = None,
) -> BaseCollector:
    """
    Instancie et retourne le collecteur correspondant à la source.

    Raises:
        ValueError: Si la source n'est pas enregistrée dans le registry.
    """
    cls = REGISTRY.get(source)
    if not cls:
        available = [s.value for s in REGISTRY]
        raise ValueError(
            f"No collector registered for source '{source}'. "
            f"Available: {available}"
        )
    return cls(params=params)


def list_available_sources() -> list[dict]:
    """Retourne la liste des sources disponibles avec leur statut."""
    result = []
    for source, cls in REGISTRY.items():
        result.append({
            "source": source.value,
            "collector": cls.__name__,
            "implemented": True,
        })
    # Sources dans le modèle mais pas encore dans le registry
    for source in DiscoverySourceName:
        if source not in REGISTRY:
            result.append({
                "source": source.value,
                "collector": None,
                "implemented": False,
            })
    return result
