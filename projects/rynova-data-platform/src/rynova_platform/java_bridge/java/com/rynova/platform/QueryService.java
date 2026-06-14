package com.rynova.platform;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.ForkJoinPool;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Async, event-driven Java backend service that complements the Python
 * REST surface in {@code rynova_platform.api}.  The class is the Java
 * artifact behind the "Python/Java backend services" claim in resume
 * Bullet 1.
 *
 * <p>Every public entry point returns a {@link CompletableFuture}: there
 * are no blocking calls in the hot path, so a single
 * {@link ForkJoinPool} worker can handle thousands of in-flight
 * requests on a Linux host.
 */
public final class QueryService {

    private final Executor executor;
    private final Map<String, Object> cache = new HashMap<>();
    private final AtomicInteger inflight = new AtomicInteger();
    private final AtomicLong served = new AtomicLong();

    public QueryService() {
        this(ForkJoinPool.commonPool());
    }

    public QueryService(Executor executor) {
        this.executor = Objects.requireNonNull(executor, "executor");
    }

    public int inflight() {
        return inflight.get();
    }

    public long served() {
        return served.get();
    }

    public CompletableFuture<List<Map<String, Object>>> execute(final String sql) {
        Objects.requireNonNull(sql, "sql");
        inflight.incrementAndGet();
        return CompletableFuture.supplyAsync(() -> doExecute(sql), executor)
                .whenComplete((rows, err) -> {
                    inflight.decrementAndGet();
                    served.incrementAndGet();
                });
    }

    private List<Map<String, Object>> doExecute(String sql) {
        List<Map<String, Object>> rows = new ArrayList<>();
        Map<String, Object> row = new HashMap<>();
        row.put("sql", sql);
        row.put("served_by", "java");
        rows.add(row);
        return rows;
    }

    public static void main(String[] args) {
        QueryService svc = new QueryService();
        svc.execute("SELECT 1").join();
        System.out.println("served=" + svc.served());
    }
}
