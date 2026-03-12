"""CLI scripts for TTS Lab.

Provides command-line interface for voice cloning and speech generation.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from tts_lab.application.dto import GenerateSpeechRequest
from tts_lab.application.use_cases import GenerateSpeechUseCase
from tts_lab.domain.entities import VoiceProfile
from tts_lab.infrastructure.config import TTSConfig
from tts_lab.infrastructure.file_storage import FileAudioRepository
from tts_lab.infrastructure.qwen_client import QwenTTSClient

console = Console()

# Single app with multiple commands
app = typer.Typer(help="TTS Lab - Voice Cloning Laboratory")


@app.command("clone")
def clone_voice(
    reference_audio: Path = typer.Argument(..., help="Path to reference audio file"),
    reference_text: str = typer.Option(..., "--ref-text", "-r", help="Transcription of reference audio"),
    text: str = typer.Option(..., "--text", "-t", help="Text to speak with cloned voice"),
    output: Path = typer.Option(Path("output/cloned.wav"), "--output", "-o", help="Output path"),
    model_path: str = typer.Option(
        "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "--model",
        "-m",
        help="HuggingFace model ID or local path",
    ),
    device: str = typer.Option("mps", "--device", "-d", help="Device (mps, cuda, cpu)"),
):
    """Clone voice from reference audio and generate speech.

    Example:
        tts clone reference.wav -r "This is my reference text." -t "Hello world!" -o output.wav
    """
    config = TTSConfig(model_path=model_path, device=device, output_dir=str(output.parent))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Loading model and cloning voice...", total=None)

        try:
            with QwenTTSClient(model_path=config.model_path, device=config.device) as client:
                profile = VoiceProfile(
                    name="cloned",
                    reference_audio_path=str(reference_audio),
                    reference_text=reference_text,
                )

                audio = client.clone_voice(profile, text)

                repo = FileAudioRepository(output_dir=str(output.parent))
                repo.save(audio, output.name)

            progress.update(task, completed=True)
            console.print(f"[green]✓[/green] Audio saved to: {output}")
            console.print(f"  Duration: {audio.duration_seconds:.2f}s")

        except Exception as e:
            console.print(f"[red]✗ Error:[/red] {e}")
            raise typer.Exit(code=1) from None


@app.command("generate")
def generate_speech(
    text: str = typer.Argument(..., help="Text to convert to speech"),
    output: Path = typer.Option(Path("output/speech.wav"), "--output", "-o", help="Output path"),
    language: str = typer.Option(
        "Auto", "--language", "-l", help="Language (Spanish, English, Auto)"
    ),
    speaker: str | None = typer.Option(None, "--speaker", "-s", help="Speaker name"),
    instruct: str | None = typer.Option(
        None, "--instruct", "-i", help="Voice style instructions"
    ),
    model_path: str = typer.Option(
        "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "--model",
        "-m",
        help="HuggingFace model ID or local path",
    ),
    device: str = typer.Option("mps", "--device", "-d", help="Device (mps, cuda, cpu)"),
):
    """Generate speech from text using preset voices.

    Example:
        tts generate "Hello world!" -l English -s Serena -o output.wav
    """
    config = TTSConfig(model_path=model_path, device=device, output_dir=str(output.parent))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating speech...", total=None)

        try:
            with QwenTTSClient(model_path=config.model_path, device=config.device) as client:
                repo = FileAudioRepository(output_dir=str(output.parent))
                use_case = GenerateSpeechUseCase(tts_client=client, audio_repo=repo)

                request = GenerateSpeechRequest(
                    text=text,
                    language=language,
                )

                response = use_case.execute(request)

            progress.update(task, completed=True)
            console.print(f"[green]✓[/green] Audio saved to: {response.audio_path}")
            console.print(f"  Duration: {response.duration_seconds:.2f}s")

        except Exception as e:
            console.print(f"[red]✗ Error:[/red] {e}")
            raise typer.Exit(code=1) from None


# Entry points for pyproject.toml
def run_clone() -> None:
    """Entry point for tts-clone command."""
    typer.run(clone_voice)


def run_generate() -> None:
    """Entry point for tts-generate command."""
    typer.run(generate_speech)


def run_app() -> None:
    """Entry point for tts command with subcommands."""
    app()


if __name__ == "__main__":
    app()
