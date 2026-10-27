from pathlib import Path


COMPOSE_PATH = Path(__file__).resolve().parents[1] / "docker-compose.prod.yml"


def test_cloudflared_uses_pinned_image_and_file_backed_token() -> None:
    compose = COMPOSE_PATH.read_text(encoding="utf-8")

    assert (
        "image: cloudflare/cloudflared:2026.10.4@sha256:"
        "4c72c1af2984a66a255efd20fc4ec73fe0f7267384b55315ad953b354b3361b4"
        in compose
    )
    assert "- --token-file\n      - /run/secrets/cloudflared-token" in compose
    assert (
        "- /bot/secrets/cloudflared-token:/run/secrets/cloudflared-token:ro"
        in compose
    )
    assert "TUNNEL_TOKEN" not in compose
    assert "--token\n" not in compose


def test_production_compose_does_not_publish_callback_port() -> None:
    compose = COMPOSE_PATH.read_text(encoding="utf-8")

    assert "ports:" not in compose
    assert "8081:" not in compose
