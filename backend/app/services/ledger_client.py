import logging
from typing import Any, Dict, Optional
import httpx

from backend.app.config import settings

logger = logging.getLogger(__name__)

class LedgerClient:
    """
    Lightweight, resilient HTTP client bridge connecting DataNexus Python/FastAPI
    to the Java 21 Spring Boot Financial Ledger & Audit service.
    Designed with graceful degradation and zero-regression guarantees.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: float = 2.0):
        self.base_url = (base_url or getattr(settings, "LEDGER_SERVICE_URL", "")).rstrip("/")
        self.timeout = timeout

    @property
    def is_enabled(self) -> bool:
        return bool(self.base_url)

    async def forward_validated_invoice(
        self,
        invoice_number: str,
        vendor_name: str,
        currency: str,
        amount: float,
        status: str = "VALIDATED",
        validation_score: Optional[float] = None,
        source_doc_hash: Optional[str] = None,
        actor: str = "fastapi-bridge",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self.is_enabled:
            logger.debug("LedgerClient is disabled: LEDGER_SERVICE_URL is not configured.")
            return None

        url = f"{self.base_url}/api/v1/ledger/entries"
        payload = {
            "invoiceNumber": invoice_number or "UNKNOWN",
            "vendorName": vendor_name or "Unknown Vendor",
            "currency": (currency or "USD").upper()[:3],
            "amount": max(float(amount), 0.0001),
            "status": status,
            "validationScore": round(float(validation_score), 2) if validation_score is not None else 100.0,
            "sourceDocHash": source_doc_hash or "",
            "actor": actor,
            "metadata": metadata or {},
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                if response.status_code in (200, 201):
                    logger.info("Successfully posted invoice %s to ledger service", invoice_number)
                    return response.json()
                else:
                    logger.warning(
                        "Ledger service returned non-2xx status code %d: %s",
                        response.status_code,
                        response.text,
                    )
                    return None
        except httpx.TimeoutException:
            logger.warning("Timeout (%ss) communicating with ledger service at %s", self.timeout, url)
            return None
        except Exception as exc:
            logger.warning("Failed to forward invoice %s to ledger service: %s", invoice_number, exc)
            return None

    def forward_validated_invoice_sync(
        self,
        invoice_number: str,
        vendor_name: str,
        currency: str,
        amount: float,
        status: str = "VALIDATED",
        validation_score: Optional[float] = None,
        source_doc_hash: Optional[str] = None,
        actor: str = "fastapi-bridge",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self.is_enabled:
            return None

        url = f"{self.base_url}/api/v1/ledger/entries"
        payload = {
            "invoiceNumber": invoice_number or "UNKNOWN",
            "vendorName": vendor_name or "Unknown Vendor",
            "currency": (currency or "USD").upper()[:3],
            "amount": max(float(amount), 0.0001),
            "status": status,
            "validationScore": round(float(validation_score), 2) if validation_score is not None else 100.0,
            "sourceDocHash": source_doc_hash or "",
            "actor": actor,
            "metadata": metadata or {},
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
                if response.status_code in (200, 201):
                    logger.info("Successfully synced invoice %s to ledger service", invoice_number)
                    return response.json()
                else:
                    logger.warning("Ledger sync returned code %d: %s", response.status_code, response.text)
                    return None
        except Exception as exc:
            logger.warning("Graceful skip: ledger service sync failed (%s)", exc)
            return None

ledger_client = LedgerClient()
