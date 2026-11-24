package com.datanexus.ledger.repository;

import com.datanexus.ledger.domain.AuditEvent;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface AuditEventRepository extends JpaRepository<AuditEvent, Long> {

    List<AuditEvent> findByLedgerEntryIdOrderByCreatedAtDesc(UUID ledgerEntryId);
}
