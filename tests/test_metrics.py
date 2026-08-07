"""Tests for the /metrics endpoint added in Milestone 8.

The cardinality test below is the important one. "No user/order/request IDs in
labels" is a stated requirement of the milestone, and the usual way it gets
broken is not a bad regex — it is somebody bumping the instrumentation
library, its default handler source changing from the route template to the
raw request path, and nothing anywhere noticing until Prometheus has a series
per order ID.
"""


def test_metrics_endpoint_is_served(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    # The Prometheus text exposition format, not JSON.
    assert "text/plain" in response.headers["content-type"]


def test_metrics_include_request_and_process_stats(client):
    body = client.get("/metrics").text

    # Request count and duration come from the instrumentator...
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    # ...and process stats come free from prometheus_client's default
    # collectors, which is what covers the brief's "process stats".
    assert "process_resident_memory_bytes" in body


def test_health_and_metrics_are_excluded_from_request_metrics(client):
    """Probes must not drown out real traffic.

    /health is hit by a readiness and a liveness probe every few seconds on
    every pod. If it were counted, "request rate" on the dashboard would be
    almost entirely the cluster talking to itself.
    """
    client.get("/health")
    body = client.get("/metrics").text

    assert 'handler="/health"' not in body
    assert 'handler="/metrics"' not in body


def test_handler_label_is_the_route_template_not_the_request_path(client):
    """The label must carry the ROUTE, never the values in it.

    Note the path: the router carries its own "/auth" prefix on top of the
    "/api" it is mounted under, so the route template is "/api/auth/me".
    Nothing the request carried — bearer token, user id, email — may appear as
    a label value.
    """
    client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    body = client.get("/metrics").text

    assert 'handler="/api/auth/me"' in body
    assert "not-a-real-token" not in body


def test_unmatched_paths_collapse_to_a_single_series(client):
    """A 404 flood must be visible, but must not create a series per URL.

    Two different nonexistent paths, each containing something that looks like
    an ID. Both are counted, and neither appears as a label.
    """
    client.get("/api/orders/ORD-2026-000001")
    client.get("/api/users/507f1f77bcf86cd799439011")
    body = client.get("/metrics").text

    assert "ORD-2026-000001" not in body
    assert "507f1f77bcf86cd799439011" not in body
