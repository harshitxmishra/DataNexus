package com.datanexus.ledger.dto;

import com.datanexus.ledger.domain.LedgerStatus;
import java.math.BigDecimal;

public class LedgerSummaryItem {
    private String currency;
    private LedgerStatus status;
    private BigDecimal totalVolume;
    private Long count;
    private Double avgValidationScore;

    public LedgerSummaryItem() {
    }

    public LedgerSummaryItem(String currency, LedgerStatus status, BigDecimal totalVolume, Long count, Double avgValidationScore) {
        this.currency = currency;
        this.status = status;
        this.totalVolume = totalVolume != null ? totalVolume : BigDecimal.ZERO;
        this.count = count != null ? count : 0L;
        this.avgValidationScore = avgValidationScore != null ? avgValidationScore : 0.0;
    }

    public String getCurrency() {
        return currency;
    }

    public void setCurrency(String currency) {
        this.currency = currency;
    }

    public LedgerStatus getStatus() {
        return status;
    }

    public void setStatus(LedgerStatus status) {
        this.status = status;
    }

    public BigDecimal getTotalVolume() {
        return totalVolume;
    }

    public void setTotalVolume(BigDecimal totalVolume) {
        this.totalVolume = totalVolume;
    }

    public Long getCount() {
        return count;
    }

    public void setCount(Long count) {
        this.count = count;
    }

    public Double getAvgValidationScore() {
        return avgValidationScore;
    }

    public void setAvgValidationScore(Double avgValidationScore) {
        this.avgValidationScore = avgValidationScore;
    }
}
