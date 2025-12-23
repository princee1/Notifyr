from fastapi import APIRouter
from .kg_graph_router import KnowledgeGraphDBRouter
from .vector_db_router import VectorDBRouter
from .data_loader_router import DataLoaderRouter
from app.services import CostService
from app.services import VaultService
from app.container import Get
from app.utils.globals import AGENTIC_CAPABILITIES

Routers:list[APIRouter] = []

vaultService = Get(VaultService)
costService = Get(CostService)

if AGENTIC_CAPABILITIES['knowledge_graph']:
    Routers.append(KnowledgeGraphDBRouter())

if AGENTIC_CAPABILITIES['vector']:
    Routers.append(VectorDBRouter())

if AGENTIC_CAPABILITIES['vector']:
    Routers.append(DataLoaderRouter())

