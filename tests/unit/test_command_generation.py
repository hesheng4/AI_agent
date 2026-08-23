from app.core.toolchain import (
    QuantizationConfig,
    VLLMRunConfig,
    generate_quantization_script,
    generate_vllm_launch_command,
)
from app.core.validator import (
    ValidationConfig,
    VLLMServerConfig,
    generate_vllm_serve_command,
)


def test_vllm_launch_command_quotes_dynamic_values():
    command = generate_vllm_launch_command(
        VLLMRunConfig(
            model="/models/Qwen 7B's",
            extra_args={"served-model-name": "name with spaces"},
        )
    )

    assert "--model '/models/Qwen 7B'\"'\"'s'" in command
    assert "--served-model-name 'name with spaces'" in command


def test_validator_serve_command_quotes_dynamic_values():
    command = generate_vllm_serve_command(
        ValidationConfig(
            model_path="/models/Qwen 7B's",
            vllm_server=VLLMServerConfig(served_model_name="model alias"),
        )
    )

    assert "vllm serve '/models/Qwen 7B'\"'\"'s'" in command
    assert "--served-model-name 'model alias'" in command


def test_quantization_script_uses_valid_python_literals():
    script = generate_quantization_script(
        config=QuantizationConfig(
            model_path="C:/models/Qwen 7B's",
            output_path="C:/out dir/model",
            dataset='data "quoted"',
        )
    )

    compile(
        script.split("python3 << 'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0],
        "<generated>",
        "exec",
    )
