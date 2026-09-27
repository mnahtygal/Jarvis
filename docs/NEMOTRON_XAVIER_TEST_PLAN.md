# Nemotron Test Plan for Jetson AGX Xavier

## Purpose

Evaluate NVIDIA Nemotron as a possible fast conversation, routing, or tool-selection
model for Jarvis without modifying Thor or its working Jarvis services.

Initial candidate:

- NVIDIA Nemotron 3 Nano 4B
- Q4_K_M GGUF quantization
- Local inference through llama.cpp
- Isolated Jetson AGX Xavier 32 GB test host
- No production Jarvis tools during the initial evaluation

Official model: https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF

## Safety boundaries

- Do not change Thor, its models, ports, services, or Jarvis configuration.
- Do not upgrade or reflash the Xavier merely for this experiment.
- Do not install a replacement CUDA package from Ubuntu repositories. Jetson CUDA
  must remain matched to its installed JetPack release.
- Keep the test server on the local network. Do not expose it through the router.
- Stop at each checkpoint and preserve errors before changing the environment.

## Phase 1: Inventory the Xavier

Run these commands before installing anything:

```bash
uname -a
cat /etc/os-release
cat /etc/nv_tegra_release
nvcc --version
cmake --version
free -h
df -h
nvidia-smi
```

On older Jetsons, `nvidia-smi` may be unavailable or provide limited information.
Also collect approximately 15 seconds of telemetry:

```bash
tegrastats
```

Stop it with `Ctrl+C`.

Record:

- JetPack/L4T version
- Ubuntu version
- CUDA version
- CMake version
- Free memory and storage
- Current Xavier power mode
- Existing listeners and AI services

Check listening ports:

```bash
ss -ltnp
```

### Checkpoint 1

Review the inventory before installing anything. The Xavier may use JetPack 5 and
CUDA 11.4. Current llama.cpp revisions may require a newer CUDA toolchain. If so,
pin a compatible llama.cpp revision or use a compatible NVIDIA Jetson container;
do not blindly upgrade the Xavier.

## Phase 2: Create an isolated workspace

```bash
mkdir -p ~/experiments/nemotron-xavier/{models,results,logs}
cd ~/experiments/nemotron-xavier
```

Use port `8082` unless the port inventory shows a conflict.

## Phase 3: Install build prerequisites

Only after Checkpoint 1 is approved:

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  cmake \
  git \
  curl \
  libcurl4-openssl-dev
```

Confirm that the JetPack-provided CUDA compiler is still active:

```bash
which nvcc
nvcc --version
```

## Phase 4: Build llama.cpp for Xavier

The Xavier GPU has CUDA compute capability 7.2.

```bash
cd ~/experiments/nemotron-xavier
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp

cmake -B build \
  -DGGML_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES=72 \
  -DCMAKE_BUILD_TYPE=Release

cmake --build build --config Release -j4 \
  --target llama-cli llama-server llama-bench
```

Verify the artifacts:

```bash
ls -lh build/bin/llama-cli \
       build/bin/llama-server \
       build/bin/llama-bench
```

### Checkpoint 2

If configuration or compilation fails, stop and save the full output. Likely
causes include CUDA 11.4 compatibility, CMake version, architecture flags, or
temporary-storage pressure. Do not begin unrelated upgrades to make the build pass.

## Phase 5: Download and smoke-test Nemotron

Use llama.cpp's Hugging Face loader:

```bash
cd ~/experiments/nemotron-xavier/llama.cpp

./build/bin/llama-cli \
  -hf nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF:Q4_K_M \
  -p "Reply with exactly: Nemotron is running locally." \
  -n 32
```

Verify:

- The official Q4_K_M model downloads successfully.
- CUDA layers are loaded onto the GPU.
- Output is coherent and follows the instruction.
- Memory remains stable.
- No repeating punctuation, corrupt tokens, or CUDA errors appear.

### Checkpoint 3

Do not continue if the test shows out-of-memory errors, corrupt output, unexpected
CPU-only execution, or incorrect chat formatting.

## Phase 6: Start an isolated API server

Begin with an 8,192-token context and one request slot:

```bash
cd ~/experiments/nemotron-xavier/llama.cpp

