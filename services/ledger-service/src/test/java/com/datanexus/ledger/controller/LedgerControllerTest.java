package com.datanexus.ledger.controller;

import com.datanexus.ledger.domain.LedgerStatus;
import com.datanexus.ledger.dto.CreateLedgerEntryRequest;
import com.datanexus.ledger.dto.LedgerEntryResponse;
import com.datanexus.ledger.dto.LedgerSummaryItem;
import com.datanexus.ledger.dto.LedgerSummaryResponse;
import com.datanexus.ledger.service.LedgerService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(LedgerController.class)
class LedgerControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private LedgerService ledgerService;

    @Test
    @DisplayName("POST /api/v1/ledger/entries creates entry returning 201 Created")
    void testCreateEntry() throws Exception {
        CreateLedgerEntryRequest request = new CreateLedgerEntryRequest();
        request.setInvoiceNumber("INV-REST-001");
        request.setVendorName("Nexus Systems");
        request.setCurrency("USD");
        request.setAmount(new BigDecimal("4500.0000"));
        request.setStatus(LedgerStatus.VALIDATED);
        request.setValidationScore(new BigDecimal("99.00"));

        UUID newId = UUID.randomUUID();
        LedgerEntryResponse response = new LedgerEntryResponse(
                newId, "INV-REST-001", "Nexus Systems", "USD",
                new BigDecimal("4500.0000"), LedgerStatus.VALIDATED,
                new BigDecimal("99.00"), "hash123", Instant.now(), Instant.now()
        );

        when(ledgerService.createEntry(any(CreateLedgerEntryRequest.class))).thenReturn(response);

        mockMvc.perform(post("/api/v1/ledger/entries")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(newId.toString()))
                .andExpect(jsonPath("$.invoiceNumber").value("INV-REST-001"))
                .andExpect(jsonPath("$.currency").value("USD"))
                .andExpect(jsonPath("$.amount").value(4500.0));
    }

    @Test
    @DisplayName("POST /api/v1/ledger/entries fails on invalid input returning 400 Bad Request")
    void testCreateEntryValidationFailure() throws Exception {
        CreateLedgerEntryRequest invalidReq = new CreateLedgerEntryRequest();
        invalidReq.setInvoiceNumber(""); // Blank
        invalidReq.setCurrency("TOOLONG"); // Invalid size

        mockMvc.perform(post("/api/v1/ledger/entries")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(invalidReq)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.validationErrors.invoiceNumber").exists());
    }

    @Test
    @DisplayName("GET /api/v1/ledger/entries returns paginated entries")
    void testGetEntries() throws Exception {
        LedgerEntryResponse response = new LedgerEntryResponse(
                UUID.randomUUID(), "INV-PAGED-1", "Alpha Logistics", "EUR",
                new BigDecimal("1200.00"), LedgerStatus.SETTLED,
                new BigDecimal("96.00"), "h", Instant.now(), Instant.now()
        );

        when(ledgerService.findEntries(any(), any(), any(), any(), any(), any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of(response)));

        mockMvc.perform(get("/api/v1/ledger/entries?currency=EUR&status=SETTLED"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].invoiceNumber").value("INV-PAGED-1"))
                .andExpect(jsonPath("$.content[0].currency").value("EUR"));
    }

    @Test
    @DisplayName("GET /api/v1/ledger/summary returns multi-currency summary rollup")
    void testGetSummary() throws Exception {
        LedgerSummaryResponse summary = new LedgerSummaryResponse(
                List.of(new LedgerSummaryItem("USD", LedgerStatus.SETTLED, new BigDecimal("10000.00"), 10L, 97.5)),
                10L, new BigDecimal("10000.00")
        );

        when(ledgerService.getSummary()).thenReturn(summary);

        mockMvc.perform(get("/api/v1/ledger/summary"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalCount").value(10))
                .andExpect(jsonPath("$.totalVolume").value(10000.00))
                .andExpect(jsonPath("$.summaries[0].currency").value("USD"));
    }
}
