package com.datanexus.ledger.dto;

import com.datanexus.ledger.domain.LedgerStatus;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import java.util.Map;

public class CreateLedgerEntryRequest {

    @NotBlank(message = "invoiceNumber is required")
    private String invoiceNumber;

    @NotBlank(message = "vendorName is required")
    private String vendorName;

    @NotBlank(message = "currency is required")
    @Size(min = 3, max = 3, message = "currency must be a 3-character ISO code")
    private String currency;

    @NotNull(message = "amount is required")
    @DecimalMin(value = "0.0001", message = "amount must be greater than zero")
    private BigDecimal amount;

    private LedgerStatus status = LedgerStatus.VALIDATED;

    @DecimalMin(value = "0.0", message = "validationScore must be at least 0.0")
    @DecimalMax(value = "100.0", message = "validationScore cannot exceed 100.0")
    private BigDecimal validationScore;

    private String sourceDocHash;

    private String actor = "fastapi-bridge";

    private Map<String, Object> metadata;

    public CreateLedgerEntryRequest() {
    }

    public CreateLedgerEntryRequest(String invoiceNumber, String vendorName, String currency,
                                    BigDecimal amount, LedgerStatus status, BigDecimal validationScore,
                                    String sourceDocHash, String actor, Map<String, Object> metadata) {
        this.invoiceNumber = invoiceNumber;
        this.vendorName = vendorName;
        this.currency = currency;
        this.amount = amount;
        this.status = status != null ? status : LedgerStatus.VALIDATED;
        this.validationScore = validationScore;
        this.sourceDocHash = sourceDocHash;
        this.actor = actor != null ? actor : "fastapi-bridge";
        this.metadata = metadata;
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

    public String getActor() {
        return actor;
    }

    public void setActor(String actor) {
        this.actor = actor;
    }

    public Map<String, Object> getMetadata() {
        return metadata;
    }

    public void setMetadata(Map<String, Object> metadata) {
        this.metadata = metadata;
    }
}
