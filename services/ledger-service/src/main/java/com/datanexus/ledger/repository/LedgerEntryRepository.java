package com.datanexus.ledger.repository;

import com.datanexus.ledger.domain.LedgerEntry;
import com.datanexus.ledger.dto.LedgerSummaryItem;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface LedgerEntryRepository extends JpaRepository<LedgerEntry, UUID>, JpaSpecificationExecutor<LedgerEntry> {

    @Query("SELECT new com.datanexus.ledger.dto.LedgerSummaryItem(" +
           "e.currency, e.status, SUM(e.amount), COUNT(e.id), AVG(e.validationScore)) " +
           "FROM LedgerEntry e " +
           "GROUP BY e.currency, e.status " +
           "ORDER BY e.currency, e.status")
    List<LedgerSummaryItem> getMultiCurrencyRollup();
}
