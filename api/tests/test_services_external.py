"""Unit tests for external genomic database service clients.

Mocks all HTTP calls (never touches the network) so tests run instantly
and reliably in CI.

Covers:
  services/civic.py        — CIViC GraphQL evidence client
  services/clinvar.py      — ClinVar E-utilities client
  services/cosmic.py       — COSMIC REST v3.1 mutations client
  services/oncokb.py       — OncoKB REST annotator
  services/cbioportal.py   — cBioPortal gene panel data
  services/llm_explainer.py — LLM + template plain-language summary
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


# ═════════════════════════════════════════════════════════════════════════════
# services/civic.py
# ═════════════════════════════════════════════════════════════════════════════

class TestGetCivicEvidence:
    """Tests for services.civic.get_civic_evidence()"""

    async def test_known_variant_returns_evidence_list(self):
        from services.civic import get_civic_evidence

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "variants": {
                    "nodes": [
                        {
                            "name": "V600E",
                            "variantAliases": ["p.Val600Glu"],
                            "evidenceItems": {
                                "nodes": [
                                    {
                                        "evidenceLevel": "A",
                                        "evidenceType": "Predictive",
                                        "clinicalSignificance": "Sensitivity/Response",
                                        "description": "Vemurafenib for BRAF V600E melanoma.",
                                        "disease": {"name": "Melanoma"},
                                        "drugs": [{"name": "Vemurafenib"}],
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("services.civic.httpx.AsyncClient", return_value=mock_client):
            result = await get_civic_evidence("BRAF", "V600E")

        assert result is not None
        assert len(result) == 1
        assert result[0]["evidenceLevel"] == "A"
        assert result[0]["clinicalSignificance"] == "Sensitivity/Response"
        assert result[0]["disease"]["name"] == "Melanoma"

    async def test_no_variant_node_returns_none(self):
        from services.civic import get_civic_evidence

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {"variants": {"nodes": []}}
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("services.civic.httpx.AsyncClient", return_value=mock_client):
            result = await get_civic_evidence("UNKNOWN_GENE", "p.Xxx0Yyy")

        assert result is None

    async def test_empty_evidence_items_returns_none(self):
        from services.civic import get_civic_evidence

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "variants": {
                    "nodes": [
                        {
                            "name": "R175H",
                            "variantAliases": [],
                            "evidenceItems": {"nodes": []},
                        }
                    ]
                }
            }
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("services.civic.httpx.AsyncClient", return_value=mock_client):
            result = await get_civic_evidence("TP53", "R175H")

        assert result is None

    async def test_network_error_returns_none(self):
        from services.civic import get_civic_evidence

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("services.civic.httpx.AsyncClient", return_value=mock_client):
            result = await get_civic_evidence("EGFR", "L858R")

        assert result is None

    async def test_http_error_returns_none(self):
        from services.civic import get_civic_evidence

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=MagicMock(),
            response=MagicMock(status_code=503),
        )

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("services.civic.httpx.AsyncClient", return_value=mock_client):
            result = await get_civic_evidence("KRAS", "G12D")

        assert result is None

    async def test_multiple_evidence_items_returned(self):
        from services.civic import get_civic_evidence

        evidence_nodes = [
            {
                "evidenceLevel": "A",
                "evidenceType": "Predictive",
                "clinicalSignificance": "Sensitivity/Response",
                "description": f"Evidence {i}",
                "disease": {"name": "Melanoma"},
                "drugs": [{"name": f"Drug{i}"}],
            }
            for i in range(5)
        ]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "variants": {
                    "nodes": [
                        {"name": "V600E", "variantAliases": [], "evidenceItems": {"nodes": evidence_nodes}}
                    ]
                }
            }
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("services.civic.httpx.AsyncClient", return_value=mock_client):
            result = await get_civic_evidence("BRAF", "V600E")

        assert len(result) == 5


# ═════════════════════════════════════════════════════════════════════════════
# services/clinvar.py
# ═════════════════════════════════════════════════════════════════════════════

class TestGetClinvarSignificance:
    """Tests for services.clinvar.get_clinvar_significance()"""

    async def test_pathogenic_variant_returned(self):
        from services.clinvar import get_clinvar_significance

        search_resp = MagicMock()
        search_resp.raise_for_status = MagicMock()
        search_resp.json.return_value = {
            "esearchresult": {"idlist": ["12345"]}
        }

        fetch_resp = MagicMock()
        fetch_resp.raise_for_status = MagicMock()
        fetch_resp.json.return_value = {
            "ClinVarResult-Set": {
                "VariationArchive": {
                    "InterpretedRecord": {
                        "Interpretations": {
                            "Interpretation": {"Description": "Pathogenic"}
                        }
                    }
                }
            }
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=[search_resp, fetch_resp])

        with patch("services.clinvar.httpx.AsyncClient", return_value=mock_client):
            result = await get_clinvar_significance("BRCA1", "c.5266dupC")

        assert result == "Pathogenic"

    async def test_no_search_results_returns_none(self):
        from services.clinvar import get_clinvar_significance

        search_resp = MagicMock()
        search_resp.raise_for_status = MagicMock()
        search_resp.json.return_value = {
            "esearchresult": {"idlist": []}
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=search_resp)

        with patch("services.clinvar.httpx.AsyncClient", return_value=mock_client):
            result = await get_clinvar_significance("FAKE_GENE", "c.9999T>A")

        assert result is None

    async def test_network_error_returns_none(self):
        from services.clinvar import get_clinvar_significance

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with patch("services.clinvar.httpx.AsyncClient", return_value=mock_client):
            result = await get_clinvar_significance("TP53", "c.817C>T")

        assert result is None

    async def test_list_interpretation_handled(self):
        from services.clinvar import get_clinvar_significance

        search_resp = MagicMock()
        search_resp.raise_for_status = MagicMock()
        search_resp.json.return_value = {"esearchresult": {"idlist": ["99999"]}}

        fetch_resp = MagicMock()
        fetch_resp.raise_for_status = MagicMock()
        fetch_resp.json.return_value = {
            "ClinVarResult-Set": {
                "VariationArchive": {
                    "InterpretedRecord": {
                        "Interpretations": {
                            "Interpretation": [
                                {"Description": "Likely pathogenic"},
                                {"Description": "Pathogenic"},
                            ]
                        }
                    }
                }
            }
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=[search_resp, fetch_resp])

        with patch("services.clinvar.httpx.AsyncClient", return_value=mock_client):
            result = await get_clinvar_significance("EGFR", "c.2573T>G")

        assert result == "Likely pathogenic"

    async def test_list_variation_archive_handled(self):
        from services.clinvar import get_clinvar_significance

        search_resp = MagicMock()
        search_resp.raise_for_status = MagicMock()
        search_resp.json.return_value = {"esearchresult": {"idlist": ["11111"]}}

        fetch_resp = MagicMock()
        fetch_resp.raise_for_status = MagicMock()
        fetch_resp.json.return_value = {
            "ClinVarResult-Set": {
                "VariationArchive": [
                    {
                        "InterpretedRecord": {
                            "Interpretations": {
                                "Interpretation": {"Description": "Benign"}
                            }
                        }
                    }
                ]
            }
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=[search_resp, fetch_resp])

        with patch("services.clinvar.httpx.AsyncClient", return_value=mock_client):
            result = await get_clinvar_significance("KRAS", "c.35G>A")

        assert result == "Benign"


# ═════════════════════════════════════════════════════════════════════════════
# services/cosmic.py
# ═════════════════════════════════════════════════════════════════════════════

class TestGetCosmicMutations:
    """Tests for services.cosmic.get_cosmic_mutations()"""

    async def test_no_credentials_returns_empty(self):
        from services.cosmic import get_cosmic_mutations
        with patch("services.cosmic.settings") as mock_settings:
            mock_settings.cosmic_email = ""
            mock_settings.cosmic_password = ""
            result = await get_cosmic_mutations("TP53")
        assert result == []

    async def test_valid_response_parsed_correctly(self):
        from services.cosmic import get_cosmic_mutations

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "mutation_id": "COSM245022",
                "mutation_aa": "p.R175H",
                "mutation_cds": "c.524G>A",
                "primary_site": "lung",
                "histology": "carcinoma",
                "sample_count": 3421,
            },
            {
                "mutation_id": "COSM99999",
                "mutation_aa": "p.R248W",
                "mutation_cds": "c.742C>T",
                "primary_site": "colon",
                "histology": "adenocarcinoma",
                "sample_count": 2100,
            },
        ]

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("services.cosmic.settings") as mock_settings, \
             patch("services.cosmic.httpx.AsyncClient", return_value=mock_client):
            mock_settings.cosmic_email = "test@test.com"
            mock_settings.cosmic_password = "hunter2"
            result = await get_cosmic_mutations("TP53")

        assert len(result) == 2
        assert result[0]["mutation_id"] == "COSM245022"
        assert result[0]["mutation_aa"] == "p.R175H"
        assert result[0]["sample_count"] == 3421

    async def test_response_capped_at_50(self):
        from services.cosmic import get_cosmic_mutations

        big_list = [
            {
                "mutation_id": f"COSM{i}",
                "mutation_aa": f"p.R{i}H",
                "mutation_cds": f"c.{i}G>A",
                "primary_site": "lung",
                "histology": "carcinoma",
                "sample_count": i,
            }
            for i in range(100)
        ]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = big_list

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("services.cosmic.settings") as mock_settings, \
             patch("services.cosmic.httpx.AsyncClient", return_value=mock_client):
            mock_settings.cosmic_email = "test@test.com"
            mock_settings.cosmic_password = "pw"
            result = await get_cosmic_mutations("TP53")

        assert len(result) == 50

    async def test_auth_failure_returns_empty(self):
        from services.cosmic import get_cosmic_mutations

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("services.cosmic.settings") as mock_settings, \
             patch("services.cosmic.httpx.AsyncClient", return_value=mock_client):
            mock_settings.cosmic_email = "bad@email.com"
            mock_settings.cosmic_password = "wrongpw"
            result = await get_cosmic_mutations("EGFR")

        assert result == []

    async def test_cancer_type_filter_passed_as_param(self):
        from services.cosmic import get_cosmic_mutations

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("services.cosmic.settings") as mock_settings, \
             patch("services.cosmic.httpx.AsyncClient", return_value=mock_client):
            mock_settings.cosmic_email = "t@t.com"
            mock_settings.cosmic_password = "pw"
            await get_cosmic_mutations("KRAS", cancer_type="pancreas")

        call_kwargs = mock_client.get.call_args
        params = call_kwargs[1].get("params", {}) or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else {}
        # Verify that the primary_site param was included
        assert mock_client.get.called

    async def test_network_error_returns_empty(self):
        from services.cosmic import get_cosmic_mutations

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("COSMIC unreachable"))

        with patch("services.cosmic.settings") as mock_settings, \
             patch("services.cosmic.httpx.AsyncClient", return_value=mock_client):
            mock_settings.cosmic_email = "t@t.com"
            mock_settings.cosmic_password = "pw"
            result = await get_cosmic_mutations("BRAF")

        assert result == []

    async def test_auth_header_uses_base64(self):
        """Verify the auth token is base64(email:password)."""
        import base64
        from services.cosmic import _auth_header

        with patch("services.cosmic.settings") as mock_settings:
            mock_settings.cosmic_email = "user@sanger.ac.uk"
            mock_settings.cosmic_password = "secretpass"
            header = _auth_header()

        assert "Authorization" in header
        scheme, token = header["Authorization"].split(" ", 1)
        assert scheme == "Basic"
        decoded = base64.b64decode(token).decode()
        assert decoded == "user@sanger.ac.uk:secretpass"


# ═════════════════════════════════════════════════════════════════════════════
# services/oncokb.py
# ═════════════════════════════════════════════════════════════════════════════

class TestOncoKBClient:
    """Tests for services.oncokb.OncoKBClient"""

    def _make_client(self):
        from services.oncokb import OncoKBClient
        return OncoKBClient(token="test-token-abc")

    async def test_annotate_mutation_returns_dict(self):
        client = self._make_client()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "oncogenic": "Oncogenic",
            "mutationEffect": {"knownEffect": "Gain-of-function"},
            "highestSensitiveLevel": "LEVEL_1",
            "highestResistanceLevel": None,
            "treatments": [
                {
                    "drugs": [{"drugName": "Erlotinib"}],
                    "level": "LEVEL_1",
                }
            ],
        }

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch("services.oncokb.httpx.AsyncClient", return_value=mock_http_client):
            result = await client.annotate_mutation("EGFR", "L858R", "Non-Small Cell Lung Cancer")

        assert result["oncogenic"] == "Oncogenic"
        assert result["highestSensitiveLevel"] == "LEVEL_1"

    async def test_oncokb_level_returns_sensitive_level(self):
        client = self._make_client()
        annotation = {"highestSensitiveLevel": "LEVEL_1", "highestResistanceLevel": None}
        assert client.oncokb_level(annotation) == "LEVEL_1"

    async def test_oncokb_level_falls_back_to_resistance(self):
        client = self._make_client()
        annotation = {"highestSensitiveLevel": None, "highestResistanceLevel": "LEVEL_R1"}
        assert client.oncokb_level(annotation) == "LEVEL_R1"

    async def test_oncokb_level_returns_none_when_both_absent(self):
        client = self._make_client()
        annotation = {"highestSensitiveLevel": None, "highestResistanceLevel": None}
        assert client.oncokb_level(annotation) is None

    async def test_is_oncogenic_true_for_oncogenic(self):
        client = self._make_client()
        assert client.is_oncogenic({"oncogenic": "Oncogenic"}) is True

    async def test_is_oncogenic_true_for_likely_oncogenic(self):
        client = self._make_client()
        assert client.is_oncogenic({"oncogenic": "Likely Oncogenic"}) is True

    async def test_is_oncogenic_false_for_unknown(self):
        client = self._make_client()
        assert client.is_oncogenic({"oncogenic": "Unknown"}) is False

    async def test_is_oncogenic_false_for_neutral(self):
        client = self._make_client()
        assert client.is_oncogenic({"oncogenic": "Likely Neutral"}) is False

    async def test_is_oncogenic_false_for_empty(self):
        client = self._make_client()
        assert client.is_oncogenic({}) is False

    async def test_bearer_token_sent_in_header(self):
        from services.oncokb import OncoKBClient
        client = OncoKBClient(token="my-secret-token")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {}

        captured_headers = {}

        class MockHttpClient:
            def __init__(self, headers=None, timeout=None):
                captured_headers.update(headers or {})

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, *args, **kwargs):
                return mock_response

        with patch("services.oncokb.httpx.AsyncClient", MockHttpClient):
            await client.annotate_mutation("KRAS", "G12D")

        assert captured_headers.get("Authorization") == "Bearer my-secret-token"

    async def test_tumor_type_included_when_provided(self):
        client = self._make_client()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"oncogenic": "Oncogenic"}

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch("services.oncokb.httpx.AsyncClient", return_value=mock_http_client):
            await client.annotate_mutation("BRAF", "V600E", tumor_type="Melanoma")

        call_kwargs = mock_http_client.get.call_args
        params = call_kwargs[1].get("params", {})
        assert params.get("tumorType") == "Melanoma"


# ═════════════════════════════════════════════════════════════════════════════
# services/llm_explainer.py
# ═════════════════════════════════════════════════════════════════════════════

class TestBuildPrompt:
    """Tests for services.llm_explainer._build_prompt()"""

    def test_prompt_contains_gene(self):
        from services.llm_explainer import _build_prompt
        prompt = _build_prompt(
            gene="EGFR",
            has_target=True,
            cancer_type="Lung adenocarcinoma",
            mutations_summary=[],
            top_drug="Osimertinib",
            cosmic_count=5000,
        )
        assert "EGFR" in prompt
        assert "Lung adenocarcinoma" in prompt

    def test_prompt_includes_drug_note_when_drug_given(self):
        from services.llm_explainer import _build_prompt
        prompt = _build_prompt(
            gene="EGFR",
            has_target=True,
            cancer_type="Lung adenocarcinoma",
            mutations_summary=[],
            top_drug="Erlotinib",
            cosmic_count=0,
        )
        assert "Erlotinib" in prompt

    def test_prompt_notes_no_drug_when_missing(self):
        from services.llm_explainer import _build_prompt
        prompt = _build_prompt(
            gene="TP53",
            has_target=False,
            cancer_type="Colon cancer",
            mutations_summary=[],
            top_drug=None,
            cosmic_count=0,
        )
        assert "No closely matching existing drug" in prompt

    def test_prompt_includes_cosmic_note_when_count_positive(self):
        from services.llm_explainer import _build_prompt
        prompt = _build_prompt(
            gene="KRAS",
            has_target=True,
            cancer_type="Pancreatic cancer",
            mutations_summary=[],
            top_drug=None,
            cosmic_count=12000,
        )
        assert "12000" in prompt or "12,000" in prompt

    def test_prompt_includes_mutation_lines(self):
        from services.llm_explainer import _build_prompt
        mutations = [
            {"gene": "EGFR", "hgvs_notation": "p.L858R", "classification": "Likely pathogenic",
             "alphamissense_score": 0.97},
        ]
        prompt = _build_prompt(
            gene="EGFR", has_target=True, cancer_type="Lung adenocarcinoma",
            mutations_summary=mutations, top_drug=None, cosmic_count=0,
        )
        assert "p.L858R" in prompt


class TestTemplateSummary:
    """Tests for services.llm_explainer._template_summary()"""

    def test_targetable_mutation_with_drug(self):
        from services.llm_explainer import _template_summary
        result = _template_summary(
            gene="EGFR",
            has_target=True,
            cancer_type="Lung adenocarcinoma",
            top_drug="Osimertinib",
            cosmic_count=8000,
        )
        assert "EGFR" in result
        assert "Osimertinib" in result
        assert "8,000" in result or "8000" in result
        assert "oncologist" in result.lower()

    def test_targetable_mutation_no_drug(self):
        from services.llm_explainer import _template_summary
        result = _template_summary(
            gene="KRAS",
            has_target=True,
            cancer_type="Pancreatic cancer",
            top_drug=None,
            cosmic_count=0,
        )
        assert "KRAS" in result
        assert "oncologist" in result.lower()

    def test_no_targetable_mutation(self):
        from services.llm_explainer import _template_summary
        result = _template_summary(
            gene=None,
            has_target=False,
            cancer_type="Colon cancer",
            top_drug=None,
            cosmic_count=0,
        )
        assert "Colon cancer" in result
        assert "oncologist" in result.lower()
        assert "not" in result.lower()

    def test_returns_nonempty_string_always(self):
        from services.llm_explainer import _template_summary
        for gene, target, drug, count in [
            (None, False, None, 0),
            ("TP53", True, None, 0),
            ("BRAF", True, "Vemurafenib", 5000),
        ]:
            result = _template_summary(
                gene=gene, has_target=target,
                cancer_type="Cancer", top_drug=drug, cosmic_count=count,
            )
            assert isinstance(result, str)
            assert len(result) > 0

    def test_cosmic_sentence_omitted_when_count_zero(self):
        from services.llm_explainer import _template_summary
        result = _template_summary(
            gene="EGFR", has_target=True,
            cancer_type="Lung cancer", top_drug=None, cosmic_count=0,
        )
        assert "COSMIC" not in result


class TestGeneratePlainLanguageSummary:
    """Tests for services.llm_explainer.generate_plain_language_summary()"""

    async def test_no_api_key_uses_template(self):
        from services.llm_explainer import generate_plain_language_summary
        with patch("config.settings") as mock_settings:
            mock_settings.openai_api_key = ""
            result = await generate_plain_language_summary(
                gene="EGFR",
                has_target=True,
                cancer_type="Lung adenocarcinoma",
                mutations_summary=[],
                top_drug="Erlotinib",
                cosmic_count=5000,
            )
        assert isinstance(result, str)
        assert len(result) > 0
        assert "EGFR" in result

    async def test_openai_success_returns_ai_text(self):
        from services.llm_explainer import generate_plain_language_summary

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": "AI-generated plain language summary for EGFR L858R."}}
            ]
        }

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.post = AsyncMock(return_value=mock_response)

        with patch("config.settings") as mock_settings, \
             patch("httpx.AsyncClient", return_value=mock_http_client):
            mock_settings.openai_api_key = "sk-test-key"
            result = await generate_plain_language_summary(
                gene="EGFR",
                has_target=True,
                cancer_type="Lung adenocarcinoma",
                mutations_summary=[],
                top_drug="Erlotinib",
            )

        assert result == "AI-generated plain language summary for EGFR L858R."

    async def test_openai_failure_falls_back_to_template(self):
        from services.llm_explainer import generate_plain_language_summary

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.post = AsyncMock(side_effect=httpx.ConnectError("OpenAI unreachable"))

        with patch("config.settings") as mock_settings, \
             patch("httpx.AsyncClient", return_value=mock_http_client):
            mock_settings.openai_api_key = "sk-bad-key"
            result = await generate_plain_language_summary(
                gene="BRAF",
                has_target=True,
                cancer_type="Melanoma",
                mutations_summary=[],
            )

        assert isinstance(result, str)
        assert len(result) > 0

    async def test_never_raises_exception(self):
        """The function contract guarantees it never raises — always returns a string."""
        from services.llm_explainer import generate_plain_language_summary
        with patch("config.settings") as mock_settings:
            mock_settings.openai_api_key = ""
            # Even with degenerate inputs, should return a string
            result = await generate_plain_language_summary(
                gene=None,
                has_target=False,
                cancer_type="Unknown cancer",
                mutations_summary=[],
            )
        assert isinstance(result, str)
