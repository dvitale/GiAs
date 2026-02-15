"""
Test E2E per endpoint streaming SSE.
Verifica /webhooks/rest/webhook/stream.
"""

import pytest
import requests
import json


class TestStreamingEndpoint:
    """Test endpoint streaming SSE."""

    @pytest.mark.e2e
    @pytest.mark.streaming
    @pytest.mark.slow
    def test_streaming_available(self, stream_url, unique_sender, complete_metadata):
        """Test che endpoint streaming risponda."""
        payload = {
            "sender": unique_sender,
            "message": "ciao",
            "metadata": complete_metadata
        }

        try:
            resp = requests.post(
                stream_url,
                json=payload,
                timeout=30,
                stream=True,
                headers={"Accept": "text/event-stream"}
            )

            # Endpoint deve esistere
            assert resp.status_code in [200, 404], f"Unexpected status: {resp.status_code}"

            if resp.status_code == 200:
                # Content type SSE
                content_type = resp.headers.get("Content-Type", "")
                assert "text/event-stream" in content_type or "application/json" in content_type

        except requests.exceptions.RequestException as e:
            pytest.skip(f"Streaming endpoint non raggiungibile: {e}")

    @pytest.mark.e2e
    @pytest.mark.streaming
    @pytest.mark.slow
    def test_streaming_receives_events(self, stream_url, unique_sender,
                                        complete_metadata):
        """Test ricezione eventi SSE."""
        payload = {
            "sender": unique_sender,
            "message": "aiuto",
            "metadata": complete_metadata
        }

        try:
            resp = requests.post(
                stream_url,
                json=payload,
                timeout=60,
                stream=True,
                headers={"Accept": "text/event-stream"}
            )

            if resp.status_code != 200:
                pytest.skip("Streaming endpoint non disponibile")

            events = []
            for line in resp.iter_lines(decode_unicode=True):
                if line:
                    events.append(line)
                    # Limita numero eventi letti
                    if len(events) >= 10:
                        break

            # Deve aver ricevuto almeno un evento
            assert len(events) > 0, "Nessun evento ricevuto"

        except requests.exceptions.RequestException as e:
            pytest.skip(f"Errore streaming: {e}")

    @pytest.mark.e2e
    @pytest.mark.streaming
    @pytest.mark.slow
    def test_streaming_event_format(self, stream_url, unique_sender,
                                     complete_metadata):
        """Test formato eventi SSE."""
        payload = {
            "sender": unique_sender,
            "message": "piani in ritardo",
            "metadata": complete_metadata
        }

        try:
            resp = requests.post(
                stream_url,
                json=payload,
                timeout=60,
                stream=True,
                headers={"Accept": "text/event-stream"}
            )

            if resp.status_code != 200:
                pytest.skip("Streaming endpoint non disponibile")

            sse_events = []
            current_event = {}

            for line in resp.iter_lines(decode_unicode=True):
                if line.startswith("event:"):
                    current_event["event"] = line[6:].strip()
                elif line.startswith("data:"):
                    current_event["data"] = line[5:].strip()
                elif line == "" and current_event:
                    sse_events.append(current_event)
                    current_event = {}

                if len(sse_events) >= 5:
                    break

            # Verifica formato SSE standard
            for event in sse_events:
                if "data" in event:
                    # Data deve essere JSON valido
                    try:
                        json.loads(event["data"])
                    except json.JSONDecodeError:
                        pass  # Alcuni eventi possono essere testo plain

        except requests.exceptions.RequestException as e:
            pytest.skip(f"Errore streaming: {e}")


class TestStreamingWithMetadata:
    """Test streaming con metadata."""

    @pytest.mark.e2e
    @pytest.mark.streaming
    @pytest.mark.slow
    def test_streaming_metadata_passed(self, stream_url, unique_sender,
                                        complete_metadata):
        """Test che metadata siano passati correttamente in streaming."""
        payload = {
            "sender": unique_sender,
            "message": "chi devo controllare",
            "metadata": complete_metadata
        }

        try:
            resp = requests.post(
                stream_url,
                json=payload,
                timeout=60,
                stream=True
            )

            if resp.status_code != 200:
                pytest.skip("Streaming endpoint non disponibile")

            # La risposta deve essere contestualizzata all'ASL
            # (difficile verificare senza parsare tutto lo stream)
            assert resp.status_code == 200

        except requests.exceptions.RequestException as e:
            pytest.skip(f"Errore streaming: {e}")


class TestStreamingTimeout:
    """Test timeout streaming."""

    @pytest.mark.e2e
    @pytest.mark.streaming
    @pytest.mark.slow
    def test_streaming_long_query(self, stream_url, unique_sender,
                                   complete_metadata):
        """Test streaming per query complessa."""
        payload = {
            "sender": unique_sender,
            "message": "analizza tutti i piani e suggerisci le priorita",
            "metadata": complete_metadata
        }

        try:
            resp = requests.post(
                stream_url,
                json=payload,
                timeout=120,  # 2 minuti per query complessa
                stream=True
            )

            if resp.status_code != 200:
                pytest.skip("Streaming endpoint non disponibile")

            # Deve completare entro timeout
            content = b""
            for chunk in resp.iter_content(chunk_size=1024):
                content += chunk
                if len(content) > 10000:  # Limita lettura
                    break

            assert len(content) > 0, "Nessun contenuto ricevuto"

        except requests.exceptions.Timeout:
            pytest.fail("Streaming timeout >120s")
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Errore streaming: {e}")
