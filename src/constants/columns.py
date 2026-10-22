"""Nomes de colunas das camadas de dados."""

# --- Silver ---------------------------------------------------------------
DEPUTY_ID = "deputy_id"
PROPOSITION_ID = "proposition_id"
VOTING_ID = "voting_id"
SPEECH_ID = "speech_id"
PARTY = "party"
VOTE = "vote"
TEXT = "text"
TEXT_CLEAN = "text_clean"
PERIOD = "period"  # primeiro dia do mês do documento

# --- Gold -----------------------------------------------------------------
TOPIC = "topic"

# --- Mapeamentos bronze (API, pt-BR) → silver (inglês) --------------------
DEPUTIES_RENAME = {
    "id": DEPUTY_ID,
    "nome": "name",
    "siglaPartido": PARTY,
    "siglaUf": "state",
    "idLegislatura": "legislature_id",
}
PROPOSITIONS_RENAME = {
    "id": PROPOSITION_ID,
    "siglaTipo": "type_code",
    "numero": "number",
    "ano": "year",
    "ementa": TEXT,
}

# --- Votos aceitos na construção da rede de alinhamento --------------------
VOTE_YES = "Sim"
VOTE_NO = "Não"
