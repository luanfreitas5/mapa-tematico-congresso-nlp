"""Configuração do projeto: leitura, validação e ambiente de execução.

Módulos
-------
settings
    Carrega os YAML de ``configs/`` e valida com Pydantic (``load_settings``).
paths
    Constantes de caminhos da raiz do repositório.
logging
    Configura logging com ``rich`` no console e arquivo com rotação diária.
environment
    Fixa sementes aleatórias para reprodutibilidade (``seed_everything``).
"""
