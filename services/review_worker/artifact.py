"""Receive only the M0 typed data artifact from the official A2A SDK."""
from google.protobuf.json_format import MessageToDict

from services.m0_contracts import BUNDLE_MEDIA_TYPE, EvidenceBundle, RetrievalRequest


def read_bundle(artifact, request: RetrievalRequest) -> EvidenceBundle:
    if artifact.name != "EvidenceBundle" or len(artifact.parts) != 1:
        raise ValueError("Expected one EvidenceBundle data part")
    part = artifact.parts[0]
    if not part.HasField("data") or part.media_type != BUNDLE_MEDIA_TYPE:
        raise ValueError("Unexpected EvidenceBundle media type")
    bundle = EvidenceBundle.model_validate(MessageToDict(part.data))
    if (
        artifact.artifact_id != str(bundle.bundle_id)
        or bundle.run_id != request.run_id
        or bundle.query != request.query
        or bundle.cutoff != request.cutoff
    ):
        raise ValueError("EvidenceBundle does not match the request")
    return bundle
