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
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.jpa.domain.Specification;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.*;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class LedgerServiceTest {

    @Mock
    private LedgerEntryRepository ledgerEntryRepository;

    @Mock
    private AuditEventRepository auditEventRepository;

    private ObjectMapper objectMapper;
    private LedgerService ledgerService;

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper();
        ledgerService = new LedgerService(ledgerEntryRepository, auditEventRepository, objectMapper);
    }

    @Test
    @DisplayName("createEntry should persist ledger entry and audit event atomically")
    void testCreateEntry() {
        CreateLedgerEntryRequest req = new CreateLedgerEntryRequest();
        req.setInvoiceNumber("INV-2026-001");
        req.setVendorName("Acme Corp");
        req.setCurrency("USD");
        req.setAmount(new BigDecimal("1250.5000"));
        req.setStatus(LedgerStatus.VALIDATED);
        req.setValidationScore(new BigDecimal("98.50"));
        req.setSourceDocHash("a1b2c3d4e5f6");
        req.setActor("finance-worker");
        req.setMetadata(Map.of("poNumber", "PO-991"));

        UUID generatedId = UUID.randomUUID();
        when(ledgerEntryRepository.save(any(LedgerEntry.class))).thenAnswer(invocation -> {
            LedgerEntry e = invocation.getArgument(0);
            e.setId(generatedId);
            return e;
        });

        LedgerEntryResponse res = ledgerService.createEntry(req);

        assertThat(res).isNotNull();
        assertThat(res.getId()).isEqualTo(generatedId);
        assertThat(res.getInvoiceNumber()).isEqualTo("INV-2026-001");
        assertThat(res.getCurrency()).isEqualTo("USD");

        ArgumentCaptor<AuditEvent> auditCaptor = ArgumentCaptor.forClass(AuditEvent.class);
        verify(auditEventRepository, times(1)).save(auditCaptor.capture());

        AuditEvent savedAudit = auditCaptor.getValue();
        assertThat(savedAudit.getLedgerEntryId()).isEqualTo(generatedId);
        assertThat(savedAudit.getActor()).isEqualTo("finance-worker");
        assertThat(savedAudit.getEventType()).isEqualTo("INVOICE_VALIDATED_INGESTION");
        assertThat(savedAudit.getPayload()).contains("INV-2026-001");
    }

    @Test
    @DisplayName("getSummary should calculate multi-currency rollup aggregation")
    void testGetSummary() {
        List<LedgerSummaryItem> rollup = List.of(
                new LedgerSummaryItem("USD", LedgerStatus.SETTLED, new BigDecimal("5000.00"), 5L, 95.0),
                new LedgerSummaryItem("EUR", LedgerStatus.VALIDATED, new BigDecimal("3200.00"), 3L, 91.5)
        );
        when(ledgerEntryRepository.getMultiCurrencyRollup()).thenReturn(rollup);

        LedgerSummaryResponse summary = ledgerService.getSummary();

        assertThat(summary.getSummaries()).hasSize(2);
        assertThat(summary.getTotalCount()).isEqualTo(8L);
        assertThat(summary.getTotalVolume()).isEqualByComparingTo(new BigDecimal("8200.00"));
    }

    @Test
    @DisplayName("findEntries should query repository with specifications")
    @SuppressWarnings("unchecked")
    void testFindEntries() {
        LedgerEntry entry = new LedgerEntry();
        entry.setId(UUID.randomUUID());
        entry.setInvoiceNumber("INV-FILTER-01");
        entry.setVendorName("Global Freight");
        entry.setCurrency("EUR");
        entry.setAmount(new BigDecimal("750.00"));
        entry.setStatus(LedgerStatus.SETTLED);
        entry.setCreatedAt(Instant.now());
        entry.setUpdatedAt(Instant.now());

        Page<LedgerEntry> page = new PageImpl<>(List.of(entry));
        when(ledgerEntryRepository.findAll(any(Specification.class), any(PageRequest.class))).thenReturn(page);

        Page<LedgerEntryResponse> result = ledgerService.findEntries(
                "EUR", LedgerStatus.SETTLED, "Global", null, null, PageRequest.of(0, 10));

        assertThat(result.getContent()).hasSize(1);
        assertThat(result.getContent().get(0).getInvoiceNumber()).isEqualTo("INV-FILTER-01");
    }
}
