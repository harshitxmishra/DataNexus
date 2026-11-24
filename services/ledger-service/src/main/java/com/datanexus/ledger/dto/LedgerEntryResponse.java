package com.datanexus.ledger.dto;

import com.datanexus.ledger.domain.LedgerEntry;
import com.datanexus.ledger.domain.LedgerStatus;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public class LedgerEntryResponse {
    private UUID id;
    private String invoiceNumber;
    private String vendorName;
    private String currency;
    private BigDecimal amount;
    private LedgerStatus status;
    private BigDecimal validationScore;
    private String sourceDocHash;
    private Instant createdAt;
    private Instant updatedAt;

    public LedgerEntryResponse() {
    }

    public LedgerEntryResponse(UUID id, String invoiceNumber, String vendorName, String currency,
                               BigDecimal amount, LedgerStatus status, BigDecimal validationScore,
                               String sourceDocHash, Instant createdAt, Instant updatedAt) {
        this.id = id;
        this.invoiceNumber = invoiceNumber;
        this.vendorName = vendorName;
        this.currency = currency;
        this.amount = amount;
        this.status = status;
        this.validationScore = validationScore;
        this.sourceDocHash = sourceDocHash;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }

    public static LedgerEntryResponse fromEntity(LedgerEntry entry) {
        return new LedgerEntryResponse(
                entry.getId(),
                entry.getInvoiceNumber(),
                entry.getVendorName(),
                entry.getCurrency(),
                entry.getAmount(),
                entry.getStatus(),
                entry.getValidationScore(),
                entry.getSourceDocHash(),
                entry.getCreatedAt(),
                entry.getUpdatedAt()
        );
    }

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public String getInvoiceNumber() {
        return invoiceNumber;
    }

    public void setInvoiceNumber(String invoiceNumber) {
        this.invoiceNumber = invoiceNumber;
    }

    public String getVendorName() {
        return vendorName;
    }

    public void setVendorName(String vendorName) {
        this.vendorName = vendorName;
    }

    public String getCurrency() {
        return currency;
    }

    public void setCurrency(String currency) {
        this.currency = currency;
    }

    public BigDecimal getAmount() {
        return amount;
    }

    public void setAmount(BigDecimal amount) {
        this.amount = amount;
    }

    public LedgerStatus getStatus() {
        return status;
    }

    public void setStatus(LedgerStatus status) {
        this.status = status;
    }

    public BigDecimal getValidationScore() {
        return validationScore;
    }

    public void setValidationScore(BigDecimal validationScore) {
        this.validationScore = validationScore;
    }

    public String getSourceDocHash() {
        return sourceDocHash;
    }

    public void setSourceDocHash(String sourceDocHash) {
        this.sourceDocHash = sourceDocHash;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(Instant updatedAt) {
        this.updatedAt = updatedAt;
    }
}