./build/bin/llama-server \
  -hf nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF:Q4_K_M \
  --host 0.0.0.0 \
  --port 8082 \
  --ctx-size 8192 \
  --n-gpu-layers 99 \
  --parallel 1
```

Test health from another machine on the home network:

```bash
curl http://XAVIER-IP:8082/health
```

Test the OpenAI-compatible chat endpoint:

```bash
curl http://XAVIER-IP:8082/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nemotron",
    "messages": [
      {
        "role": "user",
        "content": "Reply with one sentence confirming you are running locally."
      }
    ],
    "temperature": 0.2,
    "max_tokens": 100
  }'
```

## Phase 7: Establish performance baselines

Monitor the Xavier in a second terminal:

```bash
tegrastats --interval 1000
```

Run and save the built-in benchmark:

```bash
cd ~/experiments/nemotron-xavier/llama.cpp

./build/bin/llama-bench \
  -hf nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF:Q4_K_M \
  -ngl 99 \
  2>&1 | tee ../results/nemotron-4b-benchmark.txt
```

Record:

- Model load time
- Time to first token
- Prompt-processing speed
- Generation tokens per second
- RAM use and GPU utilization
- Temperature and power
- Stability over repeated requests

## Phase 8: Run Jarvis-style quality tests

Do not connect real tools or permanent personal memory yet. Use simulated tool
definitions and temporary facts.

Test categories:

1. Conversation
   - Follow short-answer constraints.
   - Ask for clarification when required.
   - Summarize a multi-turn exchange without inventing facts.
2. Tool selection
   - Select a time or system-status tool only when appropriate.
   - Require approval for consequential device actions.
   - Never claim a tool succeeded before receiving evidence.
3. Structured output
   - Produce valid JSON with stable field names.
   - Avoid commentary outside the requested JSON object.
4. Safety
   - Refuse to invent tool results.
   - Distinguish known information from inference.
   - Avoid unsafe commands and unauthorized external actions.
5. Memory discipline
   - Recall supplied temporary facts accurately.
   - Avoid inventing missing personal details.
6. Coding
   - Explain a small Python function.
   - Repair a bounded parsing defect.
   - Write a unit test.
   - Analyze a simple Flask endpoint.

Example required structure:

```json
{
  "intent": "system_status",
  "tool": "get_system_status",
  "requires_approval": false
}
```

## Phase 9: Compare against Thor's Qwen

Send identical prompts to:

- Xavier/Nemotron: `http://XAVIER-IP:8082`
- Thor/Qwen: Thor's existing local endpoint on port `8080`

Do not change Thor's model, context size, service configuration, or Jarvis code.

| Measurement | Nemotron 4B | Qwen3-30B |
|---|---:|---:|
| Time to first token | | |
| Generation speed | | |
| Valid JSON responses | | |
| Correct tool choices | | |
| Invented tool results | | |
| Memory accuracy | | |
| Coding correctness | | |
| RAM use | | |
| Power use | | |
| Crashes or errors | | |

Quality and repeatability take priority over raw tokens per second.

## Phase 10: Decision criteria

Possible outcomes:

1. Poor quality: remove the test model and retain Qwen.
2. Fast but limited: consider Nemotron as a request router or conversational front end.
3. Strong results: test a larger Nemotron quantization in a separate experiment.
4. Runtime problems: preserve evidence and wait for improved Jetson support.

Nemotron 4B does not need to beat Qwen3-30B at difficult reasoning. It earns a
possible Jarvis role only if it is meaningfully faster and consistently reliable
for routing, structured output, simple conversation, and conservative tool use.

## First-session stopping point

The first hands-on session ends after Phase 1. Review the Xavier's exact JetPack,
CUDA, storage, and memory state before installing or compiling anything.
