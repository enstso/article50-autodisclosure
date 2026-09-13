from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import PatchRejectRequest
from app.core.exceptions import (
    FindingNotFoundError,
    FindingNotRemediableError,
    InvalidPatchError,
    InvalidPatchTransitionError,
    PatchAlreadyAppliedError,
    PatchApplicationError,
    PatchNotApprovedError,
    PatchNotFoundError,
    RemediationAgentError,
    RemediationContextError,
)
from app.models import PatchApplyResponse, PatchProposal, VerificationResult
from app.services.patch_service import PatchService, get_patch_service
from app.services.scan_service import ScanService, _safe_error_message, get_scan_service

router = APIRouter(tags=["patches"])


@router.post(
    "/findings/{finding_id}/patch",
    response_model=PatchProposal,
    status_code=status.HTTP_201_CREATED,
)
def generate_patch(
    finding_id: str,
    scan_service: ScanService = Depends(get_scan_service),
    patch_service: PatchService = Depends(get_patch_service),
) -> PatchProposal:
    try:
        return patch_service.generate(finding_id, scan_service)
    except Exception as error:
        raise _patch_http_error(error) from error


@router.get("/patches/{patch_id}", response_model=PatchProposal)
def get_patch(
    patch_id: str,
    patch_service: PatchService = Depends(get_patch_service),
) -> PatchProposal:
    try:
        return patch_service.get(patch_id)
    except Exception as error:
        raise _patch_http_error(error) from error


@router.get("/patches/{patch_id}/verification", response_model=VerificationResult)
def get_patch_verification(
    patch_id: str,
    patch_service: PatchService = Depends(get_patch_service),
) -> VerificationResult:
    try:
        patch_service.get(patch_id)
        verification = patch_service.get_verification_for_patch(patch_id)
        if verification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patch verification not found.",
            )
        return verification
    except HTTPException:
        raise
    except Exception as error:
        raise _patch_http_error(error) from error


@router.post("/patches/{patch_id}/approve", response_model=PatchProposal)
def approve_patch(
    patch_id: str,
    scan_service: ScanService = Depends(get_scan_service),
    patch_service: PatchService = Depends(get_patch_service),
) -> PatchProposal:
    try:
        return patch_service.approve(patch_id, scan_service)
    except Exception as error:
        raise _patch_http_error(error) from error


@router.post("/patches/{patch_id}/reject", response_model=PatchProposal)
def reject_patch(
    patch_id: str,
    request: PatchRejectRequest | None = None,
    scan_service: ScanService = Depends(get_scan_service),
    patch_service: PatchService = Depends(get_patch_service),
) -> PatchProposal:
    try:
        return patch_service.reject(
            patch_id,
            scan_service,
            reason=request.reason if request is not None else None,
        )
    except Exception as error:
        raise _patch_http_error(error) from error


@router.post("/patches/{patch_id}/apply", response_model=PatchApplyResponse)
def apply_patch(
    patch_id: str,
    scan_service: ScanService = Depends(get_scan_service),
    patch_service: PatchService = Depends(get_patch_service),
) -> PatchApplyResponse:
    try:
        return patch_service.apply(patch_id, scan_service)
    except Exception as error:
        raise _patch_http_error(error) from error


def _patch_http_error(error: Exception) -> HTTPException:
    if isinstance(error, (FindingNotFoundError, PatchNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(
        error,
        (
            FindingNotRemediableError,
            InvalidPatchTransitionError,
            PatchAlreadyAppliedError,
            PatchNotApprovedError,
        ),
    ):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, (InvalidPatchError, RemediationContextError)):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    if isinstance(error, RemediationAgentError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The remediation agent could not produce a valid proposal.",
        )
    if isinstance(error, PatchApplicationError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        )
    if isinstance(error, (ClientError, NoCredentialsError, PartialCredentialsError)):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_safe_error_message(error),
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Patch operation failed.",
    )
