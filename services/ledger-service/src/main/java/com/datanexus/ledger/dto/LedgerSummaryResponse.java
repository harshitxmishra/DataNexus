package com.datanexus.ledger.dto;

import java.math.BigDecimal;
import java.util.List;

public class LedgerSummaryResponse {
    private List<LedgerSummaryItem> summaries;
    private long totalCount;
    private BigDecimal totalVolume;

    public LedgerSummaryResponse() {
    }

    public LedgerSummaryResponse(List<LedgerSummaryItem> summaries, long totalCount, BigDecimal totalVolume) {
        this.summaries = summaries;
        this.totalCount = totalCount;
        this.totalVolume = totalVolume != null ? totalVolume : BigDecimal.ZERO;
    }

    public List<LedgerSummaryItem> getSummaries() {
        return summaries;
    }

    public void setSummaries(List<LedgerSummaryItem> summaries) {
        this.summaries = summaries;
    }

    public long getTotalCount() {
        return totalCount;
    }

    public void setTotalCount(long totalCount) {
        this.totalCount = totalCount;
    }

    public BigDecimal getTotalVolume() {
        return totalVolume;
    }

    public void setTotalVolume(BigDecimal totalVolume) {
        this.totalVolume = totalVolume;
    }
}
