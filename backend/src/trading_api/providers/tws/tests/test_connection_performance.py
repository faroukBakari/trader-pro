"""Performance tests for TWSConnection callback dispatch.

Performance Targets:
- Average callback dispatch latency: < 2 µs
- P99 callback dispatch latency: < 5 µs
- Zero-copy: Pass TWS objects by reference (no copying)
"""

import time

from trading_api.providers.tws.tws_connection import TWSConnection


class TestCallbackPerformance:
    """Performance validation for TWSConnection callback dispatch."""

    def test_callback_dispatch_latency(self) -> None:
        """Verify callback dispatch meets <2µs average, <5µs P99 target."""
        conn = TWSConnection()

        dispatch_times = []

        def measure_callback(data: object) -> None:
            """Minimal callback for performance measurement."""

        conn.callbacks[1] = measure_callback

        # Warm up (JIT, cache warming)
        for _ in range(100):
            conn.symbolSamples(1, [])

        # Measure 1000 dispatches
        for _ in range(1000):
            start = time.perf_counter()
            conn.symbolSamples(1, [])
            elapsed = (time.perf_counter() - start) * 1_000_000  # Convert to µs
            dispatch_times.append(elapsed)

        # Calculate statistics
        avg_latency = sum(dispatch_times) / len(dispatch_times)
        p99_latency = sorted(dispatch_times)[int(len(dispatch_times) * 0.99)]
        median_latency = sorted(dispatch_times)[len(dispatch_times) // 2]

        # Report results
        print("\nCallback Dispatch Performance:")
        print(f"  Average latency: {avg_latency:.2f}µs")
        print(f"  Median latency: {median_latency:.2f}µs")
        print(f"  P99 latency: {p99_latency:.2f}µs")

        # Validate targets
        assert avg_latency < 2.0, f"Average latency too high: {avg_latency:.2f}µs"
        assert p99_latency < 5.0, f"P99 latency too high: {p99_latency:.2f}µs"

    def test_zero_copy_dispatch(self) -> None:
        """Verify callback receives same object reference (zero-copy)."""
        conn = TWSConnection()

        received_object = None

        def callback(data: object) -> None:
            nonlocal received_object
            received_object = data

        conn.callbacks[1] = callback

        # Create test data
        test_data = [{"symbol": "AAPL", "exchange": "SMART"}]

        # Dispatch callback
        conn.symbolSamples(1, test_data)

        # Verify same object reference (not a copy)
        assert received_object is test_data, "Data was copied, not passed by reference"

    def test_multi_callback_dispatch_throughput(self) -> None:
        """Test throughput with multiple concurrent callbacks."""
        conn = TWSConnection()

        callback_count = 0

        def callback(data: object) -> None:
            nonlocal callback_count
            callback_count += 1

        # Register multiple request IDs
        num_requests = 100
        for req_id in range(1, num_requests + 1):
            conn.callbacks[req_id] = callback

        # Measure throughput
        start = time.perf_counter()

        # Simulate rapid callback dispatch
        for req_id in range(1, num_requests + 1):
            conn.symbolSamples(req_id, [])

        elapsed = time.perf_counter() - start
        throughput = num_requests / elapsed

        print("\nMulti-Callback Throughput:")
        print(f"  Dispatched {num_requests} callbacks in {elapsed*1000:.2f}ms")
        print(f"  Throughput: {throughput:.0f} callbacks/sec")

        # Verify all callbacks invoked
        assert callback_count == num_requests

        # Verify reasonable throughput (> 10k callbacks/sec)
        assert (
            throughput > 10_000
        ), f"Throughput too low: {throughput:.0f} callbacks/sec"

    def test_callback_dispatch_with_large_data(self) -> None:
        """Test dispatch performance with large data payloads (zero-copy benefit)."""
        conn = TWSConnection()

        received_data = None

        def callback(data: object) -> None:
            nonlocal received_data
            received_data = data

        conn.callbacks[1] = callback

        # Create large data payload (simulating many contract descriptions)
        large_payload = [
            {"symbol": f"SYM{i}", "exchange": "SMART"} for i in range(1000)
        ]

        # Measure dispatch with large payload
        dispatch_times = []
        for _ in range(100):
            start = time.perf_counter()
            conn.symbolSamples(1, large_payload)
            elapsed = (time.perf_counter() - start) * 1_000_000
            dispatch_times.append(elapsed)

        avg_latency = sum(dispatch_times) / len(dispatch_times)

        print("\nLarge Payload Performance (1000 items):")
        print(f"  Average latency: {avg_latency:.2f}µs")

        # Zero-copy should make payload size irrelevant
        # Latency should still be < 2µs (no copying)
        assert avg_latency < 2.0, (
            f"Large payload latency too high: {avg_latency:.2f}µs "
            "(suggests data copying instead of zero-copy)"
        )

        # Verify zero-copy (same reference)
        assert received_data is large_payload
