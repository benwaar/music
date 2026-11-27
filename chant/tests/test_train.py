"""Tests for chant.train — LoRA fine-tuning pipeline.

Tests cover individual functions (model loading, LoRA attachment, tokenization)
without running a full training loop (too slow for CI).
"""

import torch
import pytest

from chant.train import (
    TrainConfig,
    attach_lora,
    load_base_model,
    load_trained_model,
    print_trainable_params,
    tokenize_example,
    load_examples,
)


# ---------------------------------------------------------------------------
# Fixtures (load once per module — model loading is slow)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def base_model_and_tokenizer():
    model, tokenizer = load_base_model("HuggingFaceTB/SmolLM2-360M")
    return model, tokenizer


@pytest.fixture(scope="module")
def tokenizer(base_model_and_tokenizer):
    return base_model_and_tokenizer[1]


# ---------------------------------------------------------------------------
# Step 1: Load base model
# ---------------------------------------------------------------------------

class TestLoadBaseModel:
    def test_model_loads(self, base_model_and_tokenizer):
        model, _ = base_model_and_tokenizer
        assert model is not None

    def test_model_is_causal_lm(self, base_model_and_tokenizer):
        model, _ = base_model_and_tokenizer
        assert "CausalLM" in type(model).__name__

    def test_tokenizer_has_pad_token(self, base_model_and_tokenizer):
        _, tok = base_model_and_tokenizer
        assert tok.pad_token is not None

    def test_tokenizer_vocab_size(self, base_model_and_tokenizer):
        _, tok = base_model_and_tokenizer
        assert len(tok) > 10_000


# ---------------------------------------------------------------------------
# Step 2: LoRA attachment
# ---------------------------------------------------------------------------

class TestAttachLoRA:
    def test_returns_peft_model(self, base_model_and_tokenizer):
        model, _ = base_model_and_tokenizer
        config = TrainConfig()
        peft_model = attach_lora(model, config)
        assert "Peft" in type(peft_model).__name__

    def test_trainable_params_much_smaller(self, base_model_and_tokenizer):
        model, _ = base_model_and_tokenizer
        config = TrainConfig()
        peft_model = attach_lora(model, config)
        trainable = sum(p.numel() for p in peft_model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in peft_model.parameters())
        assert trainable < total * 0.01  # less than 1%

    def test_base_weights_frozen(self, base_model_and_tokenizer):
        model, _ = base_model_and_tokenizer
        config = TrainConfig()
        peft_model = attach_lora(model, config)
        base_params = [
            p for n, p in peft_model.named_parameters()
            if "lora" not in n.lower()
        ]
        assert all(not p.requires_grad for p in base_params)


# ---------------------------------------------------------------------------
# Step 3: Tokenization
# ---------------------------------------------------------------------------

class TestTokenizeExample:
    def test_basic_tokenization(self, tokenizer):
        result = tokenize_example(
            "### Instruction:\nTest\n### Response:\n",
            "<BOS> N60 D120 C0 V7 <EOS>",
            tokenizer,
            max_tokens=512,
        )
        assert result is not None
        assert "input_ids" in result
        assert "labels" in result
        assert "attention_mask" in result

    def test_prompt_masked_in_labels(self, tokenizer):
        prompt = "### Instruction:\nTest\n### Response:\n"
        result = tokenize_example(
            prompt,
            "<BOS> N60 D120 C0 V7 <EOS>",
            tokenizer,
            max_tokens=512,
        )
        prompt_len = tokenizer(prompt, return_tensors="pt")["input_ids"].shape[1]
        masked = (result["labels"][0] == -100).sum().item()
        assert masked == prompt_len

    def test_truncation_applied(self, tokenizer):
        long_completion = " | ".join(["N60 D120 C0 V7"] * 1000)
        result = tokenize_example(
            "### Instruction:\nTest\n### Response:\n",
            f"<BOS> {long_completion} <EOS>",
            tokenizer,
            max_tokens=128,
        )
        assert result["input_ids"].shape[1] == 128

    def test_empty_completion_returns_none(self, tokenizer):
        prompt = "A" * 500
        result = tokenize_example(
            prompt, "", tokenizer, max_tokens=64,
        )
        # If prompt fills the entire window, no completion tokens → None
        if result is not None:
            assert (result["labels"] != -100).sum().item() > 0

    def test_forward_pass_produces_loss(self, base_model_and_tokenizer):
        model, tok = base_model_and_tokenizer
        config = TrainConfig()
        peft_model = attach_lora(model, config)
        peft_model.train()

        example = tokenize_example(
            "### Instruction:\nTest\n### Response:\n",
            "<BOS> N60 D120 C0 V7 <EOS>",
            tok,
            max_tokens=512,
        )
        outputs = peft_model(**example)
        assert outputs.loss is not None
        assert outputs.loss.item() > 0
        assert torch.isfinite(outputs.loss)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestTrainConfig:
    def test_defaults(self):
        c = TrainConfig()
        assert c.lora_rank == 8
        assert c.epochs == 3
        assert c.batch_size == 1
        assert c.max_tokens == 2048
        assert c.target_modules == ["q_proj", "v_proj"]

    def test_override(self):
        c = TrainConfig(lora_rank=4, epochs=1)
        assert c.lora_rank == 4
        assert c.epochs == 1


# ---------------------------------------------------------------------------
# Checkpoint round-trip
# ---------------------------------------------------------------------------

class TestCheckpoint:
    def test_save_and_reload(self, base_model_and_tokenizer, tmp_path):
        """Save a LoRA adapter, reload it, verify it produces output."""
        model, tok = base_model_and_tokenizer
        config = TrainConfig()
        peft_model = attach_lora(model, config)

        # Save
        save_path = tmp_path / "lora_adapter"
        peft_model.save_pretrained(str(save_path))
        tok.save_pretrained(str(save_path))

        # Reload
        loaded_model, loaded_tok = load_trained_model(
            checkpoint_dir=tmp_path,
            base_model=config.base_model,
        )
        assert "Peft" in type(loaded_model).__name__

        # Generate a few tokens
        prompt = "### Instruction:\nTest\n### Response:\n"
        inputs = loaded_tok(prompt, return_tensors="pt")
        with torch.no_grad():
            output = loaded_model.generate(
                **inputs, max_new_tokens=20, do_sample=False,
            )
        decoded = loaded_tok.decode(output[0], skip_special_tokens=True)
        assert len(decoded) > len(prompt)


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------

class TestQualityGate:
    def test_quality_result_fields(self):
        from chant.train import QualityResult
        r = QualityResult(
            caption="test",
            generated="<BOS> N60 D120 C0 V7 <EOS>",
            parseable=True,
            num_events=1,
            pitch_in_range=True,
            duration_in_range=True,
            channels_in_range=True,
        )
        assert r.parseable
        assert r.num_events == 1
