import socket

from database import as_database_connection_error


def test_dns_error_is_converted_to_database_connection_error() -> None:
    error = socket.gaierror(-2, "Name or service not known")

    converted = as_database_connection_error(error)

    assert converted is not None
    assert "Supabaseプロジェクトが停止している可能性があります" in converted.message


def test_dns_error_is_found_in_exception_chain() -> None:
    dns_error = socket.gaierror(-2, "Name or service not known")
    try:
        raise RuntimeError("connection failed") from dns_error
    except RuntimeError as error:
        converted = as_database_connection_error(error)

    assert converted is not None


def test_unrelated_error_is_not_converted() -> None:
    assert as_database_connection_error(ValueError("invalid input")) is None
