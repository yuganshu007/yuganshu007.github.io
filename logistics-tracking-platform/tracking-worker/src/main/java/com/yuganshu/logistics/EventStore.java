package com.yuganshu.logistics;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.sql.Statement;

/** see {@link #ensureSchema(String)} for idempotent schema creation. */

/**
 * Per-thread SQLite writer. WAL mode lets every worker thread (and the Python
 * reader) share a single database file concurrently. The {@code ON CONFLICT}
 * upsert keeps retries idempotent.
 */
public final class EventStore implements AutoCloseable {
    private final Connection conn;
    private final PreparedStatement upsertEvent;
    private final PreparedStatement updateShipment;

    public EventStore(String dbPath) throws SQLException {
        this.conn = DriverManager.getConnection("jdbc:sqlite:" + dbPath);
        try (Statement st = conn.createStatement()) {
            st.execute("PRAGMA journal_mode=WAL;");
            st.execute("PRAGMA synchronous=NORMAL;");
            st.execute("PRAGMA busy_timeout=30000;");
        }
        this.upsertEvent = conn.prepareStatement(
            "INSERT INTO tracking_events (event_id, shipment_id, event_type, location, " +
            "note, ingested_at_ms, processed_at_ms, attempts, outcome) " +
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) " +
            "ON CONFLICT(event_id) DO UPDATE SET processed_at_ms=excluded.processed_at_ms, " +
            "attempts=excluded.attempts, outcome=excluded.outcome");
        // Advance status monotonically by event ingest time so the latest event
        // wins regardless of which worker thread persists first.
        this.updateShipment = conn.prepareStatement(
            "UPDATE shipments SET status=?, updated_at_ms=? WHERE id=? AND ? >= updated_at_ms");
    }

    public synchronized void persist(TrackingEvent e, long processedAtMs, int attempts,
                                     String outcome) throws SQLException {
        upsertEvent.setString(1, e.eventId);
        upsertEvent.setString(2, e.shipmentId);
        upsertEvent.setString(3, e.eventType);
        upsertEvent.setString(4, e.location);
        upsertEvent.setString(5, e.note);
        upsertEvent.setLong(6, e.ingestedAtMs);
        upsertEvent.setLong(7, processedAtMs);
        upsertEvent.setInt(8, attempts);
        upsertEvent.setString(9, outcome);
        upsertEvent.executeUpdate();

        if ("OK".equals(outcome)) {
            updateShipment.setString(1, e.eventType);
            updateShipment.setLong(2, e.ingestedAtMs);
            updateShipment.setString(3, e.shipmentId);
            updateShipment.setLong(4, e.ingestedAtMs);
            updateShipment.executeUpdate();
        }
    }

    @Override
    public void close() throws SQLException {
        conn.close();
    }

    /**
     * Idempotently creates the shared schema (tables + indexes) so the worker is
     * resilient to startup ordering relative to the Python ingest service. Mirrors
     * the schema in {@code ingest-service/app/db.py}.
     */
    public static void ensureSchema(String dbPath) throws SQLException {
        try (Connection c = DriverManager.getConnection("jdbc:sqlite:" + dbPath);
             Statement st = c.createStatement()) {
            st.execute("PRAGMA journal_mode=WAL;");
            st.execute("PRAGMA busy_timeout=30000;");
            st.execute("CREATE TABLE IF NOT EXISTS shipments (" +
                "id TEXT PRIMARY KEY, origin TEXT NOT NULL, destination TEXT NOT NULL, " +
                "carrier TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'CREATED', " +
                "created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL)");
            st.execute("CREATE TABLE IF NOT EXISTS tracking_events (" +
                "event_id TEXT PRIMARY KEY, shipment_id TEXT NOT NULL, event_type TEXT NOT NULL, " +
                "location TEXT NOT NULL, note TEXT, ingested_at_ms INTEGER NOT NULL, " +
                "processed_at_ms INTEGER, attempts INTEGER NOT NULL DEFAULT 0, " +
                "outcome TEXT NOT NULL DEFAULT 'PENDING')");
            st.execute("CREATE INDEX IF NOT EXISTS idx_events_shipment " +
                "ON tracking_events (shipment_id, ingested_at_ms DESC)");
            st.execute("CREATE INDEX IF NOT EXISTS idx_events_outcome ON tracking_events (outcome)");
            st.execute("CREATE INDEX IF NOT EXISTS idx_shipments_status ON shipments (status)");
        }
    }
}
