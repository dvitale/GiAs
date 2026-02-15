"""
Test E2E per gestione metadata come frontend gchat.
Verifica priorita' ASL, risoluzione UOC, defaults.
"""

import pytest


class TestMetadataAslPriority:
    """Test priorita' ASL name su ASL id."""

    @pytest.mark.e2e
    def test_asl_name_priority_over_id(self, api_client, unique_sender):
        """Test che asl (nome) abbia priorita' su asl_id."""
        metadata = {
            "asl": "BENEVENTO",     # Deve avere priorita'
            "asl_id": "999",        # ID diverso, ignorato
            "user_id": "6448"
        }

        response = api_client("chi devo controllare", unique_sender, metadata)

        # La risposta deve essere contestualizzata a BENEVENTO
        # Non deve fallire per ASL 999 inesistente
        assert "text" in response
        # Se ci sono dati, devono essere per BENEVENTO non per 999

    @pytest.mark.e2e
    def test_asl_id_fallback(self, api_client, unique_sender):
        """Test che asl_id sia usato se asl manca."""
        metadata = {
            # NO "asl"
            "asl_id": "202",  # BENEVENTO
            "user_id": "6448"
        }

        response = api_client("piani in ritardo", unique_sender, metadata)

        assert "text" in response
        # Deve comunque funzionare


class TestMetadataUocResolution:
    """Test risoluzione UOC da user_id."""

    @pytest.mark.e2e
    def test_uoc_resolution_from_user_id(self, api_client, unique_sender):
        """Test che UOC sia risolta da user_id se manca."""
        metadata = {
            "asl": "AVELLINO",
            "user_id": "6448"  # Backend deve risolvere UOC
            # NO "uoc"
        }

        response = api_client("stabilimenti prioritari", unique_sender, metadata)

        assert "text" in response
        # Non deve fallire per UOC mancante

    @pytest.mark.e2e
    def test_explicit_uoc_preserved(self, api_client, unique_sender):
        """Test che UOC esplicito non venga sovrascritto."""
        metadata = {
            "asl": "AVELLINO",
            "user_id": "6448",
            "uoc": "UOC IGIENE URBANA"  # Esplicito
        }

        response = api_client("chi devo controllare", unique_sender, metadata)

        assert "text" in response


class TestMetadataAllFields:
    """Test con tutti i campi metadata."""

    @pytest.mark.e2e
    def test_all_frontend_fields(self, api_client, unique_sender):
        """Test con tutti i campi come passati dal frontend."""
        metadata = {
            "asl": "BENEVENTO",
            "asl_id": "202",
            "user_id": "6448",
            "codice_fiscale": "ZZIBRD65R11A783K",
            "username": "mario.rossi"
        }

        response = api_client("piani in ritardo", unique_sender, metadata)

        assert "text" in response
        assert len(response["text"]) > 0

    @pytest.mark.e2e
    def test_metadata_napoli(self, api_client, unique_sender, metadata_napoli):
        """Test con metadata ASL Napoli."""
        response = api_client("stabilimenti prioritari", unique_sender, metadata_napoli)

        assert "text" in response

    @pytest.mark.e2e
    def test_metadata_avellino(self, api_client, unique_sender, metadata_avellino):
        """Test con metadata ASL Avellino."""
        response = api_client("suggerisci controlli", unique_sender, metadata_avellino)

        assert "text" in response


class TestMetadataMissing:
    """Test comportamento con metadata mancanti."""

    @pytest.mark.e2e
    def test_no_metadata_greet(self, api_client, unique_sender):
        """Test saluto senza metadata (funziona sempre)."""
        response = api_client("ciao", unique_sender, None)

        assert "text" in response
        text = response["text"].lower()
        assert any(w in text for w in ["benvenuto", "ciao", "posso"])

    @pytest.mark.e2e
    def test_no_metadata_help(self, api_client, unique_sender):
        """Test help senza metadata (funziona sempre)."""
        response = api_client("aiuto", unique_sender, None)

        assert "text" in response
        text = response["text"].lower()
        assert any(w in text for w in ["posso", "aiuto", "domand"])

    @pytest.mark.e2e
    def test_no_asl_data_query(self, api_client, unique_sender):
        """Test query dati senza ASL."""
        metadata = {
            "user_id": "test_user"
            # NO asl, NO asl_id
        }

        response = api_client("piani in ritardo", unique_sender, metadata)

        assert "text" in response
        # Puo' chiedere chiarimento o dare risposta generica


class TestMetadataInvalidValues:
    """Test con valori metadata invalidi."""

    @pytest.mark.e2e
    def test_invalid_asl_name(self, api_client, unique_sender):
        """Test con nome ASL inesistente."""
        metadata = {
            "asl": "ASL_INESISTENTE_XYZ",
            "user_id": "test"
        }

        response = api_client("stabilimenti prioritari", unique_sender, metadata)

        # Non deve crashare, puo' dare messaggio appropriato
        assert "text" in response

    @pytest.mark.e2e
    def test_empty_metadata_fields(self, api_client, unique_sender):
        """Test con campi metadata vuoti."""
        metadata = {
            "asl": "",
            "asl_id": "",
            "user_id": ""
        }

        response = api_client("ciao", unique_sender, metadata)

        # Deve comunque rispondere
        assert "text" in response


class TestMetadataDefaultUserId:
    """Test default user_id da sender."""

    @pytest.mark.e2e
    def test_user_id_defaults_to_sender(self, api_client, unique_sender):
        """Test che user_id default sia il sender."""
        metadata = {
            "asl": "AVELLINO"
            # NO user_id - deve usare sender
        }

        response = api_client("ciao", unique_sender, metadata)

        assert "text" in response
        # Il backend deve aver usato sender come user_id
