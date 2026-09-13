from fastapi import APIRouter, Depends, HTTPException, status

from app.models import Scan, ScanCreateRequest
from app.services.scan_service import ScanService, get_scan_service

router = APIRouter(prefix="/scans", tags=["scans"])


@router.post("", response_model=Scan, status_code=status.HTTP_201_CREATED)
def create_scan(
    request: ScanCreateRequest,
    scan_service: ScanService = Depends(get_scan_service),
) -> Scan:
    return scan_service.create_scan(request.repository_url)


@router.get("/{scan_id}", response_model=Scan)
def get_scan(
    scan_id: str,
    scan_service: ScanService = Depends(get_scan_service),
) -> Scan:
    scan = scan_service.get_scan(scan_id)
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return scan
