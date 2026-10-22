"""Persistência em camadas (bronze/silver/gold).

Módulos
-------
parquet
    Leitura/escrita de Parquet com erros do domínio.
bronze
    ``BronzeStore``: snapshots imutáveis e datados, com manifesto e hash.
"""
