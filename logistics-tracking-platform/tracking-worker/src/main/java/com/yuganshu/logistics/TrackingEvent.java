package com.yuganshu.logistics;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.Set;

/** Immutable view of a tracking event read off the message queue. */
public final class TrackingEvent {
    private static final Set<String> VALID_TYPES = Set.of(
        "PICKUP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "EXCEPTION");

    public final String eventId;
    public final String shipmentId;
    public final String eventType;
    public final String location;
    public final String note;
    public final long ingestedAtMs;

    public TrackingEvent(String eventId, String shipmentId, String eventType,
                         String location, String note, long ingestedAtMs) {
        this.eventId = eventId;
        this.shipmentId = shipmentId;
        this.eventType = eventType;
        this.location = location;
        this.note = note;
        this.ingestedAtMs = ingestedAtMs;
    }

    public static TrackingEvent fromJson(JsonNode n) {
        return new TrackingEvent(
            text(n, "event_id"),
            text(n, "shipment_id"),
            text(n, "event_type"),
            text(n, "location"),
            n.hasNonNull("note") ? n.get("note").asText() : null,
            n.hasNonNull("ingested_at_ms") ? n.get("ingested_at_ms").asLong() : 0L);
    }

    private static String text(JsonNode n, String field) {
        return n.hasNonNull(field) ? n.get(field).asText() : null;
    }

    /** Second line of defense validation (the API validates first). */
    public boolean isValid() {
        return eventId != null && !eventId.isBlank()
            && shipmentId != null && !shipmentId.isBlank()
            && eventType != null && VALID_TYPES.contains(eventType)
            && location != null && !location.isBlank()
            && ingestedAtMs > 0;
    }
}
