package com.yuganshu.logistics;

/**
 * Worker configuration, driven entirely by environment variables so the
 * benchmark harness can reshape the deployment (thread count, retry policy,
 * injected failure rate, ...) without recompiling.
 */
public final class Config {
    public final String redisHost;
    public final int redisPort;
    public final String streamKey;
    public final String dlqKey;
    public final String group;
    // "tuned" -> consume <stream>.high before <stream>.normal; "fifo" -> single lane.
    public final String routingMode;
    public final String consumerPrefix;
    public final String dbPath;

    public final int workerThreads;
    public final int downstreamMs;
    public final double transientFailRate;
    public final int maxAttempts;
    public final int backoffMs;
    public final int slaMs;
    public final int batchCount;
    public final int blockMs;

    private Config() {
        this.redisHost = env("REDIS_HOST", "localhost");
        this.redisPort = Integer.parseInt(env("REDIS_PORT", "6379"));
        this.streamKey = env("STREAM_KEY", "logistics.events");
        this.dlqKey = env("DLQ_KEY", "logistics.events.dlq");
        this.group = env("CONSUMER_GROUP", "tracking-workers");
        this.routingMode = env("ROUTING_MODE", "tuned");
        this.consumerPrefix = env("CONSUMER_PREFIX", "worker");
        this.dbPath = env("DB_PATH", "../data/logistics.db");

        this.workerThreads = Integer.parseInt(env("WORKER_THREADS", "8"));
        this.downstreamMs = Integer.parseInt(env("DOWNSTREAM_MS", "22"));
        this.transientFailRate = Double.parseDouble(env("TRANSIENT_FAIL_RATE", "0.0"));
        this.maxAttempts = Integer.parseInt(env("MAX_ATTEMPTS", "5"));
        this.backoffMs = Integer.parseInt(env("BACKOFF_MS", "40"));
        this.slaMs = Integer.parseInt(env("SLA_MS", "750"));
        this.batchCount = Integer.parseInt(env("BATCH_COUNT", "32"));
        this.blockMs = Integer.parseInt(env("BLOCK_MS", "2000"));
    }

    public static Config load() {
        return new Config();
    }

    /** Lanes this worker consumes, ordered high-priority first. */
    public java.util.List<String> lanes() {
        if ("tuned".equals(routingMode)) {
            return java.util.List.of(streamKey + ".high", streamKey + ".normal");
        }
        return java.util.List.of(streamKey + ".normal");
    }

    private static String env(String key, String def) {
        String v = System.getenv(key);
        return (v == null || v.isBlank()) ? def : v;
    }
}
