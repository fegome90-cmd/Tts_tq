"""Tests for CLI - basic invocation tests."""

from unittest.mock import Mock, patch

from typer.testing import CliRunner

runner = CliRunner()


class TestCLICommands:
    """Tests for CLI commands - basic invocation."""

    def test_clone_command_help(self):
        """clone command should show help."""
        from tts_lab.cli import app

        result = runner.invoke(app, ["clone", "--help"])
        assert result.exit_code == 0

    def test_clone_help_shows_clone_defaults_and_controls(self):
        """clone command help should expose Base model and clone controls."""
        from tts_lab.cli import app

        result = runner.invoke(app, ["clone", "--help"])

        assert result.exit_code == 0
        assert "Qwen/Qwen3-TTS-12Hz-" in result.stdout
        assert "--language" in result.stdout
        assert "Spanish" in result.stdout
        assert "--embedding-only" in result.stdout
        assert "--seed" in result.stdout
        assert "--temperature" in result.stdout
        assert "--top-p" in result.stdout
        assert "--top-k" in result.stdout
        assert "--repetition-penalty" in result.stdout
        assert "--max-new-tokens" in result.stdout

    def test_clone_command_passes_defaults_to_client(self, tmp_path):
        """clone command should pass Base model and ICL Spanish defaults."""
        from tts_lab.cli import app
        from tts_lab.domain.entities import AudioResult

        reference_audio = tmp_path / "reference.wav"
        reference_audio.write_bytes(b"fake wav")
        output = tmp_path / "cloned.wav"

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.clone_voice.return_value = AudioResult(
            audio_data=b"wav",
            sample_rate=24000,
            duration_seconds=1.0,
        )

        with (
            patch("tts_lab.cli.QwenTTSClient", return_value=mock_client) as client_class,
            patch("tts_lab.cli.FileAudioRepository") as repo_class,
        ):
            repo_class.return_value.save.return_value = str(output)
            result = runner.invoke(
                app,
                [
                    "clone",
                    str(reference_audio),
                    "--ref-text",
                    "Reference text",
                    "--text",
                    "Hola mundo",
                    "--output",
                    str(output),
                ],
            )

        assert result.exit_code == 0
        client_class.assert_called_once_with(
            model_path="Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            device="mps",
        )
        profile = mock_client.clone_voice.call_args.args[0]
        assert profile.reference_audio_path == str(reference_audio)
        assert profile.reference_text == "Reference text"
        assert mock_client.clone_voice.call_args.args[1] == "Hola mundo"
        assert mock_client.clone_voice.call_args.kwargs == {
            "language": "Spanish",
            "x_vector_only_mode": False,
            "seed": 42,
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 50,
            "repetition_penalty": 1.2,
            "max_new_tokens": 512,
        }
        repo_class.assert_called_once_with(output_dir=str(output.parent))
        repo_class.return_value.save.assert_called_once_with(
            mock_client.clone_voice.return_value, output.name
        )

    def test_clone_command_passes_custom_controls_to_client(self, tmp_path):
        """clone command should pass custom clone controls."""
        from tts_lab.cli import app
        from tts_lab.domain.entities import AudioResult

        reference_audio = tmp_path / "reference.wav"
        reference_audio.write_bytes(b"fake wav")
        output = tmp_path / "cloned.wav"

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.clone_voice.return_value = AudioResult(
            audio_data=b"wav",
            sample_rate=24000,
            duration_seconds=1.0,
        )

        with (
            patch("tts_lab.cli.QwenTTSClient", return_value=mock_client),
            patch("tts_lab.cli.FileAudioRepository"),
        ):
            result = runner.invoke(
                app,
                [
                    "clone",
                    str(reference_audio),
                    "--ref-text",
                    "Reference text",
                    "--text",
                    "Hola mundo",
                    "--output",
                    str(output),
                    "--model",
                    "custom-model",
                    "--device",
                    "cpu",
                    "--language",
                    "English",
                    "--embedding-only",
                    "--seed",
                    "123",
                    "--temperature",
                    "0.7",
                    "--top-p",
                    "0.9",
                    "--top-k",
                    "40",
                    "--repetition-penalty",
                    "1.05",
                    "--max-new-tokens",
                    "1024",
                ],
            )

        assert result.exit_code == 0
        assert mock_client.clone_voice.call_args.kwargs == {
            "language": "English",
            "x_vector_only_mode": True,
            "seed": 123,
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "repetition_penalty": 1.05,
            "max_new_tokens": 1024,
        }

    def test_generate_command_help(self):
        """generate command should show help."""
        from tts_lab.cli import app

        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0

    def test_app_help(self):
        """app should show help with all commands."""
        from tts_lab.cli import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "clone" in result.stdout
        assert "generate" in result.stdout

    def test_clone_command_refused_when_provider_is_inworld(self, tmp_path):
        """Clone command refuses when TTS_PROVIDER=inworld (guard fires pre-client).

        The CLI guard at ``tts_lab/cli.py`` checks ``config.provider == 'inworld'``
        BEFORE constructing any TTS client (so no model is loaded and no network
        is touched). It prints an Inworld-specific message and exits 1. This
        test locks that guard so a future refactor can't accidentally route
        Inworld into the Qwen cloning path or vice-versa.
        """
        from tts_lab.cli import app

        reference_audio = tmp_path / "reference.wav"
        reference_audio.write_bytes(b"fake wav")

        with runner.isolated_filesystem():
            # Set TTS_PROVIDER=inworld for just this invocation.
            import os

            old = os.environ.get("TTS_PROVIDER")
            os.environ["TTS_PROVIDER"] = "inworld"
            try:
                result = runner.invoke(
                    app,
                    [
                        "clone",
                        str(reference_audio),
                        "--ref-text",
                        "Reference text",
                        "--text",
                        "Hola mundo",
                    ],
                )
            finally:
                if old is None:
                    os.environ.pop("TTS_PROVIDER", None)
                else:
                    os.environ["TTS_PROVIDER"] = old

        # Guard fires: exit 1, message mentions Inworld + not-supported.
        assert result.exit_code == 1
        combined = (result.stdout or "") + (result.output or "")
        assert "Inworld" in combined
        assert "not supported" in combined.lower()
