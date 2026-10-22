"""Ingestão da API de Dados Abertos da Câmara dos Deputados.

Módulos
-------
client
    ``CamaraClient``: HTTP com paginação por ``links.next`` e retry exponencial.
sources
    Funções ``fetch_*`` que transformam endpoints em listas de registros.
runner
    ``run_ingestion``: orquestra as fontes, com cache idempotente na bronze.
"""
