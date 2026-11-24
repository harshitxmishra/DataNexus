package com.datanexus.ledger.service;

import com.datanexus.ledger.domain.AuditEvent;
import com.datanexus.ledger.domain.LedgerEntry;
import com.datanexus.ledger.domain.LedgerStatus;
import com.datanexus.ledger.dto.CreateLedgerEntryRequest;
import com.datanexus.ledger.dto.LedgerEntryResponse;
import com.datanexus.ledger.dto.LedgerSummaryItem;
import com.datanexus.ledger.dto.LedgerSummaryResponse;
import com.datanexus.ledger.repository.AuditEventRepository;
import com.datanexus.ledger.repository.LedgerEntryRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.persistence.criteria.Predicate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.*;

@Service
public class LedgerService {

    private static final Logger log = LoggerFactory.getLogger(LedgerService.class);

    private final LedgerEntryRepository ledgerEntryRepository;
    private final AuditEventRepository auditEventRepository;
    private final ObjectMapper objectMapper;

    public LedgerService(LedgerEntryRepository ledgerEntryRepository,
                         AuditEventRepository auditEventRepository,
                         ObjectMapper objectMapper) {
        this.ledgerEntryRepository = ledgerEntryRepository;
        this.auditEventRepository = auditEventRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public LedgerEntryResponse createEntry(CreateLedgerEntryRequest request) {
        log.info("Ingesting ledger entry: invoice={}, vendor={}, amount={} {}",
                request.getInvoiceNumber(), request.getVendorName(), request.getAmount(), request.getCurrency());

        LedgerEntry entry = new LedgerEntry();
        entry.setId(UUID.randomUUID());
        entry.setInvoiceNumber(request.getInvoiceNumber());
        entry.setVendorName(request.getVendorName());
        entry.setCurrency(request.getCurrency().toUpperCase());
        entry.setAmount(request.getAmount());
        entry.setStatus(request.getStatus() != null ? request.getStatus() : LedgerStatus.VALIDATED);
        entry.setValidationScore(request.getValidationScore());
        entry.setSourceDocHash(request.getSourceDocHash());
        Instant now = Instant.now();
        entry.setCreatedAt(now);
        entry.setUpdatedAt(now);

        LedgerEntry savedEntry = ledgerEntryRepository.save(entry);

        String payloadJson = "{}";
        try {
            Map<String, Object> payloadMap = new HashMap<>();
            if (request.getMetadata() != null) {
                payloadMap.putAll(request.getMetadata());
            }
            payloadMap.put("invoiceNumber", entry.getInvoiceNumber());
            payloadMap.put("amount", entry.getAmount());
            payloadMap.put("currency", entry.getCurrency());
            payloadMap.put("status", entry.getStatus().name());
            payloadMap.put("validationScore", entry.getValidationScore());
            payloadJson = objectMapper.writeValueAsString(payloadMap);
        } catch (Exception e) {
            log.warn("Failed to serialize audit payload: {}", e.getMessage());
            payloadJson = "{\"error\":\"serialization_failed\"}";
        }

        AuditEvent auditEvent = new AuditEvent(
                savedEntry.getId(),
                "INVOICE_VALIDATED_INGESTION",
                request.getActor() != null ? request.getActor() : "fastapi-bridge",
                payloadJson
        );
        auditEventRepository.save(auditEvent);

        log.info("Ledger entry created atomically with id={} and auditEventId={}",
                savedEntry.getId(), auditEvent.getId());

        return LedgerEntryResponse.fromEntity(savedEntry);
    }

    @Transactional(readOnly = true)
    public Page<LedgerEntryResponse> findEntries(String currency,
                                                LedgerStatus status,
                                                String vendorName,
                                                Instant dateFrom,
                                                Instant dateTo,
                                                Pageable pageable) {
        Specification<LedgerEntry> spec = (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();

            if (currency != null && !currency.isBlank()) {
                predicates.add(cb.equal(cb.upper(root.get("currency")), currency.trim().toUpperCase()));
            }
            if (status != null) {
                predicates.add(cb.equal(root.get("status"), status));
            }
            if (vendorName != null && !vendorName.isBlank()) {
                predicates.add(cb.like(cb.lower(root.get("vendorName")), "%" + vendorName.trim().toLowerCase() + "%"));
            }
            if (dateFrom != null) {
                predicates.add(cb.greaterThanOrEqualTo(root.get("createdAt"), dateFrom));
            }
            if (dateTo != null) {
                predicates.add(cb.lessThanOrEqualTo(root.get("createdAt"), dateTo));
            }

            return cb.and(predicates.toArray(new Predicate[0]));
        };

        return ledgerEntryRepository.findAll(spec, pageable).map(LedgerEntryResponse::fromEntity);
    }

    @Transactional(readOnly = true)
    public LedgerSummaryResponse getSummary() {
        List<LedgerSummaryItem> summaries = ledgerEntryRepository.getMultiCurrencyRollup();
        long totalCount = 0;
        BigDecimal totalVolume = BigDecimal.ZERO;

        for (LedgerSummaryItem item : summaries) {
            totalCount += item.getCount();
            if (item.getTotalVolume() != null) {
                totalVolume = totalVolume.add(item.getTotalVolume());
            }
        }

        return new LedgerSummaryResponse(summaries, totalCount, totalVolume);
    }

    @Transactional(readOnly = true)
    public List<AuditEvent> getAuditTrail(UUID ledgerEntryId) {
        return auditEventRepository.findByLedgerEntryIdOrderByCreatedAtDesc(ledgerEntryId);
    }
}
