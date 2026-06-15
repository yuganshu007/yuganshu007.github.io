package com.yuganshu.logistics;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import redis.clients.jedis.Jedis;
import redis.clients.jedis.StreamEntryID;
import redis.clients.jedis.params.XAddParams;
import redis.clients.jedis.params.XReadGroupParams;
import redis.clients.jedis.resps.StreamEntry;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Event-driven tracking worker (the "background workers" half of the pipeline).
 *
 * <p>A pool of consumer threads reads from a Redis Streams consumer group
 * ({@code >} = undelivered entries), validates each event, simulates the
 * downstream logistics call, retries transient failures with backoff and routes
 * poison messages to a dead-letter queue. Successful events are persisted to the
 * shared SQLite store with their processing timestamp so SLA compliance can be
 * measured end to end.
 */
public final class Worker {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final AtomicBoolean RUNNING = new AtomicBoolean(true);
    private static final AtomicLong PROCESSED = new AtomicLong();
    private static final AtomicLong RETRIED = new AtomicLong();
    private static final AtomicLong DLQ = new AtomicLong();

    public static void main(String[] args) throws Exception {
        Config cfg = Config.load();
        // Ensure JDBC driver + database schema exist before any thread starts.
        Class.forName("org.sqlite.JDBC");
        EventStore.ensureSchema(cfg.dbPath);

        try (Jedis admin = new Jedis(cfg.redisHost, cfg.redisPort)) {
            try {
                admin.xgroupCreate(cfg.streamKey, cfg.group, new StreamEntryID(), true);
            } catch (Exception e) {
                // BUSYGROUP -> the group already exists, which is fine.
                if (!String.valueOf(e.getMessage()).contains("BUSYGROUP")) {
                    throw e;
                }
            }
        }

        Runtime.getRuntime().addShutdownHook(new Thread(() -> RUNNING.set(false)));

        System.out.printf(
            "[worker] starting threads=%d stream=%s group=%s downstreamMs=%d failRate=%.2f maxAttempts=%d backoffMs=%d%n",
            cfg.workerThreads, cfg.streamKey, cfg.group, cfg.downstreamMs,
            cfg.transientFailRate, cfg.maxAttempts, cfg.backoffMs);

        Thread[] threads = new Thread[cfg.workerThreads];
        for (int i = 0; i < cfg.workerThreads; i++) {
            final String consumer = cfg.consumerPrefix + "-" + i;
            threads[i] = new Thread(() -> runConsumer(cfg, consumer), consumer);
            threads[i].start();
        }

        // Lightweight throughput reporter.
        Thread reporter = new Thread(() -> {
            long last = 0;
            while (RUNNING.get()) {
                try {
                    Thread.sleep(2000);
                } catch (InterruptedException e) {
                    break;
                }
                long now = PROCESSED.get();
                System.out.printf("[worker] processed=%d (+%d) retried=%d dlq=%d%n",
                    now, now - last, RETRIED.get(), DLQ.get());
                last = now;
            }
        }, "reporter");
        reporter.setDaemon(true);
        reporter.start();

        for (Thread t : threads) {
            t.join();
        }
    }

    private static void runConsumer(Config cfg, String consumer) {
        Map<String, StreamEntryID> streams = new HashMap<>();
        streams.put(cfg.streamKey, StreamEntryID.XREADGROUP_UNDELIVERED_ENTRY);
        XReadGroupParams params = XReadGroupParams.xReadGroupParams()
            .count(cfg.batchCount)
            .block(cfg.blockMs);

        try (Jedis jedis = new Jedis(cfg.redisHost, cfg.redisPort);
             EventStore store = new EventStore(cfg.dbPath)) {
            while (RUNNING.get()) {
                List<Map.Entry<String, List<StreamEntry>>> resp =
                    jedis.xreadGroup(cfg.group, consumer, params, streams);
                if (resp == null || resp.isEmpty()) {
                    continue;
                }
                for (Map.Entry<String, List<StreamEntry>> stream : resp) {
                    for (StreamEntry entry : stream.getValue()) {
                        handle(cfg, jedis, store, entry);
                        jedis.xack(cfg.streamKey, cfg.group, entry.getID());
                    }
                }
            }
        } catch (Exception e) {
            System.err.printf("[worker:%s] fatal: %s%n", consumer, e);
        }
    }

    private static void handle(Config cfg, Jedis jedis, EventStore store, StreamEntry entry) {
        String raw = entry.getFields().get("data");
        TrackingEvent event;
        try {
            JsonNode node = MAPPER.readTree(raw);
            event = TrackingEvent.fromJson(node);
        } catch (Exception parseError) {
            deadLetter(cfg, jedis, raw, "UNPARSEABLE");
            return;
        }

        if (!event.isValid()) {
            safePersist(store, event, System.currentTimeMillis(), 1, "INVALID");
            deadLetter(cfg, jedis, raw, "VALIDATION_FAILED");
            DLQ.incrementAndGet();
            return;
        }

        // Retry transient downstream failures with linear backoff; this is what
        // keeps SLA breaches down versus the no-retry baseline.
        for (int attempt = 1; attempt <= cfg.maxAttempts; attempt++) {
            try {
                callDownstream(cfg);
                safePersist(store, event, System.currentTimeMillis(), attempt, "OK");
                PROCESSED.incrementAndGet();
                return;
            } catch (TransientException te) {
                if (attempt == cfg.maxAttempts) {
                    safePersist(store, event, System.currentTimeMillis(), attempt, "FAILED");
                    deadLetter(cfg, jedis, raw, "RETRIES_EXHAUSTED");
                    DLQ.incrementAndGet();
                    return;
                }
                RETRIED.incrementAndGet();
                sleep((long) cfg.backoffMs * attempt);
            }
        }
    }

    private static void callDownstream(Config cfg) throws TransientException {
        sleep(cfg.downstreamMs);
        if (ThreadLocalRandom.current().nextDouble() < cfg.transientFailRate) {
            throw new TransientException();
        }
    }

    private static void safePersist(EventStore store, TrackingEvent e, long ts, int attempts,
                                    String outcome) {
        try {
            store.persist(e, ts, attempts, outcome);
        } catch (Exception ex) {
            System.err.printf("[worker] persist failed for %s: %s%n", e.eventId, ex);
        }
    }

    private static void deadLetter(Config cfg, Jedis jedis, String raw, String reason) {
        Map<String, String> fields = new HashMap<>();
        fields.put("data", raw == null ? "" : raw);
        fields.put("reason", reason);
        jedis.xadd(cfg.dlqKey, XAddParams.xAddParams(), fields);
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static final class TransientException extends Exception {
        TransientException() {
            super("transient downstream failure");
        }
    }
}
