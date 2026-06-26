"""CLI scripts for TTS Lab.

Provides command-line interface for voice cloning and speech generation.
"""

import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from tts_lab.application.dto import GenerateSpeechRequest, Language
from tts_lab.application.use_cases import GenerateSpeechUseCase
from tts_lab.domain.entities import (
    GenerationFailure,
    GenerationSuccess,
    VoiceProfile,
)
from tts_lab.infrastructure.config import TTSConfig
from tts_lab.infrastructure.file_storage import FileAudioRepository
from tts_lab.infrastructure.qwen_client import (
    DEFAULT_CLONE_LANGUAGE,
    DEFAULT_CLONE_MAX_NEW_TOKENS,
    DEFAULT_CLONE_REPETITION_PENALTY,
    DEFAULT_CLONE_SEED,
    DEFAULT_CLONE_TEMPERATURE,
    DEFAULT_CLONE_TOP_K,
    DEFAULT_CLONE_TOP_P,
    QwenTTSClient,
)
from tts_lab.infrastructure.tts_provider import create_tts_client

console = Console()

# Single app with multiple commands
app = typer.Typer(help="TTS Lab - Voice Cloning Laboratory")


def _provider_from_env() -> str:
    """Read TTS_PROVIDER from env (default 'qwen').

    Tiny helper so CLI commands that build an explicit :class:`TTSConfig`
    still honor the active provider for guards/switching without duplicating
    the env-read logic (config is the single owner otherwise).
    """
    return os.getenv("TTS_PROVIDER", "qwen")


@app.command("clone")
def clone_voice(
    reference_audio: Annotated[Path, typer.Argument(help="Path to reference audio file")],
    reference_text: Annotated[
        str, typer.Option("--ref-text", "-r", help="Transcription of reference audio")
    ],
    text: Annotated[str, typer.Option("--text", "-t", help="Text to speak with cloned voice")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output path")] = Path(
        "output/cloned.wav"
    ),
    model_path: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="HuggingFace model ID or local path. Clone defaults to the Base model.",
        ),
    ] = "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    device: Annotated[str, typer.Option("--device", "-d", help="Device (mps, cuda, cpu)")] = "mps",
    language: Annotated[
        Language,
        typer.Option(
            "--language",
            "-l",
            help="Target clone language (Spanish, English, Auto)",
        ),
    ] = DEFAULT_CLONE_LANGUAGE,
    embedding_only: Annotated[
        bool,
        typer.Option(
            "--embedding-only",
            help="Use embedding-only cloning. Default is ICL cloning.",
        ),
    ] = False,
    seed: Annotated[int, typer.Option("--seed", help="Sampling seed")] = DEFAULT_CLONE_SEED,
    temperature: Annotated[
        float, typer.Option("--temperature", help="Sampling temperature")
    ] = DEFAULT_CLONE_TEMPERATURE,
    top_p: Annotated[
        float, typer.Option("--top-p", help="Nucleus sampling top-p")
    ] = DEFAULT_CLONE_TOP_P,
    top_k: Annotated[int, typer.Option("--top-k", help="Top-k sampling")] = DEFAULT_CLONE_TOP_K,
    repetition_penalty: Annotated[
        float,
        typer.Option(
            "--repetition-penalty",
            help="Repetition penalty",
        ),
    ] = DEFAULT_CLONE_REPETITION_PENALTY,
    max_new_tokens: Annotated[
        int,
        typer.Option(
            "--max-new-tokens",
            help="Maximum generated tokens",
        ),
    ] = DEFAULT_CLONE_MAX_NEW_TOKENS,
) -> None:
    """Clone voice from reference audio and generate speech.

    Example:
        tts clone reference.wav -r "This is my reference text." -t "Hello world!" -o output.wav
    """
    config = TTSConfig(
        model_path=model_path,
        device=device,
        output_dir=str(output.parent),
        provider=_provider_from_env(),
    )

    if config.provider == "inworld":
        console.print(
            "[red]✗[/red] Voice cloning is not supported by the Inworld provider. "
            "Set TTS_PROVIDER=qwen (or unset it) to clone with the Qwen model."
        )
        raise typer.Exit(code=1)

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

                audio = client.clone_voice(
                    profile,
                    text,
                    language=language,
                    x_vector_only_mode=embedding_only,
                    seed=seed,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    repetition_penalty=repetition_penalty,
                    max_new_tokens=max_new_tokens,
                )

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
    text: Annotated[str, typer.Argument(help="Text to convert to speech")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output path")] = Path(
        "output/speech.wav"
    ),
    language: Annotated[
        Language,
        typer.Option(
            "--language",
            "-l",
            help="Language (Spanish, English, Auto)",
        ),
    ] = "Auto",
    speaker: Annotated[str | None, typer.Option("--speaker", "-s", help="Speaker name")] = None,
    instruct: Annotated[
        str | None, typer.Option("--instruct", "-i", help="Voice style instructions")
    ] = None,
    model_path: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="HuggingFace model ID or local path",
        ),
    ] = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    device: Annotated[str, typer.Option("--device", "-d", help="Device (mps, cuda, cpu)")] = "mps",
) -> None:
    """Generate speech from text using preset voices.

    Example:
        tts generate "Hello world!" -l English -s Serena -o output.wav
    """
    config = TTSConfig(
        model_path=model_path,
        device=device,
        output_dir=str(output.parent),
        provider=_provider_from_env(),
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating speech...", total=None)

        # Initialization only: create_tts_client + CM + repo/use_case
        # construction + request build + execute(). Wait — execute() returns
        # GenerationResult (failure is data, NOT raised), so it cannot raise
        # a GenerationFailure. BUT it CAN raise a programming bug (KeyError,
        # AttributeError). Per R2 "no swallowing programming bugs", execute()
        # MUST sit OUTSIDE the except-Exception block. Same for request build.
        #
        # So this try covers ONLY: client creation, CM entry, repo/use_case
        # construction. execute() is called after the try, inside the CM.
        try:
            client = create_tts_client(config)
        except typer.Exit:
            raise
        except Exception as e:
            # Init failure only (model load, provider guard).
            # `from None`: typer.Exit is a control-flow signal, NOT caused by
            # the caught exception — chaining would misleadingly suggest
            # causation. The error class+message is already printed above.
            progress.update(task, completed=True)
            console.print(f"[red]✗ Error:[/red] {type(e).__name__}: {e}")
            raise typer.Exit(code=1) from None

        # Both QwenTTSClient and InworldTTSClient are context managers;
        # the domain TTSClient protocol omits CM methods by design.
        with client:  # type: ignore[attr-defined]
            repo = FileAudioRepository(output_dir=str(output.parent))
            use_case = GenerateSpeechUseCase(tts_client=client, audio_repo=repo)

            request = GenerateSpeechRequest(
                text=text,
                language=language,
                speaker=speaker,
                instruct=instruct,
            )
            # execute() returns GenerationResult; does NOT raise TTS errors
            # (they are wrapped into GenerationFailure). Programming bugs
            # (KeyError/AttributeError) propagate uncaught per R2.
            result = use_case.execute(request)

        progress.update(task, completed=True)

        # Consume GenerationResult via match — failure is data, NOT raised.
        match result:
            case GenerationSuccess():
                console.print(f"[green]✓[/green] Audio saved to: {result.audio_path}")
                console.print(f"  Duration: {result.duration_seconds:.2f}s")
            case GenerationFailure():
                # Print error_class_name only — NEVER str(error) (R5 + R3).
                console.print(f"[red]✗ Error:[/red] {type(result.error).__name__}")
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
