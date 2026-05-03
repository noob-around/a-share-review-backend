def test_create_and_list_operations(client, auth_headers):
    payload = {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "trade_date": "2026-05-03",
        "action": "买入",
        "selection_reason": "趋势向上。",
        "buy_reason": "回踩企稳。",
        "price": "1680.50",
        "quantity": "100",
        "profit_loss": "100",
        "lessons": "避免追高。",
    }

    response = client.post("/api/operations", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["id"] == 1
    assert created["stock_code"] == "600519"
    assert created["action"] == "买入"

    response = client.get("/api/operations?start_date=2026-05-01&end_date=2026-05-04", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["stock_name"] == "贵州茅台"


def test_api_requires_token_when_configured(client):
    response = client.get("/api/operations")
    assert response.status_code == 401
