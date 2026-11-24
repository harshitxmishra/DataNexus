package com.datanexus.ledger.controller;

import com.datanexus.ledger.domain.AuditEvent;
import com.datanexus.ledger.domain.LedgerStatus;
import com.datanexus.ledger.dto.CreateLedgerEntryRequest;
import com.datanexus.ledger.dto.LedgerEntryResponse;
import com.datanexus.ledger.dto.LedgerSummaryResponse;
import com.datanexus.ledger.service.LedgerService;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/ledger")
@CrossOrigin(origins = "*")
public class LedgerController {

    private final LedgerService ledgerService;

    public LedgerController(LedgerService ledgerService) {
        this.ledgerService = ledgerService;
    }

    @PostMapping("/entries")
    public ResponseEntity<LedgerEntryResponse> createEntry(@Valid @RequestBody CreateLedgerEntryRequest request) {
        LedgerEntryResponse response = ledgerService.createEntry(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @GetMapping("/entries")
    public ResponseEntity<Page<LedgerEntryResponse>> getEntries(
            @RequestParam(required = false) String currency,
            @RequestParam(required = false) LedgerStatus status,
            @RequestParam(name = "vendor_name", required = false) String vendorName,
            @RequestParam(name = "date_from", required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) Instant dateFrom,
            @RequestParam(name = "date_to", required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) Instant dateTo,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(defaultValue = "createdAt") String sortBy,
            @RequestParam(defaultValue = "DESC") String sortDir
    ) {
        Sort.Direction direction = "ASC".equalsIgnoreCase(sortDir) ? Sort.Direction.ASC : Sort.Direction.DESC;
        Pageable pageable = PageRequest.of(page, size, Sort.by(direction, sortBy));
        Page<LedgerEntryResponse> entries = ledgerService.findEntries(currency, status, vendorName, dateFrom, dateTo, pageable);
        return ResponseEntity.ok(entries);
    }

    @GetMapping("/summary")
    public ResponseEntity<LedgerSummaryResponse> getSummary() {
        LedgerSummaryResponse summary = ledgerService.getSummary();
        return ResponseEntity.ok(summary);
    }

    @GetMapping("/entries/{id}/audit")
    public ResponseEntity<List<AuditEvent>> getAuditTrail(@PathVariable UUID id) {
        List<AuditEvent> auditTrail = ledgerService.getAuditTrail(id);
        return ResponseEntity.ok(auditTrail);
    }
}
