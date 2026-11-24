package com.datanexus.ledger;

import com.datanexus.ledger.domain.AuditEvent;
import com.datanexus.ledger.domain.LedgerStatus;
import com.datanexus.ledger.dto.CreateLedgerEntryRequest;
import com.datanexus.ledger.dto.LedgerEntryResponse;
import com.datanexus.ledger.dto.LedgerSummaryResponse;
import com.datanexus.ledger.repository.AuditEventRepository;
import com.datanexus.ledger.repository.LedgerEntryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.*;
import org.springframework.test.context.ActiveProfiles;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
public class LedgerIntegrationTest {

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private LedgerEntryRepository ledgerEntryRepository;

    @Autowired
    private AuditEventRepository auditEventRepository;

    @BeforeEach
    void cleanDatabase() {
        auditEventRepository.deleteAll();
        ledgerEntryRepository.deleteAll();
    }

    @Test
    @DisplayName("End-to-end: Ingest entries across currencies, verify audit trail, and verify summary rollup")
    void testEndToEndIngestionAndRollup() {
        // 1. Ingest entry 1: USD Settled
        CreateLedgerEntryRequest req1 = new CreateLedgerEntryRequest();
        req1.setInvoiceNumber("INV-2026-USD-1");
        req1.setVendorName("Global Freight");
        req1.setCurrency("USD");
        req1.setAmount(new BigDecimal("1500.0000"));
        req1.setStatus(LedgerStatus.SETTLED);
        req1.setValidationScore(new BigDecimal("98.50"));
        req1.setActor("integration-tester");
        req1.setMetadata(Map.of("tenantId", "tenant-100"));

        ResponseEntity<LedgerEntryResponse> res1 = restTemplate.postForEntity(
                "/api/v1/ledger/entries", req1, LedgerEntryResponse.class);
        assertThat(res1.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(res1.getBody()).isNotNull();
        UUID id1 = res1.getBody().getId();
        assertThat(id1).isNotNull();

        // Verify audit event persisted atomically
        List<AuditEvent> audits1 = auditEventRepository.findByLedgerEntryIdOrderByCreatedAtDesc(id1);
        assertThat(audits1).hasSize(1);
        assertThat(audits1.get(0).getEventType()).isEqualTo("INVOICE_VALIDATED_INGESTION");
        assertThat(audits1.get(0).getActor()).isEqualTo("integration-tester");
        assertThat(audits1.get(0).getPayload()).contains("INV-2026-USD-1");

        // 2. Ingest entry 2: EUR Validated
        CreateLedgerEntryRequest req2 = new CreateLedgerEntryRequest();
        req2.setInvoiceNumber("INV-2026-EUR-1");
        req2.setVendorName("Continental Tech");
        req2.setCurrency("EUR");
        req2.setAmount(new BigDecimal("2500.0000"));
        req2.setStatus(LedgerStatus.VALIDATED);
        req2.setValidationScore(new BigDecimal("95.00"));
        req2.setActor("integration-tester");

        ResponseEntity<LedgerEntryResponse> res2 = restTemplate.postForEntity(
                "/api/v1/ledger/entries", req2, LedgerEntryResponse.class);
        assertThat(res2.getStatusCode()).isEqualTo(HttpStatus.CREATED);

        // 3. Query Summary Rollup
        ResponseEntity<LedgerSummaryResponse> summaryRes = restTemplate.getForEntity(
                "/api/v1/ledger/summary", LedgerSummaryResponse.class);
        assertThat(summaryRes.getStatusCode()).isEqualTo(HttpStatus.OK);
        LedgerSummaryResponse summary = summaryRes.getBody();
        assertThat(summary).isNotNull();
        assertThat(summary.getTotalCount()).isEqualTo(2);
        assertThat(summary.getTotalVolume()).isEqualByComparingTo(new BigDecimal("4000.0000"));
        assertThat(summary.getSummaries()).hasSize(2);

        // 4. Verify Actuator health
        ResponseEntity<String> healthRes = restTemplate.getForEntity("/actuator/health", String.class);
        assertThat(healthRes.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(healthRes.getBody()).contains("UP");
    }
}
