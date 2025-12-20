from fastapi import APIRouter
from .kg_graph_router import KnowledgeGraphDBRouter
from .vector_db_router import VectorDBRouter
from app.services import CostService
from app.services import VaultService
from app.container import Get

Routers:list[APIRouter] = []

vaultService = Get(VaultService)
costService = Get(CostService)


Routers.append(KnowledgeGraphDBRouter())
Routers.append(VectorDBRouter())