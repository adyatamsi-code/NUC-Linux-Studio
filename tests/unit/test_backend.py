import pytest
from pathlib import Path
from unittest.mock import mock_open
from backend.core import read_text, write_text, BackendError

class TestBackendCore:

    def test_read_text_success(self, mocker):
        m_open = mocker.patch("pathlib.Path.read_text", return_value=" test_value \n")

        path = Path("/fake/path")
        result = read_text(path)

        m_open.assert_called_once_with(encoding="utf-8")
        assert result == "test_value"

    def test_write_text_direct_success(self, mocker):
        # We need to mock os.access to return True so it doesn't try to elevate
        mocker.patch("os.access", return_value=True)
        m_exists = mocker.patch("pathlib.Path.exists", return_value=True)
        m_write = mocker.patch("pathlib.Path.write_text")

        path = Path("/fake/path")
        write_text(path, "test_data")

        m_write.assert_called_once_with("test_data", encoding="utf-8")

    def test_write_text_elevation_required_success(self, mocker):
        # Mock that we don't have write access
        mocker.patch("os.access", return_value=False)
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("shutil.which", return_value="/usr/bin/pkexec")

        # Mock successful subprocess run
        m_run = mocker.patch("subprocess.run")
        m_run.return_value.returncode = 0
        m_run.return_value.stderr = ""

        path = Path("/fake/path")
        write_text(path, "test_data")

        # The script should be formatted safely with printf
        m_run.assert_called_once()
        args = m_run.call_args[0][0]
        assert args[0] == "pkexec"
        assert args[1] == "sh"
        assert args[2] == "-c"
        assert "printf '%s' 'test_data' > '/fake/path'" in args[3]

    def test_write_text_elevation_fails(self, mocker):
        mocker.patch("os.access", return_value=False)
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("shutil.which", return_value="/usr/bin/pkexec")

        m_run = mocker.patch("subprocess.run")
        m_run.return_value.returncode = 1
        m_run.return_value.stderr = "Authentication failed"

        path = Path("/fake/path")
        with pytest.raises(BackendError, match="Elevation.*failed"):
            write_text(path, "test_data")
