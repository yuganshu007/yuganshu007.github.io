package com.rynova.platform;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Consumer;

/**
 * Tiny pub/sub for in-process events on the Java side of the platform.
 * Mirrors {@code rynova_platform.api.event_bus.AsyncEventBus}.
 */
public final class EventBus {

    private final Map<String, List<Consumer<Map<String, Object>>>> subscribers = new ConcurrentHashMap<>();
    private final AtomicLong delivered = new AtomicLong();

    public long delivered() {
        return delivered.get();
    }

    public void subscribe(String topic, Consumer<Map<String, Object>> handler) {
        subscribers.computeIfAbsent(topic, k -> new CopyOnWriteArrayList<>()).add(handler);
    }

    public int publish(String topic, Map<String, Object> payload) {
        List<Consumer<Map<String, Object>>> handlers = subscribers.get(topic);
        if (handlers == null) {
            return 0;
        }
        for (Consumer<Map<String, Object>> handler : handlers) {
            handler.accept(payload);
            delivered.incrementAndGet();
        }
        return handlers.size();
    }
}
